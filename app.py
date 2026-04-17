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
    </style>
    <div class="sticky-header">
        <h1>🏆 통합 조달 전략 분석 대시보드 v7.1</h1>
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

# --- 3. 데이터 로드 및 API 연동 함수들 ---
@st.cache_data(ttl=3600)
def load_local_data():
    files = ['data_mini.csv', 'data02_mini.csv', 'data03_mini.csv', 'data04.csv']
    dfs = []
    for idx, file in enumerate(files):
        try:
            df = pd.read_csv(file)
            df.rename(columns=lambda x: x.strip(), inplace=True)
            amt_col = '납품요구금액' if '납품요구금액' in df.columns else '금액'
            df = df[['업체명', '물품분류명', amt_col]]
            df.columns = ['업체명', '물품분류명', '금액']
            df['월'] = f"{idx+1}월"
            df['업체명'] = df['업체명'].astype(str).str.strip()
            df = df[df['업체명'].isin(TARGET_COMPANIES)]
            dfs.append(df)
        except: continue
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def fetch_api_data():
    if 'last_try_time' not in st.session_state: st.session_state.last_try_time = None
    if 'is_success' not in st.session_state: st.session_state.is_success = False
    if 'api_df' not in st.session_state: st.session_state.api_df = pd.DataFrame()

    now = datetime.now()
    # 30분 쿨타임 체크
    if st.session_state.is_success:
        return st.session_state.api_df, "🟢 실시간 연동 성공 상태"
    
    if st.session_state.last_try_time and (now - st.session_state.last_try_time) < timedelta(minutes=30):
        next_t = (st.session_state.last_try_time + timedelta(minutes=30)).strftime('%H:%M:%S')
        return pd.DataFrame(), f"⏳ 서버 대기 중 (다음 시도: {next_t})"

    st.session_state.last_try_time = now
    try:
        API_KEY = "c1b379f7734c7d624ddefea07510eae71b6e12c5fb89970319d76c5ae8db5248"
        URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
        params = {'serviceKey': API_KEY, 'numOfRows': '100', 'inqryDiv': '1', 
                  'inqryBgnDate': '20260415', 'inqryEndDate': now.strftime('%Y%m%d')}
        res = requests.get(URL, params=params, timeout=10)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            items = root.findall('.//item')
            data_list = []
            for item in items:
                corp = item.findtext('corpNm', '').strip()
                if corp in TARGET_COMPANIES:
                    data_list.append({'업체명': corp, '물품분류명': item.findtext('prdctClsfcNm', ''),
                                      '금액': float(item.findtext('dlvrReqAmt', 0)), '월': '4월'})
            df_api = pd.DataFrame(data_list)
            st.session_state.is_success = True
            st.session_state.api_df = df_api
            return df_api, "🟢 실시간 데이터 업데이트 완료"
        return pd.DataFrame(), f"⚠️ 서버 응답 에러 ({res.status_code})"
    except:
        return pd.DataFrame(), "⚠️ 통신 시간 초과"

# --- 4. 메인 데이터 처리 ---
df_local = load_local_data()
df_api, api_status = fetch_api_data()
df_total = pd.concat([df_local, df_api], ignore_index=True) if not df_api.empty else df_local

# --- 5. 사이드바 필터 (핵심 수정 부분) ---
with st.sidebar:
    st.header("🔍 분석 필터")
    st.info(api_status)
    
    if not df_total.empty:
        all_items = sorted(df_total['물품분류명'].dropna().unique())
        
        # 세션 스테이트 초기화 (데이터가 있을 때만)
        if 'sel_items' not in st.session_state or not st.session_state.sel_items:
            st.session_state.sel_items = all_items

        # 전체 선택/해제 버튼
        c1, c2 = st.columns(2)
        if c1.button("✅ 전체 선택"): st.session_state.sel_items = all_items
        if c2.button("❌ 전체 해제"): st.session_state.sel_items = []

        # 필터 위젯 (이 부분이 무조건 나와야 함)
        selected_items = st.multiselect("품목을 선택하세요", options=all_items, default=st.session_state.sel_items)
    else:
        st.warning("데이터 로딩 중입니다...")
        selected_items = []

# --- 6. 메인 화면 렌더링 ---
if not df_total.empty and selected_items:
    df_f = df_total[df_total['물품분류명'].isin(selected_items)]
    
    # 지표
    m1, m2 = st.columns(2)
    m1.metric("💰 총 납품요구금액", f"{df_f['금액'].sum():,.0f}원")
    m2.metric("📝 총 계약 건수", f"{len(df_f):,}건")

    # 차트
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🏆 업체별 매출 Top 10")
        top10 = df_f.groupby('업체명')['금액'].sum().nlargest(10).reset_index()
        st.plotly_chart(px.bar(top10, x='업체명', y='금액', text_auto='.2s', color='금액'), use_container_width=True)
    with col_b:
        st.subheader("🍩 품목별 점유율")
        st.plotly_chart(px.pie(df_f, names='물품분류명', values='금액', hole=0.4), use_container_width=True)

    # 표 및 다운로드
    st.subheader("📋 상세 실적 내역")
    view_df = df_f.groupby(['업체명', '물품분류명', '월'])['금액'].sum().reset_index().sort_values('금액', ascending=False)
    st.dataframe(view_df, use_container_width=True)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        view_df.to_excel(writer, index=False)
    st.download_button("💾 엑셀 다운로드", output.getvalue(), "조달실적분석.xlsx", "application/vnd.ms-excel")
else:
    st.info("왼쪽 필터에서 품목을 선택하면 분석이 시작됩니다.")

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim.</center>", unsafe_allow_html=True)
