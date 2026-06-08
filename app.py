import streamlit as st
import pandas as pd
from supabase import create_client
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os

# 1. 프리미엄 와이드 레이아웃 설정
st.set_page_config(layout="wide", page_title="조달청 실 realtime 통합 대시보드", page_icon="🏆")

# 스타일 지정을 위한 CSS 주입 (가독성 극대화)
st.markdown("""
    <style>
    .main-title { font-size:32px; font-weight:800; color:#1E3A8A; margin-bottom:5px; }
    .sub-title { font-size:16px; color:#4B5563; margin-bottom:25px; }
    .metric-box { background-color: #F3F4F6; padding: 15px; border-radius: 10px; border-left: 5px solid #2563EB; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🏆 조달청 실적 실시간 통합 분석 대시보드</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Single Source of Truth (Master_DB) 기반 실시간 차분 융합 시스템</div>', unsafe_allow_html=True)

# 2. Supabase 자원 동기화
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

try:
    supabase = get_supabase()
except Exception as e:
    st.error(f"Supabase 설정 오류: {e}. secrets를 확인하세요.")

# 3. [실시간 기능] 5월 18일부터 현재(6월)까지 조달청 API 차분 수집 함수
def run_realtime_sync():
    try:
        API_KEY = st.secrets["API_KEY"]
    except:
        st.error(" secrets에 API_KEY가 설정되어 있지 않습니다.")
        return -1
        
    # Master_DB가 끊긴 시점 부근(5월 15일)부터 오늘(2026년 6월 8일)까지 기간 타겟팅
    bgn_date = "20260515"
    end_date = datetime.now().strftime("%Y%m%d")
    
    # 조달청 오퍼레이션 4번 (getDlvrReqInfoList) 정답 주소 활용
    url = f"http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList?serviceKey={API_KEY}&numOfRows=999&pageNo=1&inqryDiv=1&inqryBgnDate={bgn_date}&inqryEndDate={end_date}"
    
    try:
        res = requests.get(url, verify=False, timeout=15)
        if res.status_code == 429:
            st.error("🚨 조달청 API 트래픽 한도 초과 (429 Quota Exceeded)")
            return -1
        elif res.status_code != 200:
            st.error(f"🚨 조달청 서버 통신 실패 (상태 코드: {res.status_code})")
            return -1
            
        items = ET.fromstring(res.content).findall('.//item')
        data_list = []
        
        for item in items:
            name = item.findtext('cntrctrNm')
            if not name or name.strip() in ["테스트업체", "테스트", "000"]: 
                continue # 쓰레기 데이터 원천 차단
                
            data_list.append({
                "사업자등록번호": item.findtext('bizrno'),
                "업체명": name.strip(),
                "물품분류명": item.findtext('prdctClsfcNm'),
                "납품요구번호": item.findtext('dlvrReqNo'),
                "일자": item.findtext('dlvrReqRcptDate'),
                "전체계약금액": float(item.findtext('dlvrReqAmt') or 0),
                "MAS여부": "Y",
                "계약종류_상세": "MAS (실시간수집)"
            })
            
        if data_list:
            # Supabase에 중복 없이 upsert 적재
            supabase.table("procurement_data").upsert(data_list, on_conflict="납품요구번호").execute()
            return len(data_list)
        return 0
    except Exception as e:
        st.error(f"수집 엔진 구동 에러: {e}")
        return -1

# 4. 하이브리드 아키텍처 데이터 로드 엔진 (유실율 0%)
@st.cache_data(ttl=60)
def load_hybrid_master():
    # A. 마스터 파일 로드
    base_file = "Master_DB.csv"
    if os.path.exists(base_file):
        df_file = pd.read_csv(base_file, dtype={'납품요구번호': str, '사업자등록번호': str}, low_memory=False)
    else:
        st.error(f"❌ 기본 파일('{base_file}') 유실됨. 파일 위치를 확인하세요.")
        df_file = pd.DataFrame()
        
    # B. Supabase 실시간 수집본 병합
    try:
        response = supabase.table("procurement_data").select("*").execute()
        df_db = pd.DataFrame(response.data)
        if not df_db.empty:
            df_db['납품요구번호'] = df_db['납품요구번호'].astype(str)
            df = pd.concat([df_file, df_db], ignore_index=True)
        else:
            df = df_file
    except:
        df = df_file

    if df.empty:
        return pd.DataFrame()

    # C. 데이터 무결성 보정 및 마이너스(취소) 금액 살리기
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    df['업체명'] = df['업체명'].fillna("알수없음").astype(str).str.strip()
    
    # 중복 제거 시 Master_DB(앞쪽 데이터)를 지켜 정합성 수치(54억) 보존
    df = df.drop_duplicates(subset=['납품요구번호'], keep='first')
    
    # 쓰레기 더미 제거
    df = df[~df['업체명'].isin(["테스트업체", "테스트", "확인필요", "000", "알수없음"])]
    
    # 날짜 파싱 고도화 (20260515 및 문자열 대응)
    df['일자_clean'] = df['일자'].astype(str).str.replace(r'\.0', '', regex=True).str.strip()
    df['DateTime'] = pd.to_datetime(df['일자_clean'], format='%Y%m%d', errors='coerce')
    
    # 날짜 파싱 실패 데이터 보정
    df['DateTime'] = df['DateTime'].fillna(pd.Timestamp('2026-01-01'))
    
    # 정렬 기준용 연월/분기 생성
    df['연월'] = df['DateTime'].dt.strftime('%m월')
    df['분기'] = df['DateTime'].dt.quarter.astype(str) + "분기"
    
    return df

# 5. 사이드바 제어 보드 (IT 감각 디자인)
with st.sidebar:
    st.markdown("### 📡 실시간 데이터 최신화")
    st.write("클릭 시 5월 18일 이후부터 오늘까지의 조달청 차분 실적을 동기화합니다.")
    if st.button("🔄 실시간 차분 데이터 수집 실행"):
        with st.spinner("조달청 V5 통신 게이트웨이 연결 중..."):
            sync_count = run_realtime_sync()
            if sync_count >= 0:
                st.success(f"🎉 실시간 데이터 {sync_count}건 융합 성공!")
                st.cache_data.clear() # 캐시 폭파 후 새로고침
                st.rerun()
                
    st.markdown("---")
    st.markdown("### 🛠️ 디버깅 필터")
    show_raw = st.checkbox("통합 Raw 데이터셋 보기")

# 데이터 프로세싱 구동
total_df = load_hybrid_master()

if not total_df.empty:
    # 6. 상단 요약 매트릭스 보드 (임원 보고용 세련된 디자인)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="metric-box"><b>📊 누적 분석 건수</b><br><span style="font-size:24px; font-weight:700; color:#2563EB;">{len(total_df):,} 건</span></div>', unsafe_allow_html=True)
    with c2:
        pure_plus = total_df[total_df['전체계약금액'] > 0]['전체계약금액'].sum()
        st.markdown(f'<div class="metric-box"><b>💰 순수 계약 총액 (양수)</b><br><span style="font-size:24px; font-weight:700; color:#10B981;">{pure_plus:,.0f} 원</span></div>', unsafe_allow_html=True)
    with c3:
        net_total = total_df['전체계약금액'].sum()
        st.markdown(f'<div class="metric-box"><b>📉 실상계 총액 (마이너스 반영)</b><br><span style="font-size:24px; font-weight:700; color:#EF4444;">{net_total:,.0f} 원</span></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

# 7. [핵심] 월별, 분기별, 총합계 계층 구조 피벗 테이블 빌드
    st.subheader("🏢 업체별 분기/월별 정밀 실적 분석 (총 합계 순 정렬)")
    
    try:
        # 피벗 테이블 구성
        pivot_table = total_df.pivot_table(
            index='업체명',
            columns=['분기', '연월'],
            values='전체계약금액',
            aggfunc='sum',
            fill_value=0,
            margins=True,
            margins_name='총 합계'
        )
        
        # 컬럼명 평탄화 (튜플 제거)
        new_cols = []
        for col in pivot_table.columns:
            if isinstance(col, tuple):
                new_cols.append(f"{col[0]} {col[1]}".strip())
            else:
                new_cols.append(str(col))
        pivot_table.columns = new_cols
        
        # 정렬 (총 합계 행을 제외하고 정렬 후 다시 결합)
        if '총 합계' in pivot_table.index:
            companies_only = pivot_table.drop('총 합계')
            total_row = pivot_table.loc[['총 합계']]
            sorted_companies = companies_only.sort_values(by='총 합계', ascending=False)
            final_pivot = pd.concat([sorted_companies, total_row])
        else:
            final_pivot = pivot_table.sort_values(by='총 합계', ascending=False)
            
        # [에러 원천 차단] style 함수를 쓰지 않고, 데이터 자체를 '문자열(X,XXX원)'로 강제 변환!
        display_df = final_pivot.copy()
        for col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"{int(x):,}원" if pd.notnull(x) else "0원")
            
        # 렌더링 (아무 기교 없이 가장 안전하게 출력)
        st.dataframe(display_df, use_container_width=True)

        # 8. 대형 차트 (상위 10개사 성과)
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📊 상위 10개 리딩 기업 마켓 셰어 비교")
        
        # 차트용 데이터 (총 합계 행 제외)
        if '총 합계' in final_pivot.index:
            top_10 = final_pivot.drop('총 합계')['총 합계'].head(10)
        else:
            top_10 = final_pivot['총 합계'].head(10)
            
        st.bar_chart(top_10)

    except Exception as e:
        st.error(f"테이블 렌더링 중 치명적 오류: {e}")
        st.warning("원본 데이터를 강제 출력합니다.")
        st.dataframe(total_df, use_container_width=True)

    # Raw 데이터 출력 세션
    if show_raw:
        st.markdown("---")
        st.subheader("📋 융합 Raw 데이터 레이어")
        st.dataframe(total_df[['사업자등록번호', '업체명', '납품요구번호', '일자', '전체계약금액', '계약종류_상세']], use_container_width=True)
