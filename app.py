import streamlit as st
import pandas as pd
import requests
import os
import plotly.express as px
from datetime import datetime, timedelta

# 1. 페이지 설정 및 디자인 강화
st.set_page_config(page_title="Procurement Dashboard v4.0", layout="wide")

# 커스텀 CSS 적용 (프리미엄 디자인)
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    div[data-testid="stExpander"] { border: none !important; box-shadow: 0 2px 4px rgba(0,0,0,0.05); background-color: white; border-radius: 10px; }
    h1, h2, h3 { color: #1e3a8a; font-family: 'Nanum Gothic', sans-serif; }
    .stDataFrame { border-radius: 10px; overflow: hidden; }
    </style>
""", unsafe_allow_html=True)

# --- 설정 및 상수 ---
SERVICE_KEY = "c1b3792f-37f0-4d57-897b-3b3614522855"
TARGET_COMPANIES = ["마이크로시스템", "핀텔", "웹게이트", "크리에이티브넷", "두원전자통신", "올인원 코리아", "티제이원", "앤다스", "지성이엔지", "송우인포텍", "렉스젠", "비티에스", "솔디아", "홍석", "비엔에스테크", "디케이앤트", "제이한테크", "그린아이티코리아", "펜타게이트", "한국아이티에스", "미르텍", "포딕스시스템", "명광", "뉴코리아전자통신", "오티에스", "아라드네트웍스", "시큐인포", "센텍", "원우이엔지", "경림이앤지", "진명아이앤씨", "디라직", "알엠텍", "아이엔아이", "지인테크", "다누시스", "에코아이넷", "사이테크놀로지스", "인텔리빅스", "한국씨텍", "아이즈온솔루션", "대신네트웍스", "새움", "이노뎁", "포소드", "에스카", "제노시스", "디지탈라인", "세오", "포커스에이아이", "비알인포텍", "파로스"]

# --- 2. 4월 API 수집 ---
def fetch_api_data():
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    url = "http://apis.data.go.kr/1230000/ShoppingMallPrdctInfoService05/getDlvrReqInfoList"
    params = {'serviceKey': requests.utils.unquote(SERVICE_KEY), 'type': 'json', 'numOfRows': '999', 'pageNo': '1', 'inqryDiv': '1', 'inqryBgnDate': '20260401', 'inqryEndDate': yesterday}
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            body = data.get('response', {}).get('body', {})
            items_container = body.get('items', [])
            raw_items = items_container.get('item', []) if isinstance(items_container, dict) else items_container
            if raw_items:
                df = pd.DataFrame(raw_items)
                df_api = df[['corpNm', 'prdctClsfcNm', 'dlvrReqAmt', 'cntrctCnclsStleNm']].copy()
                df_api.columns = ['업체명', '물품분류명', '금액', '계약유형']
                df_api['금액'] = pd.to_numeric(df_api['금액'], errors='coerce').fillna(0)
                df_api['월'] = "4월"
                df_api['건수'] = 1
                return df_api[df_api['업체명'].str.contains('|'.join(TARGET_COMPANIES), na=False)], "성공"
    except Exception as e: return None, str(e)
    return pd.DataFrame(), "서버 미응답"

# --- 3. 데이터 로드 ---
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
    if df_api is not None and not df_api.empty: 
        all_dfs.append(df_api)
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame(), status

df_raw, api_status = load_data()

# --- 4. 화면 구성 ---
if not df_raw.empty:
    all_k = sorted(df_raw['물품분류명'].unique())
    if 'selected_k' not in st.session_state: st.session_state.selected_k = all_k
    def toggle_k(): st.session_state.selected_k = all_k if st.session_state.master_k else []

    # 사이드바 (여기가 아까 잘렸던 부분이야!)
    with st.sidebar:
        st.header("🔍 분석 필터")
        st.checkbox("🌟 품목 분류 전체 선택", key="master_k", on_change=toggle_k, value=True)
        selected_k = st.multiselect("분석 대상 품목", options=all_k, key="selected_k")
        st.divider()
        unique_r = sorted(df_raw['계약유형'].unique())
        master_r = st.checkbox("계약유형 전체 선택", value=True)
        selected_r = [m for m in unique_r if st.checkbox(m, value=master_r, key=f"r_{m}")]
        
        st.divider()
        if "성공" in api_status: st.success("✅ 4월 실시간 연동 중")
        else: st.warning(f"⚠️ 4월 연동 실패 ({api_status})")

    df_f = df_raw[(df_raw['물품분류명'].isin(selected_k)) & (df_raw['계약유형'].isin(selected_r))]

    st.title("🏆 통합 조달 전략 분석 대시보드")
    st.caption("2026년 1분기 및 4월 실시간 실적 집계")

    if df_f.empty:
        st.info("조건에 맞는 데이터가 없습니다.")
    else:
        # [1] 상단 KPI 카드
        t_amt = df_f['금액'].sum()
        t_cnt = df_f['건수'].sum()
        avg_amt = t_amt / t_cnt if t_cnt > 0 else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("총 납품 실적", f"{int(t_amt/1000000):,} 백만 원")
        c2.metric("총 계약 건수", f"{int(t_cnt):,} 건")
        c3.metric("건당 평균 가격", f"{int(avg_amt/10000):,} 만 원")

        # [2] 월별 추이 (Area Chart)
        st.markdown("### 📈 월별 실적 트렌드")
        trend = df_f.groupby('월').agg({'금액':'sum', '건수':'sum'}).reindex(["1월", "2월", "3월", "4월"]).fillna(0).reset_index()
        fig_area = px.area(trend, x='월', y='금액', text='건수', labels={'금액':'금액(원)'}, color_discrete_sequence=['#1e3a8a'])
        fig_area.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=350)
        st.plotly_chart(fig_area, use_container_width=True)

        # [3] 점유율 분석
        col_l, col_r = st.columns(2)
        with col_l:
            target_month = st.selectbox("📅 분석 대상 월", ["전체", "1월", "2월", "3월", "4월"])
            df_pie = df_f if target_month == "전체" else df_f[df_f['월'] == target_month]
            
            st.write("**Top 10 업체별 점유율**")
            comp_data = df_pie.groupby('업체명')['금액'].sum().sort_values(ascending=False).head(10)
            if not comp_data.empty:
                st.plotly_chart(px.pie(comp_data, values=comp_data.values, names=comp_data.index, hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu), use_container_width=True)
            else: st.write("데이터 없음")
        
        with col_r:
            st.write(" ") # 줄맞춤용
            st.write(" ")
            st.write("**물품 분류별 비중**")
            cat_data = df_pie.groupby('물품분류명')['금액'].sum()
            if not cat_data.empty:
                st.plotly_chart(px.pie(cat_data, values=cat_data.values, names=cat_data.index, hole=0.4, color_discrete_sequence=px.colors.sequential.Blues_r), use_container_width=True)
            else: st.write("데이터 없음")

        # [4] 상세 데이터 표
        st.markdown("---")
        st.subheader("📑 상세 실적 및 분기 합계")
        pivot_amt = df_f.pivot_table(index='업체명', columns='월', values='금액', aggfunc='sum', fill_value=0)
        pivot_cnt = df_f.pivot_table(index='업체명', columns='월', values='건수', aggfunc='sum', fill_value=0)
        
        res = pd.DataFrame(index=pivot_amt.index)
        for m in ["1월", "2월", "3월", "4월"]:
            if m in pivot_amt.columns:
                res[f"{m}(액)"] = pivot_amt[m]
                res[f"{m}(건)"] = pivot_cnt[m]
            else:
                res[f"{m}(액)"] = 0
                res[f"{m}(건)"] = 0
        
        q_months = [m for m in ["1월", "2월", "3월"] if m in pivot_amt.columns]
        res['1분기(액)'] = pivot_amt[q_months].sum(axis=1) if q_months else 0
        res['1분기(건)'] = pivot_cnt[q_months].sum(axis=1) if q_months else 0
        res['전체 총액'] = pivot_amt.sum(axis=1)
        res['전체 총건수'] = pivot_cnt.sum(axis=1)
        
        st.dataframe(res.sort_values('전체 총액', ascending=False).style.format(lambda x: f"{int(x):,}원" if x > 1000 else f"{int(x)}건").background_gradient(cmap='YlGnBu', subset=['전체 총액']), use_container_width=True)

else:
    st.error("데이터 로드 실패. 깃허브의 CSV 파일들을 다시 확인해 주세요.")
