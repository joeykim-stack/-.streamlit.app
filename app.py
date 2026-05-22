import streamlit as st
import pandas as pd
from supabase import create_client
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os

st.set_page_config(layout="wide", page_title="조달청 실시간 통합 분석 시스템")
st.title("🏆 조달청 하이브리드 실적 통합 대시보드")

# 1. Supabase 연결
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# 2. [핵심] 하이브리드 데이터 로드 (로컬 파일 + 실시간 DB)
@st.cache_data(ttl=600)
def load_hybrid_data():
    # 1) 베이스 데이터 로드 (이미 다운받은 과거 데이터)
    base_file = "raw.csv" # 👈 여기에 실제 가지고 있는 파일 이름을 넣어주세요!
    if os.path.exists(base_file):
        base_df = pd.read_csv(base_file)
    else:
        base_df = pd.DataFrame()

    # 2) DB 데이터 로드 (API로 수집된 최신 실시간 데이터)
    try:
        response = supabase.table("procurement_data").select("*").execute()
        db_df = pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"DB 로드 에러: {e}")
        db_df = pd.DataFrame()

    # 3) 두 데이터 합치기 (병합 후 중복 제거)
    if not base_df.empty and not db_df.empty:
        # DB에 있는 최신 데이터가 우선순위를 갖도록 덮어쓰기
        combined_df = pd.concat([base_df, db_df])
        combined_df = combined_df.drop_duplicates(subset=['납품요구번호'], keep='last')
        return combined_df
    elif not base_df.empty:
        return base_df
    elif not db_df.empty:
        return db_df
    else:
        return pd.DataFrame()

# 3. 최신 데이터 수집 함수 (최근 3일치만 빠르게 수집)
def run_delta_crawler():
    API_KEY = st.secrets["API_KEY"]
    bgn_date = (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")
    url = f"http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList?serviceKey={API_KEY}&numOfRows=100&pageNo=1&inqryDiv=1&inqryBgnDate={bgn_date}&inqryEndDate={end_date}"
    
    try:
        res = requests.get(url, verify=False)
        items = ET.fromstring(res.content).findall('.//item')
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
        return -1

# 4. 사이드바 제어
with st.sidebar:
    st.header("⚙️ 데이터 동기화")
    if st.button("📡 최근 3일치 실시간 업데이트"):
        with st.spinner("최신 데이터를 DB에 가져오는 중..."):
            count = run_delta_crawler()
            if count >= 0:
                st.success(f"{count}건 신규 적재 완료!")
                st.cache_data.clear()
                st.rerun()

# 5. UI 화면 출력
df = load_hybrid_data()

if not df.empty:
    st.sidebar.subheader("필터링 설정")
    target_items = st.sidebar.multiselect("품목 선택 (예: 영상감시장치)", options=df['물품분류명'].unique())
    filtered_df = df[df['물품분류명'].isin(target_items)] if target_items else df

    col1, col2 = st.columns(2)
    col1.metric("총 데이터 건수", f"{len(filtered_df):,} 건")
    col2.metric("총 계약금액 합계", f"{filtered_df['전체계약금액'].sum():,.0f} 원")

    st.bar_chart(filtered_df.groupby('업체명')['전체계약금액'].sum().sort_values(ascending=False))
    st.dataframe(filtered_df, use_container_width=True)
else:
    st.warning("⚠️ 베이스 파일(raw.csv)을 찾을 수 없고, DB도 비어있습니다.")
