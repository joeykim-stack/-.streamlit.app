import streamlit as st
import pandas as pd
from supabase import create_client
import os

st.set_page_config(layout="wide", page_title="최종 데이터 정합성 보정 시스템")

# 1. Supabase 연결
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# 2. 강제 병합 및 정제 함수
@st.cache_data(ttl=600)
def get_final_data():
    # A. 파일 데이터 (진실의 원천)
    if os.path.exists("Master_DB.csv"):
        base_df = pd.read_csv("Master_DB.csv")
    else:
        base_df = pd.DataFrame()
        
    # B. DB 데이터 (실시간 보충)
    try:
        response = supabase.table("procurement_data").select("*").execute()
        db_df = pd.DataFrame(response.data)
    except:
        db_df = pd.DataFrame()

    # C. 완전 병합 (파일 우선)
    if not db_df.empty:
        # DB 컬럼명을 파일 컬럼명에 맞춤
        db_df = db_df.rename(columns={'납품요구번호': '납품요구번호', '전체계약금액': '전체계약금액'}) 
        df = pd.concat([base_df, db_df], ignore_index=True)
    else:
        df = base_df

    # D. 가장 중요한 정제 (중복 제거 & 금액 타입 고정)
    df = df.drop_duplicates(subset=['납품요구번호'], keep='first') # 파일 데이터 우선 보존
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    
    return df

df = get_final_data()

# 3. 결과 출력
st.subheader("총 데이터 수 및 금액 검증")
col1, col2 = st.columns(2)
col1.metric("총 데이터 건수", f"{len(df):,} 건")
col2.metric("총 계약금액 합계", f"{df['전체계약금액'].sum():,.0f} 원")

# 업체별 실적 확인
st.dataframe(df.groupby('업체명')['전체계약금액'].sum().sort_values(ascending=False))
