import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import plotly.express as px
from io import BytesIO

# --- 1. 기본 설정 및 UI 테마 ---
st.set_page_config(page_title="조달청 실적 분석 대시보드", layout="wide")

st.markdown("""
    <style>
    .sticky-header {
        position: sticky;
        top: 0;
        background-color: #f8f9fa;
        z-index: 999;
        padding: 1rem 0;
        border-bottom: 2px solid #e9ecef;
    }
    .css-1d391kg { padding-top: 1rem; }
    </style>
    <div class="sticky-header">
        <h1>🏆 통합 조달 전략 분석 대시보드 v7.0</h1>
    </div>
""", unsafe_allow_html=True)

# --- 2. 분석 대상 52개 업체 (화이트리스트) ---
TARGET_COMPANIES = [
    "주식회사 티제이원", "주식회사 파로스", "주식회사 포딕스시스템", "주식회사 세오", 
    "주식회사 펜타게이트", "주식회사 홍석", "주식회사 솔디아", "주식회사 디라직", 
    "주식회사 새움", "주식회사 디지탈라인", "주식회사 지인테크", "(주)비엔에스테크", 
    "주식회사 시큐인포", "주식회사 명광", "주식회사 올인원 코리아(ALL-IN-ONE KOREA CO., LTD.)", 
    "주식회사 포커스에이아이", "주식회사 한국아이티에스", "(주)앤다스", "주식회사 다누시스", 
    "이노뎁(주)", "주식회사 핀텔", "주식회사 오티에스", "주식회사 에스카", "에코아이넷(주)", 
    "미르텍 주식회사", "주식회사 아이즈온솔루션", "주식회사 그린아이티코리아", "주식회사 제노시스", 
    "(주)지성이엔지", "주식회사 알엠텍", "(주)원우이엔지", "(주)포소드", "주식회사 두원전자통신", 
    "대신네트웍스주식회사", "주식회사 마이크로시스템", "주식회사 크리에이티브넷", "주식회사센텍", 
    "(주)경림이앤지", "주식회사 웹게이트", "한국씨텍(주)", "뉴코리아전자통신 주식회사", 
    "주식회사 제이한테크", "주식회사 아라드네트웍스", "주식회사 진명아이앤씨", "렉스젠 주식회사", 
    "주식회사 디케이앤트", "사이테크놀로지스 주식회사", "주식회사 송우인포텍", "주식회사 아이엔아이", 
    "비티에스 주식회사", "주식회사 인텔리빅스", "주식회사 비알인포텍"
]

# --- 3. 과거 데이터 (CSV) 로드 ---
@st.cache_data(ttl=3600)
def load_local_data():
    files = ['data_mini.csv', 'data02_mini.csv', 'data03_mini.csv', 'data04.csv']
    dfs = []
    for idx, file in enumerate(files):
        try:
            df = pd.read_csv(file)
            df.rename(columns=lambda x: x.strip(), inplace=True)
            amt_col = '납품요구금액' if '납품요구금액' in df.columns else '금액'
            df = df[['업체명', '물품분류명', amt_col, '계약체결형태명']]
            df.columns = ['업체명', '물품분류명', '금액', '계약유형']
            df['월'] = f"{idx+1}월"
            df['업체명'] = df['업체명'].astype(str).str.strip()
            df = df[df['업체명'].isin(TARGET_COMPANIES)]
            dfs.append(df)
        except Exception:
            continue
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# --- 4. 🚀 실시간 API 호출 (30분 쿨타임 재시도 로직) ---
def fetch_api_with_smart_retry():
    # 세션 상태 초기화
    if 'last_try_time' not in st.session_state:
        st.session_state['last_try_time'] = None
    if 'is_success' not in st.session_state:
        st.session_state['is_success'] = False
    if 'api_data' not in st.session_state:
        st.session_state['api_data'] = pd.DataFrame()

    now = datetime.now()

    # 이미 성공했다면 캐시된 데이터 반환
    if st.session_state['is_success']:
        return st.session_state['api_data'], "🟢 API 연동 성공! 실시간 데이터 유지 중"

    # 최초 실행이거나 마지막 시도 후 30분이 지났을 경우에만 서버 찌르기
    if st.session_state['last_try_time'] is None or (now - st.session_state['last_try_time']) > timedelta(minutes=30):
        st.session_state['last_try_time'] = now # 시도 시간 업데이트
        
        API_KEY = "c1b379f7734c7d624ddefea07510eae71b6e12c5fb89970319d76c5ae8db5248"
        URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
        # 시작 날짜는 4월 15일 (data04.csv 이후)
        params = {
            'serviceKey': API_KEY,
            'numOfRows': '100', 'pageNo': '1', 'inqryDiv': '1',
            'inqryBgnDate': '20260415',
            'inqryEndDate': now.strftime('%Y%m%d')
        }
        
        try:
            res = requests.get(URL, params=params, timeout=10)
            if res.status_code == 200:
                root = ET.fromstring(res.content)
                items = root.findall('.//item')
                if items:
                    # 데이터 파싱 성공
                    data_list = []
                    for item in items:
                        corp = item.findtext('corpNm', '').strip()
                        if corp in TARGET_COMPANIES:
                            data_list.append({
                                '업체명': corp,
                                '물품분류명': item.findtext('prdctClsfcNm', ''),
                                '금액': float(item.findtext('dlvrReqAmt', 0)),
                                '계약유형': item.findtext('cntrctCnclsStleNm', ''),
                                '월': '4월'
                            })
                    df_api = pd.DataFrame(data_list)
                    st.session_state['is_success'] = True
                    st.session_state['api_data'] = df_api
                    return df_api, "🟢 연동 성공! 실시간 데이터 업데이트 완료"
                else:
                    return pd.DataFrame(), "🔵 연결 정상: 금일 정산 실적 대기 중"
            elif res.status_code == 500:
                next_time = (now + timedelta(minutes=30)).strftime('%H:%M:%S')
                return pd.DataFrame(), f"⚠️ 조달청 야간 배치/점검 중 (500) - 다음 재시도: {next_time}"
            elif res.status_code == 429:
                next_time = (now + timedelta(minutes=30)).strftime('%H:%M:%S')
                return pd.DataFrame(), f"⚠️ 일일 트래픽 초과 (429) - 자정 후 갱신 대기 (다음 확인: {next_time})"
            else:
                next_time = (now + timedelta(minutes=30)).strftime('%H:%M:%S')
                return pd.DataFrame(), f"⚠️ 통신 장애 ({res.status_code}) - 다음 재시도: {next_time}"
                
        except Exception as e:
            next_time = (now + timedelta(minutes=30)).strftime('%H:%M:%S')
            return pd.DataFrame(), f"⚠️ 서버 타임아웃/응답 없음 - 다음 재시도: {next_time}"
            
    # 30분이 지나지 않았다면 쿨타임 대기 메시지 반환 (서버 호출 안함)
    else:
        next_time = (st.session_state['last_try_time'] + timedelta(minutes=30)).strftime('%H:%M:%S')
        return pd.DataFrame(), f"⏳ 서버 안정화 대기 쿨타임 적용 중... (다음 시도: {next_time})"

# --- 5. 데이터 병합 및 UI 렌더링 ---
df_local = load_local_data()
df_api, api_status_msg = fetch_api_with_smart_retry()

if not df_api.empty:
    df_total = pd.concat([df_local, df_api], ignore_index=True)
else:
    df_total = df_local.copy()

# 사이드바 UI
with st.sidebar:
    st.markdown("### 🔍 분석 필터")
    st.info(api_status_msg)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 전체 선택"):
            if not df_total.empty:
                st.session_state['selected_items'] = list(df_total['물품분류명'].dropna().unique())
    with col2:
        if st.button("❌ 전체 해제"):
            st.session_state['selected_items'] = []

    if 'selected_items' not in st.session_state:
        if not df_total.empty:
            st.session_state['selected_items'] = list(df_total['물품분류명'].dropna().unique())
        else:
            st.session_state['selected_items'] = []
            
    options = list(df_total['물품분류명'].dropna().unique()) if not df_total.empty else []
    selected_items = st.multiselect("품목 선택", options=options, default=st.session_state.get('selected_items', []))

# 메인 필터링 및 화면 출력
if not df_total.empty and selected_items:
    df_filtered = df_total[df_total['물품분류명'].isin(selected_items)]
    
    st.success(f"🟢 데이터 로딩 완료! (총 {len(df_filtered):,}건의 데이터 렌더링 중)")
    
    # --- 📊 1. 핵심 요약 지표 (Metrics) ---
    total_amt = df_filtered['금액'].sum()
    total_cnt = len(df_filtered)
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("💰 누적 납품요구금액")
        st.subheader(f"{total_amt:,.0f} 원")
    with col2:
        st.info("📝 총 계약 건수")
        st.subheader(f"{total_cnt:,} 건")

    st.markdown("---")

    # --- 📈 2. 차트 렌더링 ---
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("### 🏆 업체별 매출 순위 (Top 10)")
        top_10 = df_filtered.groupby('업체명')['금액'].sum().nlargest(10).reset_index()
        fig_bar = px.bar(top_10, x='업체명', y='금액', text_auto='.2s', 
                         color='금액', color_continuous_scale='Blues')
        fig_bar.update_layout(xaxis_title="업체명", yaxis_title="매출액(원)")
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_chart2:
        st.markdown("### 🍩 시장 점유율 (품목별)")
        fig_pie = px.pie(df_filtered, names='물품분류명', values='금액', hole=0.4)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")

    # --- 📋 3. 상세 실적 데이터 표 ---
    st.markdown("### 📋 상세 실적 데이터베이스")
    display_df = df_filtered.groupby(['업체명', '물품분류명', '월']).agg(
        금액=('금액', 'sum'), 
        건수=('금액', 'count')
    ).reset_index().sort_values(by='금액', ascending=False)
    
    st.dataframe(display_df, use_container_width=True, height=300)

    # --- 💾 4. 엑셀 다운로드 기능 ---
    def to_excel(df):
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='조달실적분석')
        writer.close()
        processed_data = output.getvalue()
        return processed_data

    st.download_button(
        label="💾 엑셀(.xlsx) 보고서 다운로드",
        data=to_excel(display_df),
        file_name='조달실적_통합분석보고서.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    
else:
    st.warning("데이터가 없거나 품목이 선택되지 않았습니다. 왼쪽 사이드바에서 필터를 확인해주세요.")

# --- 카피라이트 ---
st.markdown("""
    <hr>
    <div style='text-align: center; color: #adb5bd; padding: 20px 0;'>
        Copyright(C)2026 by Joey Kim. All Right Reserved.
    </div>
""", unsafe_allow_html=True)
