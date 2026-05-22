import streamlit as st
import pandas as pd
from supabase import create_client
import requests
import xml.etree.ElementTree as ET

st.set_page_config(layout="wide", page_title="진단 및 데이터 수집기")
st.title("🔍 조달청 & DB 연결 진단기")

# 1. Supabase 연결
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# 2. 진단 버튼
if st.button("🚨 진단 실행 (API + DB 테스트)"):
    # Step 1: 조달청 API 호출 테스트
    st.write("Step 1: 조달청 API 호출 중...")
    try:
        API_KEY = st.secrets["API_KEY"]
        url = f"http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList?serviceKey={API_KEY}&numOfRows=1&pageNo=1&inqryDiv=1&inqryBgnDate=20260101&inqryEndDate=20260102"
        res = requests.get(url, verify=False)
        if res.status_code == 200:
            st.success("✅ 조달청 서버 통신 성공!")
        else:
            st.error(f"❌ 조달청 서버 에러 (코드: {res.status_code})")
    except Exception as e:
        st.error(f"❌ 조달청 API 연결 실패: {e}")

    # Step 2: Supabase DB 쓰기 테스트
    st.write("Step 2: DB 저장 테스트...")
    try:
        test_data = {"사업자등록번호": "000", "납품요구번호": "TEST_ID_12345", "업체명": "테스트"}
        supabase.table("procurement_data").upsert(test_data, on_conflict="납품요구번호").execute()
        st.success("✅ DB 연결 및 저장 성공!")
    except Exception as e:
        st.error(f"❌ DB 저장 실패: {e}")

# 3. 데이터 확인
st.markdown("---")
st.subheader("현재 DB에 저장된 데이터 확인")
try:
    response = supabase.table("procurement_data").select("*").limit(5).execute()
    st.dataframe(pd.DataFrame(response.data))
except Exception as e:
    st.error("데이터를 불러올 수 없습니다.")
