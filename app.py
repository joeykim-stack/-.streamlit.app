import streamlit as st
import pandas as pd
from supabase import create_client
import os

# 1. 페이지 설정 및 라이브러리 로드
st.set_page_config(layout="wide", page_title="조달청 데이터 검증 시스템")

# 2. Supabase 연결
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# 3. 데이터 로드 및 정제 엔진
@st.cache_data(ttl=600)
def load_analysis_data():
    # Master_DB 로드
    if os.path.exists("Master_DB.csv"):
        base_df = pd.read_csv("Master_DB.csv")
    else:
        base_df = pd.DataFrame()

    # 실시간 DB 로드
    try:
        response = supabase.table("procurement_data").select("*").execute()
        db_df = pd.DataFrame(response.data)
    except:
        db_df = pd.DataFrame()
    
    # 합치기
    df = pd.concat([base_df, db_df]).drop_duplicates(subset=['납품요구번호'], keep='last')
    
    # [데이터 정제] 허위 데이터 및 공백 제거
    trash_data = ["테스트업체", "테스트", "확인필요", "000"]
    df = df[~df['업체명'].isin(trash_data)]
    df['업체명'] = df['업체명'].str.strip() # 공백 제거
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    
    return df

# 데이터 실행
df = load_analysis_data()

# 4. UI 및 정밀 검증
st.title("🔍 데이터 검증 및 분석 대시보드")

if st.sidebar.button("세오 업체 데이터 정밀 분석"):
    seo_base = pd.read_csv("Master_DB.csv")[pd.read_csv("Master_DB.csv")['업체명'].str.contains("세오", na=False)]
    seo_db = df[df['업체명'].str.contains("세오", na=False)]
    
    st.subheader("검증 결과")
    st.write(f"Master_DB 세오 건수: {len(seo_base)}, 합계: {seo_base['전체계약금액'].sum():,.0f}")
    st.write(f"현재 통합 데이터 세오 건수: {len(seo_db)}, 합계: {seo_db['전체계약금액'].sum():,.0f}")
    
    # 상세 데이터 보기
    st.dataframe(seo_db)

# 5. 월/분기별 순위 보드
if not df.empty:
    df['일자'] = pd.to_datetime(df['일자'], format='%Y%m%d', errors='coerce')
    df['월'] = df['일자'].dt.to_period('M')
    df['분기'] = df['일자'].dt.to_period('Q')
    
    monthly = df.pivot_table(index='업체명', columns='월', values='전체계약금액', aggfunc='sum', fill_value=0)
    total = df.groupby('업체명')['전체계약금액'].sum().sort_values(ascending=False).to_frame('총합계')
    
    analysis_df = pd.concat([total, monthly], axis=1).fillna(0)
    
    st.subheader("🏢 업체별 실적 요약 (순위별)")
    st.dataframe(analysis_df.style.format("{:,.0f}"), use_container_width=True)
else:
    st.warning("데이터가 없습니다.")
