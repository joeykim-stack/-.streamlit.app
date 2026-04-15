import streamlit as st
import pandas as pd
import requests
import os
import plotly.express as px
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="조달 분석 솔루션 v3.3", layout="wide")

# --- 설정 및 상수 ---
SERVICE_KEY = "c1b3792f-37f0-4d57-897b-3b3614522855"
TARGET_COMPANIES = ["마이크로시스템", "핀텔", "웹게이트", "크리에이티브넷", "두원전자통신", "올인원 코리아", "티제이원", "앤다스", "지성이엔지", "송우인포텍", "렉스젠", "비티에스", "솔디아", "홍석", "비엔에스테크", "디케이앤트", "제이한테크", "그린아이티코리아", "펜타게이트", "한국아이티에스", "미르텍", "포딕스시스템", "명광", "뉴코리아전자통신", "오티에스", "아라드네트웍스", "시큐인포", "센텍", "원우이엔지", "경림이앤지", "진명아이앤씨", "디라직", "알엠텍", "아이엔아이", "지인테크", "다누시스", "에코아이넷", "사이테크놀로지스", "인텔리빅스", "한국씨텍", "아이즈온솔루션", "대신네트웍스", "새움", "이노뎁", "포소드", "에스카", "제노시스", "디지탈라인", "세오", "포커스에이아이", "비알인포텍", "파로스"]

# --- 2. 데이터 수집 (4월 API) ---
def fetch_api_data():
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    url = "http://apis.data.go.kr/1230000/ShoppingMallPrdctInfoService05/getDlvrReqInfoList"
    params = {'serviceKey': SERVICE_KEY, 'type': 'json', 'numOfRows': '999', 'pageNo': '1', 'inqryDiv': '1', 'inqryBgnDate': '20260401', 'inqryEndDate': yesterday}
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            items = res.json().get('response', {}).get('body', {}).get('items', [])
            if items:
                df = pd.DataFrame(items)
                df_api = df[['corpNm', 'prdctClsfcNm', 'dlvrReqAmt', 'cntrctCnclsStleNm']].copy()
                df_api.columns = ['업체명', '물품분류명', '금액', '계약유형']
                df_api['금액'] = pd.to_numeric(df_api['금액'], errors='coerce').fillna(0)
                df_api['월'] = "4월"
                df_api['건수'] = 1
                return df_api[df_api['업체명'].str.contains('|'.join(TARGET_COMPANIES), na=False)]
    except: pass
    return pd.DataFrame()

# --- 3. 데이터 통합 로드 (중찬이가 수정한 파일명 data.csv에 맞춤) ---
@st.cache_data(ttl=600)
def load_data():
    all_dfs = []
    # 중찬이가 깃허브에 올린 파일명 그대로 사용
    file_map = {"1월": "data.csv", "2월": "data02.csv", "3월": "data03.csv"}
    
    for month, path in file_map.items():
        if os.path.exists(path):
            try:
                # 🚨 다이어트된 파일은 이제 표준 CSV(쉼표 구분, utf-8)이므로 일반적인 방식으로 읽음
                tmp = pd.read_csv(path, encoding='utf-8-sig')
                
                # 컬럼명에 혹시 모를 공백 제거
                tmp.columns = [str(c).strip() for c in tmp.columns]
                
                # 필요한 정보만 매핑
                c_corp = next((c for c in tmp.columns if '업체명' in c), None)
                c_item = next((c for c in tmp.columns if '물품분류명' in c), None)
                c_method = next((c for c in tmp.columns if '계약유형' in c or '계약체결형태' in c), None)
                c_amt = next((c for c in tmp.columns if '금액' in c or '납품금액' in c), None)
                
                if all([c_corp, c_item, c_method, c_amt]):
                    df_sub = pd.DataFrame()
                    df_sub['업체명'] = tmp[c_corp].astype(str).str.strip()
                    df_sub['물품분류명'] = tmp[c_item].astype(str).str.strip()
                    df_sub['계약유형'] = tmp[c_method].astype(str).str.strip()
                    df_sub['금액'] = pd.to_numeric(tmp[c_amt].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                    df_sub['월'] = month
                    df_sub['건수'] = 1
                    all_dfs.append(df_sub)
            except Exception as e:
                st.error(f"{month} 파일 읽기 실패: {e}")
                continue
                
    df_api = fetch_api_data()
    if not df_api.empty: all_dfs.append(df_api)
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

df_raw = load_data()

# --- 4. 필터 및 세션 로직 ---
if not df_raw.empty:
    all_k = sorted(df_raw['물품분류명'].unique())
    if 'selected_k' not in st.session_state: st.session_state.selected_k = all_k
    def toggle_k(): st.session_state.selected_k = all_k if st.session_state.master_k else []

    st.title("📊 조달 실적 통합 정밀 분석 대시보드 v3.3")

    with st.sidebar:
        st.header("🔍 상세 필터")
        st.checkbox("🌟 물품분류 전체 선택", key="master_k", on_change=toggle_k, value=True)
        selected_k = st.multiselect("품목 선택", options=all_k, key="selected_k")
        st.divider()
        unique_r = sorted(df_raw['계약유형'].unique())
        master_r = st.checkbox("계약유형 전체 선택", value=True)
        selected_r = [m for m in unique_r if st.checkbox(m, value=master_r, key=f"r_{m}")]

    df_f = df_raw[(df_raw['물품분류명'].isin(selected_k)) & (df_raw['계약유형'].isin(selected_r))]

    if df_f.empty:
        st.warning("선택한 조건에 맞는 데이터가 없습니다.")
    else:
        # --- 📈 1구역: 월별 추이 (꺾은선) ---
        st.subheader("📈 월별 매출 및 계약 건수 추이")
        trend = df_f.groupby('월').agg({'금액':'sum', '건수':'sum'}).reindex(["1월", "2월", "3월", "4월"]).fillna(0)
        fig_line = px.line(trend, y='금액', text='건수', labels={'value':'금액(원)', '월':'기간'}, markers=True)
        st.plotly_chart(fig_line, use_container_width=True)

        # --- 📊 2구역: 점유율 분석 (Pie Charts) ---
        st.markdown("---")
        c_m1, c_m2 = st.columns([1, 3])
        with c_m1:
            target_month = st.selectbox("📅 분석 대상 월 선택", ["전체", "1월", "2월", "3월", "4월"], index=0)
        
        df_pie = df_f if target_month == "전체" else df_f[df_f['월'] == target_month]
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**[업체별 점유율 - {target_month}]**")
            comp_share = df_pie.groupby('업체명')['금액'].sum().sort_values(ascending=False).head(10)
            fig_pie1 = px.pie(values=comp_share.values, names=comp_share.index, hole=0.4)
            st.plotly_chart(fig_pie1, use_container_width=True)
        with col2:
            st.write(f"**[물품분류별 비중 - {target_month}]**")
            cat_share = df_pie.groupby('물품분류명')['금액'].sum()
            fig_pie2 = px.pie(values=cat_share.values, names=cat_share.index, hole=0.4)
            st.plotly_chart(fig_pie2, use_container_width=True)

        # --- 📑 3구역: 상세 데이터 및 분기 합계 ---
        st.markdown("---")
        st.subheader("📑 월별/분기별 상세 실적 (금액 및 건수)")
        
        pivot_amt = df_f.pivot_table(index='업체명', columns='월', values='금액', aggfunc='sum', fill_value=0)
        pivot_cnt = df_f.pivot_table(index='업체명', columns='월', values='건수', aggfunc='sum', fill_value=0)

        res_df = pd.DataFrame(index=pivot_amt.index)
        for m in ["1월", "2월", "3월", "4월"]:
            if m in pivot_amt.columns:
                res_df[f"{m}(액)"] = pivot_amt[m]
                res_df[f"{m}(건)"] = pivot_cnt[m]
            else:
                res_df[f"{m}(액)"] = 0
                res_df[f"{m}(건)"] = 0
        
        q1_months = [m for m in ["1월", "2월", "3월"] if m in pivot_amt.columns]
        res_df['1분기 합계(액)'] = pivot_amt[q1_months].sum(axis=1) if q1_months else 0
        res_df['1분기 합계(건)'] = pivot_cnt[q1_months].sum(axis=1) if q1_months else 0
        res_df['전체 총액'] = pivot_amt.sum(axis=1)
        res_df['전체 건수'] = pivot_cnt.sum(axis=1)

        st.dataframe(
            res_df.sort_values('전체 총액', ascending=False)
            .style.format(lambda x: f"{int(x):,}원" if x > 1000 else f"{int(x)}건"),
            use_container_width=True, height=500
        )
else:
    st.error("데이터를 로드할 수 없습니다. 깃허브에 data.csv, data02.csv, data03.csv 파일이 있는지 확인해 주세요.")
