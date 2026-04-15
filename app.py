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
                c_item = next((
