import streamlit as st
import pandas as pd
from supabase import create_client
import os

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="조달청 데이터 검증기")
st.title("🔍 데이터 검증 및 분석 대시보드")

# 2. Supabase 연결
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# 3. 데이터 로드 및 정제 엔진
@st.cache_data(ttl=600)
def load_analysis_data():
    # 파일 로드
    base_file = "Master_DB.csv"
    base_df = pd.read_csv(base_file) if os.path.exists(base_file) else pd.DataFrame()
    
    # DB 데이터 로드
    try:
        response = supabase.table("procurement_data").select("*").execute()
        db_df = pd.DataFrame(response.data)
    except:
        db_df = pd.DataFrame()
    
    # 데이터 합치기
    df = pd.concat([base_df, db_df], ignore_index=True)
    df = df.drop_duplicates(subset=['납품요구번호'], keep='last')
    
    # [데이터 정제]
    df['업체명'] = df['업체명'].fillna("알수없음").astype(str).str.strip()
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    
    # 테스트용 더미 데이터 강력 제거
    trash_data = ["테스트업체", "테스트", "확인필요", "000", "알수없음"]
    df = df[~df['업체명'].isin(trash_data)]
    
    return df

# 4. 데이터 로드
df = load_analysis_data()

# 5. 정밀 검증 버튼
if st.sidebar.button("세오 업체 데이터 정밀 분석"):
    # 파일 데이터만 로드 (검증용)
    if os.path.exists("Master_DB.csv"):
        raw_base = pd.read_csv("Master_DB.csv")
        raw_base['업체명'] = raw_base['업체명'].astype(str).str.strip()
        seo_base = raw_base[raw_base['업체명'].str.contains("세오", na=False)]
        st.write(f"### 📂 Master_DB 세오 결과")
        st.write(f"건수: {len(seo_base)}, 합계: {seo_base['전체계약금액'].sum():,.0f}")
    
    # 통합 데이터 검증
    seo_db = df[df['업체명'].str.contains("세오", na=False)]
    st.write(f"### 📊 현재 통합 데이터 세오 결과")
    st.write(f"건수: {len(seo_db)}, 합계: {seo_db['전체계약금액'].sum():,.0f}")
    
    st.write("---")
    st.dataframe(seo_db)

# 6. 대시보드 테이블
if not df.empty:
    st.subheader("🏢 업체별 실적 요약 테이블")
    total = df.groupby('업체명')['전체계약금액'].sum().sort_values(ascending=False).to_frame('총합계')
    st.dataframe(total.style.format("{:,.0f}"), use_container_width=True)
else:
    st.warning("데이터가 없습니다.")
