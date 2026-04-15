import streamlit as st
import pandas as pd
import requests
import os
import plotly.express as px
from datetime import datetime, timedelta

# 1. 페이지 설정 및 디자인
st.set_page_config(page_title="Procurement Dashboard v4.6", layout="wide")

# [디자인 강화] 타이틀 완벽 고정 및 사이드바 간격 대폭 축소 CSS
st.markdown("""
    <style>
    /* 🚨 1. 타이틀 고정을 위한 스트림릿 기본 컨테이너 스크롤 강제 해제 */
    .main .block-container {
        overflow: initial !important;
        padding-top: 2rem !important;
    }
    
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    h1, h2, h3 { color: #1e3a8a; font-family: 'Nanum Gothic', sans-serif; }
    
    /* 🚨 2. 사이드바 체크박스 높이/간격을 기존의 40% 수준으로 초압축 */
    section[data-testid="stSidebar"] div[data-testid="stCheckbox"] {
        margin-top: -12px !important;
        margin-bottom: -12px !important;
    }
    section[data-testid="stSidebar"] label[data-baseweb="checkbox"] {
        min-height: 20px !important;
        padding-bottom: 0px !important;
        margin-bottom: 0px !important;
    }
    section[data-testid="stSidebar"] .stCheckbox p {
        font-size: 12.5px !important;
        line-height: 1 !important;
        padding-bottom: 0px !important;
    }
    
    /* 사이드바 헤더 간격 조절 */
    section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {
        margin-top: -15px;
        margin-bottom: 5px;
    }

    /* 🚨 3. 타이틀 상단 찰싹 고정 (Sticky Header) */
    .sticky-header {
        position: -webkit-sticky;
        position: sticky;
        top: 2.875rem; /* 상단 바 바로 아래에 고정 */
        background-color: #f8f9fa; /* 글자 비침 방지용 메인 배경색 */
        z-index: 9999;
        padding: 10px 0 10px 0;
        border-bottom: 2px solid #e9ecef;
        margin-top: -30px;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 설정 및 상수 ---
SERVICE_KEY = "c1b3792f-37f0-4d57-897b-3b3614522855"
TARGET_COMPANIES = ["마이크로시스템", "핀텔", "웹게이트", "크리에이티브넷", "두원전자통신", "올인원 코리아", "티제이원", "앤다스", "지성이엔지", "송우인포텍", "렉스젠", "비티에스", "솔디아", "홍석", "비엔에스테크", "디케이앤트", "제이한테크", "그린아이티코리아", "펜타게이트", "한국아이티에스", "미르텍", "포딕스시스템", "명광", "뉴코리아전자통신", "오티에스", "아라드네트웍스", "시큐인포", "센텍", "원우이엔지", "경림이앤지", "진명아이앤씨", "디라직", "알엠텍", "아이엔아이", "지인테크", "다누시스", "에코아이넷", "사이테크놀로지스", "인텔리빅스", "한국씨텍", "아이즈온솔루션", "대신네트웍스", "새움", "이노뎁", "포소드", "에스카", "제노시스", "디지탈라인", "세오", "포커스에이아이", "비알인포텍", "파로스"]

# --- 2. 데이터 수집 함수 ---
def fetch_api_data():
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    url = "http://apis.data.go.kr/1230000/ShoppingMallPrdctInfoService05/getDlvrReqInfoList"
    params = {'serviceKey': requests.utils.unquote(SERVICE_KEY), 'type': 'json', 'numOfRows': '999', 'pageNo': '1', 'inqryDiv': '1', 'inqryBgnDate': '20260401', 'inqryEndDate': yesterday}
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            items = data.get('response', {}).get('body', {}).get('items', [])
            raw_items = items.get('item', []) if isinstance(items, dict) else items
            if raw_items:
                df = pd.DataFrame(raw_items)
                df_api = df[['corpNm', 'prdctClsfcNm', 'dlvrReqAmt', 'cntrctCnclsStleNm']].copy()
                df_api.columns = ['업체명', '물품분류명', '금액', '계약유형']
                df_api['금액'] = pd.to_numeric(df_api['금액'], errors='coerce').fillna(0)
                df_api['월'] = "4월"
                df_api['건수'] = 1
                return df_api[df_api['업체명'].str.contains('|'.join(TARGET_COMPANIES), na=False)], "성공"
    except: pass
    return pd.DataFrame(), "서버 점검 중 (500)"

@st.cache_data(ttl=600)
def load_data():
    all_dfs = []
    file_map = {"1월": "data.csv", "2월": "data02.csv", "3월": "data03.csv"}
    for month, path in file_map.items():
        if os.path.exists(path):
            try:
                df = pd.read_csv(path, encoding='utf-8-sig', on_bad_lines='skip')
                df.columns = [str(c).strip() for c in df.columns]
                c_corp = next((c for c in df.columns if '업체명' in c), None)
                c_item = next((c for c in df.columns if '물품분류명' in c), None)
                c_method = next((c for c in df.columns if '계약유형' in c or '계약체결형태' in c), None)
                c_amt = next((c for c in df.columns if '금액' in c or '납품금액' in c), None)
                if all([c_corp, c_item, c_method, c_amt]):
                    tmp = pd.DataFrame()
                    tmp['업체명'] = df[c_corp].astype(str).str.strip()
                    tmp['물품분류명'] = df[c_item].astype(str).str.strip()
                    tmp['계약유형'] = df[c_method].astype(str).str.strip()
                    tmp['금액'] = pd.to_numeric(df[c_amt].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                    tmp['월'] = month
                    tmp['건수'] = 1
                    all_dfs.append(tmp)
            except: continue
    df_api, status = fetch_api_data()
    if not df_api.empty: all_dfs.append(df_api)
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame(), status

df_raw, api_status = load_data()

# --- 3. 메인 화면 타이틀 (상단 고정 HTML) ---
st.markdown("""
    <div class="sticky-header">
        <h1 style="margin: 0; padding: 0;">🏆 통합 조달 전략 분석 대시보드 v4.6</h1>
    </div>
""", unsafe_allow_html=True)

# --- 4. 사이드바 및 필터 로직 ---
if not df_raw.empty:
    st.sidebar.header("🔍 분석 필터")
    all_categories = sorted(df_raw['물품분류명'].unique())
    
    if "selected_k" not in st.session_state:
        st.session_state.selected_k = all_categories

    master_k = st.sidebar.checkbox("🌟 품목 분류 전체 선택", value=len(st.session_state.selected_k) == len(all_categories))
    
    selected_k = []
    st.sidebar.write("---")
    st.sidebar.subheader("📦 상세 품목 리스트")
    for cat in all_categories:
        if st.sidebar.checkbox(cat, value=master_k or cat in st.session_state.selected_k, key=f"cat_{cat}"):
            selected_k.append(cat)
    st.session_state.selected_k = selected_k

    st.sidebar.write("---")
    unique_r = sorted(df_raw['계약유형'].unique())
    master_r = st.sidebar.checkbox("📄 계약유형 전체 선택", value=True)
    selected_r = [m for m in unique_r if st.sidebar.checkbox(m, value=master_r, key=f"r_{m}")]
    
    st.sidebar.write("---")
    if "성공" in api_status: st.sidebar.success("✅ 4월 실시간 연동 중")
    else: st.sidebar.warning(f"⚠️ 4월 연동 대기 ({api_status})")

    df_f = df_raw[(df_raw['물품분류명'].isin(selected_k)) & (df_raw['계약유형'].isin(selected_r))]

    if df_f.empty:
        st.info("왼쪽 필터에서 품목을 선택해 주세요.")
    else:
        # [KPI 카드]
        t_amt, t_cnt = df_f['금액'].sum(), df_f['건수'].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("총 납품 실적", f"{int(t_amt/1000000):,} 백만 원")
        c2.metric("총 계약 건수", f"{int(t_cnt):,} 건")
        c3.metric("건당 평균가", f"{int(t_amt/t_cnt/10000) if t_cnt > 0 else 0:,} 만 원")

        # [월별 추이]
        st.markdown("### 📈 매출 추이 (1~4월)")
        trend = df_f.groupby('월').agg({'금액':'sum'}).reindex(["1월", "2월", "3월", "4월"]).fillna(0).reset_index()
        st.plotly_chart(px.area(trend, x='월', y='금액', color_discrete_sequence=['#1e3a8a']), use_container_width=True)

        # [점유율 분석]
        col_l, col_r = st.columns(2)
        with col_l:
            st.write("**Top 10 업체 점유율**")
            comp_data = df_f.groupby('업체명')['금액'].sum().sort_values(ascending=False).head(10)
            st.plotly_chart(px.pie(comp_data, values=comp_data.values, names=comp_data.index, hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu), use_container_width=True)
        with col_r:
            st.write("**품목별 매출 비중**")
            cat_data = df_f.groupby('물품분류명')['금액'].sum()
            st.plotly_chart(px.pie(cat_data, values=cat_data.values, names=cat_data.index, hole=0.4, color_discrete_sequence=px.colors.sequential.Blues_r), use_container_width=True)

        # [상세 데이터 표]
        st.markdown("---")
        st.subheader("📑 상세 실적 통계 (업체별 순위)")
        
        show_cnt = st.checkbox("📊 월별 계약건수 함께 보기", value=False)
        
        pivot_amt = df_f.pivot_table(index='업체명', columns='월', values='금액', aggfunc='sum', fill_value=0)
        pivot_cnt = df_f.pivot_table(index='업체명', columns='월', values='건수', aggfunc='sum', fill_value=0)
        
        display_df = pd.DataFrame(index=pivot_amt.index)
        for m in ["1월", "2월", "3월", "4월"]:
            if m in pivot_amt.columns:
                display_df[f"{m}(액)"] = pivot_amt[m]
                if show_cnt:
                    display_df[f"{m}(건)"] = pivot_cnt[m]
        
        display_df['1분기 합계'] = pivot_amt.get(["1월", "2월", "3월"], pd.DataFrame()).sum(axis=1)
        display_df['전체 총액'] = pivot_amt.sum(axis=1)

        display_df = display_df.sort_values('전체 총액', ascending=False)
        display_df.insert(0, 'No.', range(1, len(display_df) + 1)) 

        def format_columns(val, col_name):
            if col_name == "No.":
                return f"{int(val)}"
            elif "(건)" in col_name:
                return f"{int(val):,}건"
            else:
                return f"{int(val):,}원"

        st.dataframe(
            display_df.style.format({col: (lambda v, c=col: format_columns(v, c)) for col in display_df.columns})
            .background_gradient(cmap='YlGnBu', subset=['전체 총액']), 
            use_container_width=True, height=600
        )
else:
    st.error("데이터 로드 실패. 파일을 확인해 주세요.")
