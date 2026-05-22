import streamlit as st
import pandas as pd
from supabase import create_client

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="조달청 실시간 통합 대시보드")
st.title("🏆 조달청 54개사 통합 실적 대시보드")
st.markdown("---")

# 2. Supabase 연결 (이제 DB 금고를 엽니다)
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# 3. 데이터 로드 (이제 파일은 안녕!)
@st.cache_data(ttl=60)
def load_db_data():
    response = supabase.table("procurement_data").select("*").execute()
    return pd.DataFrame(response.data)

df = load_db_data()

if not df.empty:
    # 상단 요약 (가독성 향상)
    col1, col2, col3 = st.columns(3)
    col1.metric("총 등록 데이터", f"{len(df):,} 건")
    col2.metric("전체 계약금액 합계", f"{df['전체계약금액'].sum():,.0f} 원")
    col3.metric("대상 업체 수", f"{df['사업자등록번호'].nunique()} 개사")
    
    st.markdown("---")
    
    # 탭 구성 (분석/랭킹)
    tab1, tab2 = st.tabs(["📊 실적 상세 분석", "🏢 업체별 랭킹 분석"])
    
    with tab1:
        st.subheader("📋 전체 데이터 내역")
        st.dataframe(df.sort_values(by='일자', ascending=False), use_container_width=True)
        
    with tab2:
        st.subheader("🏢 업체별 납품요구액 랭킹")
        ranking = df.groupby('사업자등록번호')['전체계약금액'].sum().sort_values(ascending=False).reset_index()
        st.bar_chart(ranking.set_index('사업자등록번호'))
else:
    st.info("데이터베이스에 데이터가 없습니다.")

st.sidebar.markdown("---")
st.sidebar.markdown("✅ **상태:** 데이터베이스 연동 완료")
