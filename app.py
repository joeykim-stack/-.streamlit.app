import streamlit as st
import pandas as pd
from supabase import create_client
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="조달청 실시간 통합 분석 시스템")
st.title("🏆 조달청 54개사 실적 통합 분석 대시보드")

# 2. Supabase 클라이언트 연결
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

# 3. DB에서 데이터 불러오기 (캐시 처리)
@st.cache_data(ttl=600)
def load_db_data():
    try:
        response = supabase.table("procurement_data").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"DB 로드 실패: {e}")
        return pd.DataFrame()

# 4. 데이터 수집 및 DB 업로드 (수동 트리거)
def run_crawler():
    API_KEY = st.secrets["API_KEY"] # Streamlit Secrets에 저장된 키 사용
    # 예시 기간: 최근 3일치 차분 업데이트
    bgn_date = (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")
    url = f"http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList?serviceKey={API_KEY}&numOfRows=500&pageNo=1&inqryDiv=1&inqryBgnDate={bgn_date}&inqryEndDate={end_date}"
    
    try:
        res = requests.get(url, verify=False)
        items = ET.fromstring(res.content).findall('.//item')
        
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
        
        # 중복 방지 저장 (upsert)
        if data_list:
            supabase.table("procurement_data").upsert(data_list, on_conflict="납품요구번호").execute()
        return len(data_list)
    except Exception as e:
        return f"🚨 에러: {e}"

# 5. UI 대시보드 화면
df = load_db_data()

with st.sidebar:
    st.header("⚙️ 시스템 제어")
    if st.button("📡 최신 데이터 수집 및 업데이트"):
        with st.spinner("조달청 서버와 통신 중..."):
            count = run_crawler()
            st.success(f"{count}건 반영 완료!")
            st.cache_data.clear() # 캐시 삭제 후 리런
            st.rerun()

if not df.empty:
    # 지표 분석
    col1, col2, col3 = st.columns(3)
    col1.metric("DB 전체 건수", f"{len(df):,} 건")
    col2.metric("총 계약금액 합계", f"{df['전체계약금액'].sum():,.0f} 원")
    col3.metric("대상 업체 수", f"{df['사업자등록번호'].nunique()} 개사")
    
    st.markdown("---")
    
    # 탭 시각화
    tab1, tab2 = st.tabs(["📊 상세 내역", "🏢 업체별 실적 랭킹"])
    with tab1:
        st.dataframe(df.sort_values(by='일자', ascending=False), use_container_width=True)
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 데이터 다운로드(CSV)", csv, "조달데이터.csv", "text/csv")
    with tab2:
        ranking = df.groupby('사업자등록번호')['전체계약금액'].sum().sort_values(ascending=False).reset_index()
        st.bar_chart(ranking.set_index('사업자등록번호'))
else:
    st.warning("데이터가 없습니다. 업데이트 버튼을 눌러주세요.")
