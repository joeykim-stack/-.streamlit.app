import streamlit as st
import pandas as pd
import requests
import os
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# 1. 페이지 설정 및 디자인
st.set_page_config(page_title="Procurement Dashboard v5.8", layout="wide")

st.markdown("""
    <style>
    .main .block-container { overflow: initial !important; padding-top: 2rem !important; }
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    h1, h2, h3 { color: #1e3a8a; font-family: 'Nanum Gothic', sans-serif; }
    section[data-testid="stSidebar"] div[data-testid="stCheckbox"] { margin-top: -4px !important; margin-bottom: -4px !important; }
    section[data-testid="stSidebar"] label[data-baseweb="checkbox"] { min-height: 26px !important; }
    section[data-testid="stSidebar"] .stCheckbox p { font-size: 13.5px !important; line-height: 1.3 !important; }
    section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 { margin-top: -15px; margin-bottom: 5px; }
    .sticky-header {
        position: -webkit-sticky; position: sticky; top: 2.875rem; 
        background-color: #f8f9fa; z-index: 9999;
        padding: 10px 0 10px 0; border-bottom: 2px solid #e9ecef;
        margin-top: -30px; margin-bottom: 20px;
    }
    .stDownloadButton > button { width: 100%; color: #1e3a8a; border: 1px solid #1e3a8a; }
    </style>
""", unsafe_allow_html=True)

# --- 🚨 [정밀 매칭] 52개 업체 화이트리스트 ---
TARGET_COMPANIES = [
    "주식회사 마이크로시스템", "주식회사 핀텔", "주식회사 웹게이트", "주식회사 크리에이티브넷",
    "주식회사 두원전자통신", "주식회사 올인원 코리아(ALL-IN-ONE KOREA CO., LTD.)", "주식회사 티제이원",
    "(주)앤다스", "(주)지성이엔지", "주식회사 송우인포텍", "렉스젠 주식회사", "비티에스 주식회사",
    "주식회사 솔디아", "주식회사 홍석", "(주)비엔에스테크", "주식회사 디케이앤트", "주식회사 제이한테크",
    "주식회사 그린아이티코리아", "주식회사 펜타게이트", "주식회사 한국아이티에스", "미르텍 주식회사",
    "주식회사 포딕스시스템", "주식회사 명광", "뉴코리아전자통신 주식회사", "주식회사 오티에스",
    "주식회사 아라드네트웍스", "주식회사 시큐인포", "주식회사센텍", "(주)원우이엔지", "(주)경림이앤지",
    "주식회사 진명아이앤씨", "주식회사 디라직", "주식회사 알엠텍", "주식회사 아이엔아이", "주식회사 지인테크",
    "주식회사 다누시스", "에코아이넷(주)", "사이테크놀로지스 주식회사", "주식회사 인텔리빅스", "한국씨텍(주)",
    "주식회사 아이즈온솔루션", "대신네트웍스주식회사", "주식회사 새움", "이노뎁(주)", "(주)포소드",
    "주식회사 에스카", "주식회사 제노시스", "주식회사 디지탈라인", "주식회사 세오", "주식회사 포커스에이아이",
    "주식회사 비알인포텍", "주식회사 파로스"
]

SERVICE_KEY = "c1b3792f-37f0-4d57-897b-3b3614522855"

def fetch_api_data():
    today = datetime.now().strftime("%Y%m%d")
    url = "http://apis.data.go.kr/1230000/ShoppingMallPrdctInfoService05/getDlvrReqInfoList"
    params = {'serviceKey': requests.utils.unquote(SERVICE_KEY), 'type': 'json', 'numOfRows': '999', 'pageNo': '1', 'inqryDiv': '1', 'inqryBgnDate': '20260415', 'inqryEndDate': today}
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
                df_api['월'] = "4월"; df_api['건수'] = 1
                # 🎯 정밀 매칭 필터
                return df_api[df_api['업체명'].isin(TARGET_COMPANIES)], f"연동 성공 (신규 {len(df_api)}건)"
            else: return pd.DataFrame(), "연결 성공: 실적 정산 대기 중"
        elif res.status_code == 500: return pd.DataFrame(), "조달청 점검 중 (500)"
    except: pass
    return pd.DataFrame(), "실시간 연동 대기"

@st.cache_data(ttl=600)
def load_data():
    all_dfs = []
    file_map = {"1월": "data.csv", "2월": "data02.csv", "3월": "data03.csv", "4월": "data04.csv"}
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
                    tmp['월'] = month; tmp['건수'] = 1
                    # 🎯 정밀 매칭 필터
                    all_dfs.append(tmp[tmp['업체명'].isin(TARGET_COMPANIES)])
            except: continue
    df_api, status = fetch_api_data()
    if not df_api.empty: all_dfs.append(df_api)
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame(), status

df_raw, api_status = load_data()

# --- UI 레이아웃 ---
st.markdown(f'<div class="sticky-header"><h1 style="margin: 0;">🏆 통합 조달 전략 분석 대시보드 v5.8</h1></div>', unsafe_allow_html=True)

if not df_raw.empty:
    st.sidebar.header("🔍 분석 필터")
    all_cats = sorted(df_raw['물품분류명'].unique())
    for c in all_cats:
        if f"cat_{c}" not in st.session_state: st.session_state[f"cat_{c}"] = True
    
    col1, col2 = st.sidebar.columns(2)
    if col1.button("✅ 전체 선택"): 
        for c in all_cats: st.session_state[f"cat_{c}"] = True
    if col2.button("❌ 전체 해제"): 
        for c in all_cats: st.session_state[f"cat_{c}"] = False

    selected_k = [c for c in all_cats if st.sidebar.checkbox(c, key=f"cat_{c}")]
    st.sidebar.write("---")
    unique_r = sorted(df_raw['계약유형'].unique())
    master_r = st.sidebar.checkbox("📄 계약유형 전체 선택", value=True)
    selected_r = [m for m in unique_r if st.sidebar.checkbox(m, value=master_r, key=f"r_{m}")]
    
    st.sidebar.write("---")
    if "연결 성공" in api_status: st.sidebar.info(f"🟢 {api_status}")
    else: st.sidebar.warning(f"⚠️ {api_status}")
    st.sidebar.caption(f"🕒 마지막 동기화: {datetime.now().strftime('%H:%M:%S')}")

    df_f = df_raw[(df_raw['물품분류명'].isin(selected_k)) & (df_raw['계약유형'].isin(selected_r))]

    if df_f.empty: st.info("👈 왼쪽에서 분석할 품목을 선택해 주세요.")
    else:
        # KPI 카드
        t_amt, t_cnt = df_f['금액'].sum(), df_f['건수'].sum()
        k1, k2, k3 = st.columns(3)
        k1.metric("총 납품 실적", f"{int(t_amt/1000000):,} 백만 원")
        k2.metric("총 계약 건수", f"{int(t_cnt):,} 건")
        k3.metric("건당 평균가", f"{int(t_amt/t_cnt/10000) if t_cnt > 0 else 0:,} 만 원")

        # 월별 트렌드
        st.markdown("### 📊 월별 매출 및 계약 건수 트렌드")
        trend = df_f.groupby('월').agg({'금액':'sum', '건수':'sum'}).reindex(["1월", "2월", "3월", "4월"]).fillna(0).reset_index()
        fig_trend = make_subplots(specs=[[{"secondary_y": True}]])
        fig_trend.add_trace(go.Bar(x=trend['월'], y=trend['금액'], name="매출액", marker_color='#1e3a8a', opacity=0.85), secondary_y=False)
        fig_trend.add_trace(go.Scatter(x=trend['월'], y=trend['건수'], name="계약건수", mode='lines+markers+text', text=trend['건수'], textposition="top center", textfont=dict(color='#ff7f0e', size=13, family="Arial Black"), line=dict(color='#ff7f0e', width=3), marker=dict(size=8, color='#ff7f0e')), secondary_y=True)
        fig_trend.update_layout(margin=dict(l=0, r=0, b=0, t=30), height=350, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_trend, use_container_width=True)

        # 점유율 분석
        st.markdown("---")
        st.markdown("### 💎 기간별 점유율 분석")
        selected_period = st.selectbox("📅 분석 기간 선택", ["전체합계", "1분기 (1~3월)", "1월", "2월", "3월", "4월"])
        df_pie = df_f if selected_period == "전체합계" else df_f[df_f['월'].isin(["1월", "2월", "3월"])] if selected_period == "1분기 (1~3월)" else df_f[df_f['월'] == selected_period]

        pl, pr = st.columns(2)
        with pl:
            comp_data = df_pie.groupby('업체명')['금액'].sum().sort_values(ascending=False).head(10)
            if not comp_data.empty:
                fig_p1 = go.Figure(data=[go.Pie(labels=comp_data.index, values=comp_data.values, hole=0.45, pull=[0.12 if i==0 else 0 for i in range(len(comp_data))], textinfo='percent+label', marker=dict(line=dict(color='#ffffff', width=2), colors=px.colors.sequential.Agsunset))])
                fig_p1.update_layout(margin=dict(t=30, b=10, l=10, r=10), showlegend=False, title=f"Top 10 업체 ({selected_period})")
                st.plotly_chart(fig_p1, use_container_width=True)
        with pr:
            cat_data = df_pie.groupby('물품분류명')['금액'].sum().sort_values(ascending=False)
            if not cat_data.empty:
                fig_p2 = go.Figure(data=[go.Pie(labels=cat_data.index, values=cat_data.values, hole=0.45, pull=[0.12 if i==0 else 0 for i in range(len(cat_data))], textinfo='percent+label', marker=dict(line=dict(color='#ffffff', width=2), colors=px.colors.sequential.Tealgrn))])
                fig_p2.update_layout(margin=dict(t=30, b=10, l=10, r=10), showlegend=False, title=f"품목별 비중 ({selected_period})")
                st.plotly_chart(fig_p2, use_container_width=True)

        # 상세 실적 표
        st.markdown("---")
        t_col1, t_col2 = st.columns([5, 1])
        with t_col1: st.subheader("📑 상세 실적 통계 (업체별 순위)")
        
        pivot_amt = df_f.pivot_table(index='업체명', columns='월', values='금액', aggfunc='sum', fill_value=0)
        pivot_cnt = df_f.pivot_table(index='업체명', columns='월', values='건수', aggfunc='sum', fill_value=0)
        show_cnt = st.checkbox("📊 월별 계약건수 함께 보기", value=False)
        
        display_df = pd.DataFrame(index=pivot_amt.index)
        for m in ["1월", "2월", "3월", "4월"]:
            if m in pivot_amt.columns:
                display_df[f"{m}(액)"] = pivot_amt[m]
                if show_cnt: display_df[f"{m}(건)"] = pivot_cnt[m]
        
        display_df['1분기 합계'] = pivot_amt.get(["1월", "2월", "3월"], pd.DataFrame()).sum(axis=1)
        display_df['전체 총액'] = pivot_amt.sum(axis=1)
        display_df = display_df.sort_values('전체 총액', ascending=False).reset_index()
        display_df.insert(0, 'No.', range(1, len(display_df) + 1)) 

        with t_col2:
            csv = display_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("💾 CSV 내보내기", data=csv, file_name=f"procurement_rank_{selected_period}.csv", mime='text/csv')

        format_dict = {col: "{:,.0f}건" if '(건)' in col else ("{}" if col in ['No.', '업체명'] else "{:,.0f}원") for col in display_df.columns}
        styled_df = display_df.style.apply(lambda r: ['background-color: #e6f2ff; font-weight: bold' if r.name < 20 else '']*len(r), axis=1).format(format_dict).background_gradient(cmap='YlGnBu', subset=['전체 총액'])
        
        st.dataframe(styled_df, hide_index=True, column_config={"No.": st.column_config.NumberColumn("No.", width=40)}, use_container_width=True, height=600)
else:
    st.error("데이터 로드 실패. 깃허브 파일을 확인하세요.")
