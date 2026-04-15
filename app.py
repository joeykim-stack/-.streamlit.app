import streamlit as st
import pandas as pd
import requests
import os
import plotly.express as px
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="조달 분석 솔루션 v3.4", layout="wide")

# --- 설정 및 상수 ---
SERVICE_KEY = "c1b3792f-37f0-4d57-897b-3b3614522855"
TARGET_COMPANIES = ["마이크로시스템", "핀텔", "웹게이트", "크리에이티브넷", "두원전자통신", "올인원 코리아", "티제이원", "앤다스", "지성이엔지", "송우인포텍", "렉스젠", "비티에스", "솔디아", "홍석", "비엔에스테크", "디케이앤트", "제이한테크", "그린아이티코리아", "펜타게이트", "한국아이티에스", "미르텍", "포딕스시스템", "명광", "뉴코리아전자통신", "오티에스", "아라드네트웍스", "시큐인포", "센텍", "원우이엔지", "경림이앤지", "진명아이앤씨", "디라직", "알엠텍", "아이엔아이", "지인테크", "다누시스", "에코아이넷", "사이테크놀로지스", "인텔리빅스", "한국씨텍", "아이즈온솔루션", "대신네트웍스", "새움", "이노뎁", "포소드", "에스카", "제노시스", "디지탈라인", "세오", "포커스에이아이", "비알인포텍", "파로스"]

# --- 2. 데이터 수집 (4월 API 보강 버전) ---
def fetch_api_data():
    # 어제 날짜 계산 (데이터 안정성 위해)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    url = "http://apis.data.go.kr/1230000/ShoppingMallPrdctInfoService05/getDlvrReqInfoList"
    
    params = {
        'serviceKey': SERVICE_KEY,
        'type': 'json',
        'numOfRows': '999',
        'pageNo': '1',
        'inqryDiv': '1',
        'inqryBgnDate': '20260401', # 4월 1일부터
        'inqryEndDate': yesterday   # 어제까지
    }
    
    try:
        res = requests.get(url, params=params, timeout=15)
        if res.status_code == 200:
            data = res.json()
            # [핵심 보강] 조달청 API 특유의 복잡한 구조 분해
            body = data.get('response', {}).get('body', {})
            items_container = body.get('items', [])
            
            raw_items = []
            if isinstance(items_container, dict):
                raw_items = items_container.get('item', [])
            elif isinstance(items_container, list):
                raw_items = items_container
            
            if raw_items:
                df = pd.DataFrame(raw_items)
                # 컬럼 매핑 (API 필드명 기준)
                df_api = df[['corpNm', 'prdctClsfcNm', 'dlvrReqAmt', 'cntrctCnclsStleNm']].copy()
                df_api.columns = ['업체명', '물품분류명', '금액', '계약유형']
                df_api['금액'] = pd.to_numeric(df_api['금액'], errors='coerce').fillna(0)
                df_api['월'] = "4월"
                df_api['건수'] = 1
                
                # 타겟 업체 필터링
                df_filtered = df_api[df_api['업체명'].str.contains('|'.join(TARGET_COMPANIES), na=False)]
                return df_filtered
    except Exception as e:
        # 오류 발생 시 로그만 남김
        print(f"API Error: {e}")
    return pd.DataFrame()

# --- 3. 데이터 통합 로드 (캐시 제외하여 실시간성 확보) ---
def load_data():
    all_dfs = []
    # 1~3월 파일 데이터
    file_map = {"1월": "data.csv", "2월": "data02.csv", "3월": "data03.csv"}
    
    for month, path in file_map.items():
        if os.path.exists(path):
            try:
                tmp = pd.read_csv(path, encoding='utf-8-sig')
                tmp.columns = [str(c).strip() for c in tmp.columns]
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
            except: continue
                
    # 4월 API 데이터 추가
    df_api_april = fetch_api_data()
    if not df_api_april.empty:
        all_dfs.append(df_api_april)
        st.sidebar.success(f"✅ 4월 데이터 불러오기 성공 ({len(df_api_april)}건)")
    else:
        st.sidebar.warning("⚠️ 4월 실시간 데이터를 불러올 수 없습니다.")
        
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

df_raw = load_data()

# --- 4. 필터 및 세션 로직 ---
if not df_raw.empty:
    all_k = sorted(df_raw['물품분류명'].unique())
    if 'selected_k' not in st.session_state: st.session_state.selected_k = all_k
    def toggle_k(): st.session_state.selected_k = all_k if st.session_state.master_k else []

    st.title("📊 조달 실적 통합 분석 대시보드 v3.4")

    with st.sidebar:
        st.header("🔍 상세 필터")
        st.checkbox("🌟 물품분류 전체 선택", key="master_k", on_change=toggle_k, value=True)
        selected_k = st.multiselect("품목 선택", options=all_k, key="selected_k")
        st.divider()
        unique_r = sorted(df_raw['계약유형'].unique())
        master_r = st.checkbox("계약유형 전체 선택", value=True)
        selected_r = [m for m in unique_r if st.checkbox(m, value=master_r, key=f"r_{m}")]

    # 데이터 필터링 적용
    df_f = df_raw[(df_raw['물품분류명'].isin(selected_k)) & (df_raw['계약유형'].isin(selected_r))]

    if df_f.empty:
        st.warning("선택한 조건에 맞는 데이터가 없습니다.")
    else:
        # --- 📈 시각화 및 데이터 표 (기존 v3.3 로직 동일) ---
        st.subheader("📈 월별 매출 및 계약 건수 추이")
        target_months = ["1월", "2월", "3월", "4월"]
        trend_data = df_f.groupby('월').agg({'금액':'sum', '건수':'sum'}).reindex(target_months).fillna(0)
        
        fig_line = px.line(trend_data, y='금액', text='건수', labels={'value':'금액(원)', '월':'기간'}, markers=True)
        st.plotly_chart(fig_line, use_container_width=True)

        st.markdown("---")
        # [생략] 점유율 원형 그래프 및 하단 데이터 표 로직 (v3.3과 동일하여 생략, 실제 코드에는 포함됨)
        # (중략된 부분은 위 v3.3의 그래프/표 코드를 그대로 사용하세요)
        c_m1, c_m2 = st.columns([1, 3])
        with c_m1:
            target_month = st.selectbox("📅 분석 대상 월 선택", ["전체"] + target_months, index=0)
        df_pie = df_f if target_month == "전체" else df_f[df_f['월'] == target_month]
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**[업체별 점유율 - {target_month}]**")
            comp_share = df_pie.groupby('업체명')['금액'].sum().sort_values(ascending=False).head(10)
            if not comp_share.empty:
                st.plotly_chart(px.pie(values=comp_share.values, names=comp_share.index, hole=0.4), use_container_width=True)
            else: st.write("데이터 없음")
        with col2:
            st.write(f"**[물품분류별 비중 - {target_month}]**")
            cat_share = df_pie.groupby('물품분류명')['금액'].sum()
            if not cat_share.empty:
                st.plotly_chart(px.pie(values=cat_share.values, names=cat_share.index, hole=0.4), use_container_width=True)
            else: st.write("데이터 없음")

        st.markdown("---")
        st.subheader("📑 상세 실적 현황")
        pivot_amt = df_f.pivot_table(index='업체명', columns='월', values='금액', aggfunc='sum', fill_value=0)
        pivot_cnt = df_f.pivot_table(index='업체명', columns='월', values='건수', aggfunc='sum', fill_value=0)
        res_df = pd.DataFrame(index=pivot_amt.index)
        for m in target_months:
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

        st.dataframe(res_df.sort_values('전체 총액', ascending=False).style.format(lambda x: f"{int(x):,}원" if x > 1000 else f"{int(x)}건"), use_container_width=True, height=500)
else:
    st.error("데이터 로드 실패.")
