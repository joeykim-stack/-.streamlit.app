import streamlit as st
import pandas as pd
from supabase import create_client

# --- 1. 페이지 기본 설정 ---
st.set_page_config(layout="wide", page_title="조달청 실적 분석 대시보드")
st.title("🏆 조달청 54개사 실적 분석 대시보드")
st.markdown("---")

# --- 2. Supabase 연결 ---
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

# --- 3. 데이터 로드 ---
@st.cache_data(ttl=600)
def load_data():
    # 이제 파일 대신 DB에서 바로 긁어옵니다.
    response = supabase.table("procurement_data").select("*").execute()
    return pd.DataFrame(response.data)

df = load_data()

# --- 4. 대시보드 레이아웃 ---
if not df.empty:
    # 상단 요약 지표
    col1, col2, col3 = st.columns(3)
    col1.metric("총 등록 데이터", f"{len(df):,} 건")
    col2.metric("전체 계약금액 합계", f"{df['전체계약금액'].sum():,.0f} 원")
    col3.metric("대상 업체 수", f"{df['사업자등록번호'].nunique()} 개사")
    
    st.markdown("---")
    
    # 탭 구성 (새로운 화면 구성)
    tab1, tab2 = st.tabs(["📊 실적 상세 분석", "🏢 업체별 랭킹"])
    
    with tab1:
        st.subheader("📋 데이터 상세 내역")
        st.dataframe(df.sort_values(by='일자', ascending=False), use_container_width=True)
        
        # 엑셀 다운로드 (예전 디자인 계승)
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 데이터 엑셀(CSV) 다운로드", csv, "조달청_실적_데이터.csv", "text/csv")
        
    with tab2:
        st.subheader("🏢 업체별 납품요구액 랭킹")
        ranking = df.groupby('사업자등록번호')['전체계약금액'].sum().reset_index()
        st.bar_chart(ranking.set_index('사업자등록번호'))

else:
    st.warning("⚠️ DB에 저장된 데이터가 없습니다. 수집기를 실행해주세요.")

# 하단 카피라이트 (예전 디자인 계승)
st.sidebar.markdown("---")
st.sidebar.markdown("© 2026 조달청 실적 통합 관리 시스템")
