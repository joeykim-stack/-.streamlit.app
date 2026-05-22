import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET

# 1. Supabase 연결 설정
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

st.title("🏆 조달청 54개사 실시간 DB 대시보드")

# 2. 조달청 데이터 수집 및 DB 저장 로직
def run_and_save():
    API_KEY = "df5a1c97ab56593d5e99889ae1c030bfe0b5e9d924ffba9bae3712c8bb1ad75c"
    # 수집 기간 (1분기 전체)
    bgn_date = "20260101"
    end_date = "20260331"
    
    url = f"http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList?serviceKey={API_KEY}&numOfRows=500&pageNo=1&inqryDiv=1&inqryBgnDate={bgn_date}&inqryEndDate={end_date}"
    
    try:
        res = requests.get(url, verify=False)
        root = ET.fromstring(res.content)
        items = root.findall('.//item')
        
        if not items: return "🔵 수집된 데이터가 없습니다."
        
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
        
        # Supabase 저장 (납품요구번호 기준 중복 방지)
        supabase.table("procurement_data").upsert(data_list, on_conflict="납품요구번호").execute()
        
        return f"🎉 총 {len(data_list)}건의 데이터를 DB에 안전하게 적재 완료!"
    except Exception as e:
        return f"🚨 에러: {str(e)}"

# 3. 화면 UI
if st.button("📡 [실행] 조달청 데이터 수집 및 저장"):
    with st.spinner("조달청 API 조회 및 DB 저장 중..."):
        msg = run_and_save()
        st.success(msg)
        st.cache_data.clear()
        st.rerun()

# 4. 저장된 데이터 불러오기
@st.cache_data(ttl=60)
def load_db_data():
    response = supabase.table("procurement_data").select("*").execute()
    return pd.DataFrame(response.data)

df = load_db_data()
st.metric("DB 적재 완료 건수", f"{len(df):,} 건")
st.dataframe(df.tail(10))
