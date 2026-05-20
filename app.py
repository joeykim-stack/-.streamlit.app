import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET
import urllib3
import time
import os

# SSL 경고 숨기기
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [절대 경로 설정] 파일 위치 고정 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_DB_FILE = os.path.join(BASE_DIR, "Master_DB.csv")
TARGET_FILE = os.path.join(BASE_DIR, "target_companies.csv")

# --- [내장형 수집 봇 함수] ---
def run_daily_crawler():
    API_KEY = "df5a1c97ab56593d5e99889ae1c030bfe0b5e9d924ffba9bae3712c8bb1ad75c" 
    
    today = datetime.now()
    bgn_date = (today - timedelta(days=2)).strftime("%Y%m%d")
    end_date = (today - timedelta(days=1)).strftime("%Y%m%d")

    # 1. 타겟 업체 로드
    try:
        raw_target = pd.read_csv(TARGET_FILE, encoding='utf-8-sig', header=None, dtype=str)
        header_idx = None
        for idx, row in raw_target.iterrows():
            if row.astype(str).str.contains('사업자등록번호').any():
                header_idx = idx; break
        columns = [str(c).strip() for c in raw_target.iloc[header_idx].tolist()]
        df_target = raw_target.iloc[header_idx+1:].copy()
        df_target.columns = columns
        
        biz_col = [c for c in df_target.columns if '사업자등록번호' in c][0]
        name_col = [c for c in df_target.columns if '계약업체' in c or '업체명' in c][0]
        
        df_target[biz_col] = df_target[biz_col].fillna('').str.replace('-', '', regex=False).str.replace(r'\.0$', '', regex=True).str.strip()
        TARGET_MAP = dict(zip(df_target[biz_col], df_target[name_col]))
    except Exception as e:
        return f"🚨 타겟 업체 파일 로드 에러: {e}"

    # 2. 조달청 API 호출
    BASE_URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
    headers = {'User-Agent': 'Mozilla/5.0'}
    all_new_data = []

    page = 1
    while True:
        url = f"{BASE_URL}?serviceKey={API_KEY}&numOfRows=500&pageNo={page}&inqryDiv=1&inqryBgnDate={bgn_date}&inqryEndDate={end_date}"
        try:
            res = requests.get(url, headers=headers, timeout=15, verify=False)
            if res.status_code != 200: break
            root = ET.fromstring(res.content)
            if root.findtext('.//resultCode') not in ['00', '0']: break
            total = int(root.findtext('.//totalCount') or 0)
            if total == 0: break
            
            items = root.findall('.//item')
            for item in items:
                all_new_data.append({child.tag: child.text for child in item})
            if page * 500 >= total: break
            page += 1
        except: break

    # 3. 데이터 정제 및 DB 업데이트
    if all_new_data:
        df_api = pd.DataFrame(all_new_data)
        if 'bizrno' in df_api.columns:
            df_api['bizrno'] = df_api['bizrno'].str.replace('-', '', regex=False)
            df_new = df_api[df_api['bizrno'].isin(TARGET_MAP.keys())].copy()
            
            if not df_new.empty:
                df_new = df_new.rename(columns={'bizrno': '사업자등록번호', 'prdctClsfcNm': '물품분류명', 'dlvrReqNo': '납품요구번호', 'dlvrReqRcptDate': '일자', 'dlvrReqAmt': '전체계약금액'})
                df_new['업체명'] = df_new['사업자등록번호'].map(TARGET_MAP)
                df_new['전체계약금액'] = pd.to_numeric(df_new['전체계약금액'], errors='coerce').fillna(0)
                df_new['일자'] = df_new['일자'].astype(str).str[:8]
                df_new['월'] = df_new['일자'].str[4:6].apply(lambda x: f"{int(x)}월" if x.isdigit() else "미상")

                df_master = pd.read_csv(MASTER_DB_FILE, encoding='utf-8-sig', dtype=str)
                df_master['전체계약금액'] = pd.to_numeric(df_master['전체계약금액'], errors='coerce')
                df_combined = pd.concat([df_master, df_new], ignore_index=True)
                df_combined = df_combined.drop_duplicates(subset=['납품요구번호', '물품분류명', '전체계약금액'], keep='last')
                df_combined.to_csv(MASTER_DB_FILE, index=False, encoding='utf-8-sig')
                return f"🎉 업데이트 완료! ({len(df_new)}건 추가)"
            return "🔵 신규 실적이 없습니다."
    return "🔵 업데이트할 데이터가 없습니다."

# --- [Streamlit 대시보드 UI] ---
st.set_page_config(layout="wide")
st.title("🏆 조달청 54개사 전수 실적 분석")

with st.sidebar:
    if st.button("📡 [실행] 오늘자 신규 실적 수집"):
        with st.spinner("수집 중..."):
            msg = run_daily_crawler()
            st.success(msg)
            st.cache_data.clear()
            st.rerun()

# 데이터 로드
@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv(MASTER_DB_FILE, encoding='utf-8-sig', dtype={'사업자등록번호': str})
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    return df

df = load_data()
st.metric("총 데이터 건수", f"{len(df):,} 건")
st.dataframe(df.tail(10)) # 마지막 10건만 미리보기
