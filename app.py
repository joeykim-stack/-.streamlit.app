import streamlit as st
import pandas as pd
from supabase import create_client
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="조달청 실시간 통합 분석 시스템")
st.title("🏆 조달청 실적 통합 분석 대시보드")

# 2. Supabase 연결 (실시간 데이터용)
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# 3. [핵심] 하이브리드 데이터 로드 (Master_DB.csv + Supabase)
@st.cache_data(ttl=600)
def load_hybrid_data():
    # 1) 베이스 데이터: Master_DB.csv (이게 없으면 시작부터 에러남)
    base_file = "Master_DB.csv" 
    if os.path.exists(base_file):
        base_df = pd.read_csv(base_file)
    else:
        st.error(f"❌ '{base_file}' 파일을 찾을 수 없습니다! 프로젝트 폴더에 파일을 확인하세요.")
        base_df = pd.DataFrame()

    # 2) DB 데이터: 실시간 최신 정보
    try:
        response = supabase.table("procurement_data").select("*").execute()
        db_df = pd.DataFrame(response.data)
    except Exception as e:
        st.warning(f"⚠️ DB 연결은 되었으나 실시간 데이터를 가져오지 못했습니다: {e}")
        db_df = pd.DataFrame()

    # 3) 데이터 합치기
    if not db_df.empty:
        # DB의 최신 데이터로 베이스 데이터 업데이트/병합
        combined_df = pd.concat([base_df, db_df])
        # 납품요구번호 기준 중복 제거 (DB 최신 데이터 우선)
        combined_df = combined_df.drop_duplicates(subset=['납품요구번호'], keep='last')
        return combined_df
    return base_df

# 4. 실시간 차분 수집 함수 (API)
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

# 5. 사이드바 및 UI
with st.sidebar:
    st.header("⚙️ 시스템 관리")
    if st.button("📡 최신 실적 수집"):
        with st.spinner("최신 데이터 동기화 중..."):
            count = run_delta_crawler()
            st.success(f"{count}건 신규 적재 완료!")
            st.cache_data.clear()
            st.rerun()

df = load_hybrid_data()

if not df.empty:
    st.sidebar.subheader("데이터 필터링")
    items = sorted(df['물품분류명'].dropna().unique().tolist())
    target_items = st.sidebar.multiselect("품목 선택", options=items)
    
    filtered_df = df[df['물품분류명'].isin(target_items)] if target_items else df
    
    col1, col2 = st.columns(2)
    col1.metric("총 데이터 수", f"{len(filtered_df):,} 건")
    col2.metric("총 계약금액", f"{filtered_df['전체계약금액'].sum():,.0f} 원")
    
    st.bar_chart(filtered_df.groupby('업체명')['전체계약금액'].sum().sort_values(ascending=False))
    st.dataframe(filtered_df, use_container_width=True)
else:
    st.warning("⚠️ 데이터 로드 실패. Master_DB.csv가 있는지, DB가 연결되었는지 확인하세요.")
