import streamlit as st
import pandas as pd
from supabase import create_client
import os

# 페이지 설정
st.set_page_config(layout="wide", page_title="조달청 실적 통합 분석 대시보드")
st.title("🏆 조달청 실적 상세 분석: 월/분기별 랭킹")

# 1. Supabase 연결
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# 2. 하이브리드 데이터 로드 (Master_DB.csv + DB)
@st.cache_data(ttl=600)
def load_analysis_data():
    base_file = "Master_DB.csv"
    base_df = pd.read_csv(base_file) if os.path.exists(base_file) else pd.DataFrame()
    
    try:
        response = supabase.table("procurement_data").select("*").execute()
        db_df = pd.DataFrame(response.data)
    except:
        db_df = pd.DataFrame()
    
    df = pd.concat([base_df, db_df]).drop_duplicates(subset=['납품요구번호'], keep='last')
    
    # 날짜 처리
    df['일자'] = pd.to_datetime(df['일자'], format='%Y%m%d', errors='coerce')
    df['월'] = df['일자'].dt.to_period('M')
    df['분기'] = df['일자'].dt.to_period('Q')
    return df

df = load_analysis_data()

if not df.empty:
    # 3. 데이터 구조화 (피벗 테이블 생성)
    # 업체별 월별 합계
    monthly_pivot = df.pivot_table(index='업체명', columns='월', values='전체계약금액', aggfunc='sum', fill_value=0)
    # 업체별 분기별 합계
    quarterly_pivot = df.pivot_table(index='업체명', columns='분기', values='전체계약금액', aggfunc='sum', fill_value=0)
    # 총합계 계산 및 랭킹 정렬
    total_df = df.groupby('업체명')['전체계약금액'].sum().sort_values(ascending=False).to_frame('총합계')
    
    # 데이터 병합 (최종 분석용 테이블)
    analysis_df = pd.concat([total_df, quarterly_pivot, monthly_pivot], axis=1).fillna(0)
    analysis_df = analysis_df.sort_values(by='총합계', ascending=False)

    # 4. UI 구성
    st.sidebar.subheader("필터링 설정")
    target_items = st.sidebar.multiselect("품목 선택", options=df['물품분류명'].dropna().unique())
    
    if target_items:
        df_f = df[df['물품분류명'].isin(target_items)]
        analysis_df = df_f.groupby('업체명')['전체계약금액'].sum().sort_values(ascending=False).to_frame('총합계')

    st.subheader("🏢 업체별 실적 요약 테이블 (순위별)")
    st.dataframe(analysis_df.style.format("{:,.0f}원"), use_container_width=True)
    
    # 시각화
    st.subheader("📊 상위 10개 업체 총 실적 비교")
    st.bar_chart(analysis_df['총합계'].head(10))
    
    # 다운로드
    csv = analysis_df.to_csv().encode('utf-8-sig')
    st.download_button("📥 분석 데이터 다운로드(CSV)", csv, "업체별_실적_분석.csv", "text/csv")
else:
    st.warning("⚠️ 데이터를 불러올 수 없습니다. Master_DB.csv를 확인하세요.")
