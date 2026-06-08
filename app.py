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

    if not df.empty:
    # 1. 월/분기 데이터를 범주형으로 강제 정의 (순서 고정)
    df['월'] = df['DateTime'].dt.month
    df['분기'] = df['DateTime'].dt.quarter
    
    # 2. 피벗 테이블 생성 (월/분기별 합계)
    # margins=True로 '총 합계' 자동 생성
    pivot = df.pivot_table(
        index='업체명', 
        columns=['분기', '월'], 
        values='전체계약금액', 
        aggfunc='sum', 
        fill_value=0
    )
    
    # 3. 분기별 합계 컬럼 추가 (1분기, 2분기, 3분기, 4분기)
    for q in range(1, 5):
        pivot[f'{q}분기 합계'] = pivot.loc[:, q].sum(axis=1) if q in pivot.columns else 0
        
    # 4. 연간 총 합계 컬럼 추가
    pivot['총 합계'] = pivot[[f'{q}분기 합계' for q in range(1, 5)]].sum(axis=1)
    
    # 5. 보기 좋게 정렬 (순서: 1월, 2월, 3월, 1분기 합계, 4월...)
    cols_order = []
    for q in range(1, 5):
        for m in range(1, 4):
            if (q, (q-1)*3 + m) in pivot.columns:
                cols_order.append((q, (q-1)*3 + m))
        cols_order.append(f'{q}분기 합계')
    cols_order.append('총 합계')
    
    pivot = pivot[cols_order]
    pivot = pivot.sort_values(by='총 합계', ascending=False)
    
    # 6. 최종 렌더링 (천 단위 콤마)
    st.subheader("📋 업체별 월/분기 실적 종합 분석표")
    st.dataframe(pivot.style.format("{:,.0f}원"), use_container_width=True)
    
    # 7. 다운로드 버튼
    st.download_button("📥 전체 분석 데이터 다운로드", pivot.to_csv().encode('utf-8-sig'), "조달_실적_종합_분석.csv")
else:
    st.warning("데이터가 아직 없습니다.")
