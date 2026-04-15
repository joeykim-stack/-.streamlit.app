import streamlit as st
import pandas as pd
import requests
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# 1. 페이지 설정 및 디자인
st.set_page_config(page_title="Procurement Dashboard v5.0", layout="wide")

st.markdown("""
    <style>
    .main .block-container { overflow: initial !important; padding-top: 2rem !important; }
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    h1, h2, h3 { color: #1e3a8a; font-family: 'Nanum Gothic', sans-serif; }
    
    /* 사이드바 체크박스 간격 황금비율 */
    section[data-testid="stSidebar"] div[data-testid="stCheckbox"] { margin-top: -4px !important; margin-bottom: -4px !important; }
    section[data-testid="stSidebar"] label[data-baseweb="checkbox"] { min-height: 26px !important; }
    section[data-testid="stSidebar"] .stCheckbox p { font-size: 13.5px !important; line-height: 1.3 !important; }
    section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 { margin-top: -15px; margin-bottom: 5px; }

    /* 타이틀 상단 고정 */
    .sticky-header {
        position: -webkit-sticky; position: sticky; top: 2.875rem; 
        background-color: #f8f9fa; z-index: 9999;
        padding: 10px 0 10px 0; border-bottom: 2px solid #e9ecef;
        margin-top: -30px; margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 설정 및 상수 ---
SERVICE_KEY = "c1b3792f-37f0-4d57-897b-3b3614522855"
TARGET_COMPANIES = ["마이크로시스템", "핀텔", "웹게이트", "크리에이티브넷", "두원전자통신", "올인원 코리아", "티제이원", "앤다스", "지성이엔지", "송우인포텍", "렉스젠", "비티에스", "솔디아", "홍석", "비엔에스테크", "디케이앤트", "제이한테크", "그린아이티코리아", "펜타게이트", "한국아이티에스", "미르텍", "포딕스시스템", "명광", "뉴코리아전자통신", "오티에스", "아라드네트웍스", "시큐인포", "센텍", "원우이엔지", "경림이앤지", "진명아이앤씨", "디라직", "알엠텍", "아이엔아이", "지인테크", "다누시스", "에코아이넷", "사이테크놀로지스", "인텔리빅스", "한국씨텍", "아이즈온솔루션", "대신네트웍스", "새움", "이노뎁", "포소드", "에스카", "제노시스", "디지탈라인", "세오", "포커스에이아이", "비알인포텍"] 
# 🚨 파로스는 리스트에서 제거함 및 하단에서 필터링 추가

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

# 🚨 [수정 포인트 1] 파로스시스템 데이터 원천 삭제
if not df_raw.empty:
    df_raw = df_raw[~df_raw['업체명'].str.contains('파로스', na=False)]

# --- 3. 메인 화면 타이틀 ---
st.markdown("""
    <div class="sticky-header">
        <h1 style="margin: 0; padding: 0;">🏆 통합 조달 전략 분석 대시보드 v5.0</h1>
    </div>
""", unsafe_allow_html=True)

# --- 4. 사이드바 및 필터 로직 ---
if not df_raw.empty:
    st.sidebar.header("🔍 분석 필터")
    all_categories = sorted(df_raw['물품분류명'].unique())
    
    for cat in all_categories:
        if f"cat_{cat}" not in st.session_state:
            st.session_state[f"cat_{cat}"] = True

    def check_all():
        for c in all_categories: st.session_state[f"cat_{c}"] = True
    def uncheck_all():
        for c in all_categories: st.session_state[f"cat_{c}"] = False

    col1, col2 = st.sidebar.columns(2)
    col1.button("✅ 전체 선택", on_click=check_all, use_container_width=True)
    col2.button("❌ 전체 해제", on_click=uncheck_all, use_container_width=True)
    
    selected_k = []
    st.sidebar.write("---")
    st.sidebar.subheader("📦 상세 품목 리스트")
    for cat in all_categories:
        if st.sidebar.checkbox(cat, key=f"cat_{cat}"):
            selected_k.append(cat)

    st.sidebar.write("---")
    unique_r = sorted(df_raw['계약유형'].unique())
    master_r = st.sidebar.checkbox("📄 계약유형 전체 선택", value=True)
    selected_r = [m for m in unique_r if st.sidebar.checkbox(m, value=master_r, key=f"r_{m}")]
    
    st.sidebar.write("---")
    if "성공" in api_status: st.sidebar.success("✅ 4월 실시간 연동 중")
    else: st.sidebar.warning(f"⚠️ 4월 연동 대기 ({api_status})")

    df_f = df_raw[(df_raw['물품분류명'].isin(selected_k)) & (df_raw['계약유형'].isin(selected_r))]

    if df_f.empty:
        st.info("👈 왼쪽 사이드바에서 분석할 품목을 하나 이상 선택해 주세요.")
    else:
        # [KPI 카드]
        t_amt, t_cnt = df_f['금액'].sum(), df_f['건수'].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("총 납품 실적", f"{int(t_amt/1000000):,} 백만 원")
        c2.metric("총 계약 건수", f"{int(t_cnt):,} 건")
        c3.metric("건당 평균가", f"{int(t_amt/t_cnt/10000) if t_cnt > 0 else 0:,} 만 원")

        # 3D 트렌드
        st.markdown("### 🪐 3D 다차원 실적 트렌드 (월별/매출/건수)")
        st.caption("💡 그래프를 마우스로 드래그하여 다양한 각도에서 입체적으로 분석해보세요.")
        trend = df_f.groupby('월').agg({'금액':'sum', '건수':'sum'}).reindex(["1월", "2월", "3월", "4월"]).fillna(0).reset_index()
        fig_3d = px.scatter_3d(trend, x='월', y='금액', z='건수', size='금액', color='금액', color_continuous_scale=px.colors.sequential.Plotly3, text='월', opacity=0.9)
        fig_3d.update_traces(marker=dict(line=dict(width=2, color='white')), textposition='top center')
        fig_3d.update_layout(scene=dict(xaxis_title='월', yaxis_title='매출액', zaxis_title='계약건수', camera=dict(eye=dict(x=1.6, y=-1.6, z=0.8))), margin=dict(l=0, r=0, b=0, t=10), height=500)
        st.plotly_chart(fig_3d, use_container_width=True)

        # 하이엔드 점유율 분석
        st.markdown("---")
        st.markdown("### 💎 하이엔드 점유율 분석")
        selected_period = st.selectbox("📅 분석 기간 (월별/분기별) 선택", ["전체합계", "1분기 (1~3월)", "1월", "2월", "3월", "4월"])

        if selected_period == "전체합계": df_pie = df_f
        elif selected_period == "1분기 (1~3월)": df_pie = df_f[df_f['월'].isin(["1월", "2월", "3월"])]
        else: df_pie = df_f[df_f['월'] == selected_period]

        col_l, col_r = st.columns(2)
        with col_l:
            st.write(f"**Top 10 업체 점유율 ({selected_period})**")
            comp_data = df_pie.groupby('업체명')['금액'].sum().sort_values(ascending=False).head(10)
            if not comp_data.empty:
                pull_vals = [0.15 if i == 0 else 0 for i in range(len(comp_data))]
                fig_pie1 = go.Figure(data=[go.Pie(labels=comp_data.index, values=comp_data.values, hole=0.45, pull=pull_vals, textinfo='percent+label', marker=dict(line=dict(color='#ffffff', width=2), colors=px.colors.sequential.Agsunset))])
                fig_pie1.update_layout(margin=dict(t=20, b=20, l=20, r=20), showlegend=False, paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_pie1, use_container_width=True)
            else: st.info("해당 기간에 데이터가 없습니다.")

        with col_r:
            st.write(f"**품목별 매출 비중 ({selected_period})**")
            cat_data = df_pie.groupby('물품분류명')['금액'].sum().sort_values(ascending=False)
            if not cat_data.empty:
                pull_vals2 = [0.15 if i == 0 else 0 for i in range(len(cat_data))]
                fig_pie2 = go.Figure(data=[go.Pie(labels=cat_data.index, values=cat_data.values, hole=0.45, pull=pull_vals2, textinfo='percent+label', marker=dict(line=dict(color='#ffffff', width=2), colors=px.colors.sequential.Tealgrn))])
                fig_pie2.update_layout(margin=dict(t=20, b=20, l=20, r=20), showlegend=False, paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_pie2, use_container_width=True)
            else: st.info("해당 기간에 데이터가 없습니다.")

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

        # 🚨 [수정 포인트 2] 업체명을 인덱스에서 해제하고, No를 맨 앞에 삽입
        display_df = display_df.sort_values('전체 총액', ascending=False)
        display_df = display_df.reset_index() # 인덱스 해제 (업체명이 컬럼으로 변환됨)
        display_df.insert(0, 'No.', range(1, len(display_df) + 1)) 

        # 포맷팅 딕셔너리 생성
        format_dict = {}
        for col in display_df.columns:
            if col == 'No.': format_dict[col] = "{}"
            elif col == '업체명': pass # 텍스트는 그대로
            elif '(건)' in col: format_dict[col] = "{:,.0f}건"
            else: format_dict[col] = "{:,.0f}원"

        # 🚨 [수정 포인트 3] 상위 20개 업체 색상 하이라이트 함수
        def highlight_top_20(row):
            if row.name < 20: # 0부터 19번 인덱스까지 (상위 20위)
                return ['background-color: #e6f2ff; font-weight: bold'] * len(row)
            return [''] * len(row)

        # 스타일 적용
        styled_df = display_df.style.apply(highlight_top_20, axis=1) \
                                    .format(format_dict) \
                                    .background_gradient(cmap='YlGnBu', subset=['전체 총액'])

        # 🚨 [수정 포인트 4] No. 컬럼 넓이 최소화 및 인덱스 숨김
        st.dataframe(
            styled_df, 
            hide_index=True, # 쓸데없는 0, 1, 2 인덱스 숨김
            column_config={
                "No.": st.column_config.NumberColumn("No.", width="small"), # 넓이 최소화
                "업체명": st.column_config.TextColumn("업체명", width="medium")
            },
            use_container_width=True, 
            height=600
        )
else:
    st.error("데이터 로드 실패. 파일을 확인해 주세요.")
