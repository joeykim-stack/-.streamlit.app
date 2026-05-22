import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [1. 연결 설정] ---
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

st.set_page_config(layout="wide", page_title="조달청 실시간 DB 대시보드")
st.title("🏆 조달청 54개사 실시간 DB 분석")

# --- [2. 데이터 수집 및 DB 저장 로직 (Upsert)] ---
def run_and_save():
    API_KEY = "df5a1c97ab56593d5e99889ae1c030bfe0b5e9d924ffba9bae3712c8bb1ad75c"
    # 최근 3일 치 조회 (혹시 모를 누락 방지)
    bgn_date = (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")
    
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
                "업체명": "확인필요", # 추후 맵핑 로직 추가 가능
                "물품분류명": item.findtext('prdctClsfcNm'),
                "납품요구번호": item.findtext('dlvrReqNo'),
                "일자": item.findtext('dlvrReqRcptDate'),
                "전체계약금액": float(item.findtext('dlvrReqAmt') or 0)
            })
            
        df_new = pd.DataFrame(data_list)
        
        # [핵심] Supabase에 저장 (이미 있으면 덮어쓰고, 없으면 새로 넣음 = Upsert)
        # on_conflict="납품요구번호"로 설정하면 중복 데이터를 알아서 걸러줘!
        supabase.table("procurement_data").upsert(data_list, on_conflict="납품요구번호").execute()
        
        return f"🎉 총 {len(df_new)}건의 데이터를 DB에 안전하게 저장했습니다!"
    except Exception as e:
        return f"🚨 수집 중 에러 발생: {e}"

# --- [3. 메인 화면] ---
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("📡 [실행] 오늘자 실적 수집/업데이트"):
        with st.spinner("조달청 서버와 통신 중..."):
            msg = run_and_save()
            st.success(msg)
            st.cache_data.clear() # 캐시 비우기
            st.rerun()

# --- [4. 데이터 읽기] ---
@st.cache_data(ttl=60)
def load_data():
    # 데이터베이스에서 모든 내용 가져오기
    response = supabase.table("procurement_data").select("*").execute()
    return pd.DataFrame(response.data)

df = load_data()

if not df.empty:
    st.metric("DB 전체 데이터 건수", f"{len(df):,} 건")
    st.dataframe(df.tail(10)) # 마지막 10건 확인
else:
    st.info("데이터가 없습니다. [실행] 버튼을 눌러보세요!")
