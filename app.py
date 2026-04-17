import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import plotly.express as px
from io import BytesIO

# --- 1. 기본 설정 ---
st.set_page_config(page_title="조달청 실적 분석 대시보드", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: 800; margin-bottom: 0.5rem; }
    .update-time { color: #6c757d; font-size: 0.9rem; margin-bottom: 2rem; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 분석 대상 업체 ---
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

# --- 3. [즉시 로드] 로컬 데이터 로직 ---
@st.cache_data(ttl=3600)
def load_historical_data():
    files = ['data_mini.csv', 'data02_mini.csv', 'data03_mini.csv', 'data04.csv']
    dfs = []
    for idx, file in enumerate(files):
        try:
            df = pd.read_csv(file)
            df.rename(columns=lambda x: x.strip(), inplace=True)
            amt_col = '납품요구금액' if '납품요구금액' in df.columns else '금액'
            temp_df = df[['업체명', '물품분류명', amt_col]].copy()
            temp_df.columns = ['업체명', '물품분류명', '금액']
            temp_df['월'] = f"{idx+1}월"
            temp_df['업체명'] = temp_df['업체명'].astype(str).str.strip()
            # 타겟 업체 필터링
            dfs.append(temp_df[temp_df['업체명'].isin(TARGET_COMPANIES)])
        except: continue
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# --- 4. [백그라운드] 실시간 API 업데이트 로직 ---
def update_realtime_data():
    if 'api_df' not in st.session_state: st.session_state.api_df = pd.DataFrame()
    if 'last_update' not in st.session_state: st.session_state.last_update = "업데이트 전"
    if 'retry_time' not in st.session_state: st.session_state.retry_time = None

    now = datetime.now()
    
    # 쿨타임 체크 (30분)
    if st.session_state.retry_time and now < st.session_state.retry_time:
        return st.session_state.api_df, f"⏳ 재시도 대기 중 (다음: {st.session_state.retry_time.strftime('%H:%M:%S')})"

    # API 호출 (성공 시에만 데이터 업데이트)
    try:
        API_KEY = "c1b379f7734c7d624ddefea07510eae71b6e12c5fb89970319d76c5ae8db5248"
        URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
        params = {'serviceKey': API_KEY, 'numOfRows': '100', 'inqryDiv': '1', 
                  'inqryBgnDate': '20260415', 'inqryEndDate': now.strftime('%Y%m%d')}
        res = requests.get(URL, params=params, timeout=5)
        
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            items = root.findall('.//item')
            new_data = []
            for item in items:
                corp = item.findtext('corpNm', '').strip()
                if corp in TARGET_COMPANIES:
                    new_data.append({'업체명': corp, '물품분류명': item.findtext('prdctClsfcNm', ''),
                                     '금액': float(item.findtext('dlvrReqAmt', 0)), '월': '4월(실시간)'})
            
            if new_data:
                st.session_state.api_df = pd.DataFrame(new_data)
                st.session_state.last_update = now.strftime('%H:%M:%S')
                return st.session_state.api_df, "🟢 실시간 업데이트 완료"
            return pd.DataFrame(), "🔵 최신 실적 없음 (동기화 대기)"
        else:
            st.session_state.retry_time = now + timedelta(minutes=30)
            return pd.DataFrame(), f"⚠️ 서버 점검 중 (500) - 30분 뒤 재시도"
    except:
        st.session_state.retry_time = now + timedelta(minutes=30)
        return pd.DataFrame(), "⚠️ 통신 일시 장애 - 30분 뒤 재시도"

# --- 5. 화면 렌더링 시작 ---
df_hist = load_historical_data()
df_api, api_msg = update_realtime_data()

# 데이터 합치기 (로컬은 무조건, API는 있으면 합침)
df_total = pd.concat([df_hist, df_api], ignore_index=True) if not df_api.empty else df_hist

st.markdown(f"<div class='main-title'>🏆 통합 조달 전략 분석 v7.2</div>", unsafe_allow_html=True)
st.markdown(f"<div class='update-time'>🕒 마지막 업데이트: {st.session_state.last_update} | 상태: {api_msg}</div>", unsafe_allow_html=True)

# --- 6. 사이드바 필터 ---
with st.sidebar:
    st.header("🔍 분석 필터")
    if not df_total.empty:
        all_items = sorted(df_total['물품분류명'].dropna().unique())
        
        # 필터 초기값 설정 (최초 실행 시 전체 선택)
        if 'filter_items' not in st.session_state:
            st.session_state.filter_items = all_items

        col1, col2 = st.columns(2)
        if col1.button("✅ 전체"): st.session_state.filter_items = all_items
        if col2.button("❌ 해제"): st.session_state.filter_items = []

        selected = st.multiselect("품목 선택", options=all_items, default=st.session_state.filter_items)
    else:
        selected = []

# --- 7. 메인 차트 및 데이터 ---
if selected:
    df_f = df_total[df_total['물품분류명'].isin(selected)]
    
    # 지표 요약
    c1, c2 = st.columns(2)
    c1.metric("💰 누적 매출액", f"{df_f['금액'].sum():,.0f}원")
    c2.metric("📝 총 계약 건수", f"{len(df_f):,}건")

    # 시각화
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("업체별 매출 순위")
        top10 = df_f.groupby('업체명')['금액'].sum().nlargest(10).reset_index()
        st.plotly_chart(px.bar(top10, x='업체명', y='금액', text_auto='.2s', color='금액'), use_container_width=True)
    with col_b:
        st.subheader("품목별 시장 점유율")
        st.plotly_chart(px.pie(df_f, names='물품분류명', values='금액', hole=0.4), use_container_width=True)

    # 상세 표
    st.subheader("📋 상세 분석 데이터")
    st.dataframe(df_f.sort_values('금액', ascending=False), use_container_width=True)
else:
    st.info("왼쪽 필터에서 품목을 선택해주세요. (데이터가 로드되지 않았다면 CSV 파일을 확인해주세요)")

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim. Data from Public Data Portal.</center>", unsafe_allow_html=True)
