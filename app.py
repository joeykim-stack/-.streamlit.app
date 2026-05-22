import streamlit as st
import pandas as pd
from supabase import create_client
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="조달청 실시간 통합 분석 시스템")
st.title("🏆 조달청 실적 통합 분석 대시보드")

# 2. Supabase 연결
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# 3. 데이터 로드 (캐시 10분)
@st.cache_data(ttl=600)
def load_db_data():
    try:
        response = supabase.table("procurement_data").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"DB 로드 실패: {e}")
        return pd.DataFrame()

# 4. 데이터 수집 함수 (필터링 제거)
def run_crawler():
    API_KEY = st.secrets["API_KEY"]
    bgn_date = (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")
    url = f"http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList?serviceKey={API_KEY}&numOfRows=10&pageNo=1&inqryDiv=1&inqryBgnDate={bgn_date}&inqryEndDate={end_date}"
    
    try:
        res = requests.get(url, verify=False)
        root = ET.fromstring(res.content)
        items = root.findall('.//item')
        
        # 디버깅용 샘플 출력
        if items:
            st.write("### 🚨 API 원본 데이터 필드 확인")
            sample = {child.tag: child.text for child in items[0]}
            st.json(sample)
        
        data_list = []
        for item in items:
            data_list.append({
                "사업자등록번호": item.findtext('bizrno'),
                "업체명": item.findtext('cntrctrNm') or "알수없음",
                "물품분류명": item.findtext('prdctClsfcNm'),
                "납품요구번호": item.findtext('dlvrReqNo'),
                "일자": item.findtext('dlvrReqRcptDate'),
                "전체계약금액": float(item.findtext('dlvrReqAmt') or 0)
            })
        
        if data_list:
            supabase.table("procurement_data").upsert(data_list, on_conflict="납품요구번호").execute()
        return len(data_list)
    except Exception as e:
        st.error(f"수집 에러: {e}")
        return -1

# 5. UI 화면
if st.sidebar.button("📡 최신 데이터 수집"):
    count = run_crawler()
    if count >= 0:
        st.success(f"{count}건 반영 완료!")
        st.rerun()

df = load_db_data()
if not df.empty:
    st.dataframe(df)
else:
    st.warning("데이터가 없습니다.")
