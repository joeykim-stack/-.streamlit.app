import streamlit as st
import pandas as pd
import requests
import os
import plotly.express as px
import plotly.graph_objects as go
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

# --- 2. 4월 API 수집 (진단 및 보강) ---
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

# --- 3. 데이터 로드 (1~3월 파일 인식 보강) ---
def load_data():
    all_dfs = []
    file_map = {"1월": "data.csv", "2월": "data02.csv", "3월": "data03.csv"}
    for month, path in file_map.items():
        if os.path.exists(path):
            try:
                # 중찬이가 압축한 UTF-8 형식으로 읽기
                df = pd.read_csv(path, encoding='utf-8-sig')
                df.columns = [str(c).strip() for c in df.columns]
                
                # 유연한 컬럼 찾기
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

# --- 4. 화면 구성 ---
if not df_raw.empty:
    all_k = sorted(df_raw['물품분류명'].unique())
    if 'selected_k' not in st.session_state: st.session_state.selected_k = all_k
    def toggle_k(): st.session_state.selected_k = all_k if st.session_state.master_k else []

    # 사이드바
    with st.sidebar:
        st.image("https://www.pps.go.kr/images/common/logo.png", width=150) # 조달청 로고 예시
        st.header("🔍 분석 필터")
        st.checkbox("🌟 품목 분류 전체 선택", key="master_k", on_change=toggle_k, value=True)
        selected_k = st.
