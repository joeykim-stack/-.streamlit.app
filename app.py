import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET

# --- [1. 연결 설정] ---
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

st.set_page_config(layout="wide", page_title="조달청 실시간 DB 대시보드")
st.title("🏆 조달청 54개사 통합 실적 보드")

# --- [2. 데이터 수집 봇] ---
def run_crawler():
    API_KEY = "df5a1c97ab56593d5e99889ae1c030bfe0b5e9d924ffba9bae3712c8bb1ad75c"
    # 수집 기간 설정 (오늘부터 과거 3일치 차분 업데이트)
    bgn_date = (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")
    
    url = f"http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList?serviceKey={API_KEY}&numOfRows=500&pageNo=1&inqryDiv=1&inqryBgnDate={bgn_date}&inqryEndDate={end_date}"
    
    try:
        res = requests.get(url, verify=False)
        root = ET.fromstring(res.content)
        items = root.findall('.//item')
        
        if not items: return 0
        
        data_list = []
        for item in items:
            data_list.append({
                "사업자등록번호": item.findtext('bizrno'),
                "업체명": "확인필요",
                "물품분류명": item.findtext('prdctClsfcNm'),
                "납품요구번호": item.findtext('dlvrReqNo'),
                "일자": item.findtext('dlvrReqRcptDate'),
                "전체계약금액": float(item.findtext('dlvrReqAmt') or 0)
            })
        
        # 중복 방지를 위한 UPSERT (납품요구번호가 같으면 덮어쓰고, 없으면 넣음)
        supabase.table("procurement_data").upsert(data_list, on_conflict="납품요구번호").execute()
        return len(data_list)
    except:
        return -1

# --- [3. UI 및 대시보드] ---
if st.button("📡 최신 실적 새로고침"):
    with st.spinner("수집 중..."):
        count = run_crawler()
        if count >= 0:
            st.success(f"{count}건의 실적이 성공적으로 반영되었습니다!")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("수집 실패: 조달청 서버 부하")

# 데이터 불러오기
@st.cache_data(ttl=600)
def load_db_data():
    # 랭킹 계산을 위해 전체 데이터 불러오기
    response = supabase.table("procurement_data").select("*").execute()
    return pd.DataFrame(response.data)

df = load_db_data()
st.metric("DB 전체 데이터 건수", f"{len(df):,} 건")
st.dataframe(df.sort_values(by='일자', ascending=False))
