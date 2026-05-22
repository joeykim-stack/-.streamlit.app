import streamlit as st
import pandas as pd
from supabase import create_client
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os

st.set_page_config(layout="wide", page_title="조달청 실적 통합 분석 시스템")
st.title("🏆 조달청 54개사 실적 통합 분석 (정제 완료)")

# 우리 타겟 업체 52~54개사 리스트 (실제 업체명 리스트로 업데이트 필요)
TARGET_COMPANIES = ["주식회사 파로스", "이노뎁(주)", "주식회사 핀텔"] # 실제 업체명 리스트 추가

@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

@st.cache_data(ttl=600)
def load_and_clean_data():
    # 1. Master_DB.csv 로드
    base_df = pd.read_csv("Master_DB.csv") if os.path.exists("Master_DB.csv") else pd.DataFrame()
    
    # 2. DB 데이터 로드
    response = supabase.table("procurement_data").select("*").execute()
    db_df = pd.DataFrame(response.data)
    
    # 3. 데이터 통합 및 '쓰레기 데이터' 필터링 (핵심!)
    df = pd.concat([base_df, db_df]).drop_duplicates(subset=['납품요구번호'], keep='last')
    
    # 테스트용 더미 데이터 강력 삭제
    trash_data = ["테스트업체", "테스트", "확인필요", "000"]
    df = df[~df['업체명'].isin(trash_data)]
    df = df[df['사업자등록번호'] != "000"]
    
    # [중요] 타겟 업체만 남기기 (원한다면 전체 데이터 보려면 이 줄 주석 처리)
    # df = df[df['업체명'].isin(TARGET_COMPANIES)]
    
    return df

# 데이터 로드
df = load_and_clean_data()

# 4. 분석 테이블 구조화 (월/분기/총합)
if not df.empty:
    df['일자'] = pd.to_datetime(df['일자'], format='%Y%m%d', errors='coerce')
    df['월'] = df['일자'].dt.to_period('M')
    df['분기'] = df['일자'].dt.to_period('Q')
    
    # 월별, 분기별 피벗
    monthly = df.pivot_table(index='업체명', columns='월', values='전체계약금액', aggfunc='sum', fill_value=0)
    quarterly = df.pivot_table(index='업체명', columns='분기', values='전체계약금액', aggfunc='sum', fill_value=0)
    total = df.groupby('업체명')['전체계약금액'].sum().sort_values(ascending=False).to_frame('총합계')
    
    # 병합
    final_analysis = pd.concat([total, quarterly, monthly], axis=1).fillna(0)
    
    st.subheader("📋 업체별 실적 분석 테이블")
    st.dataframe(final_analysis.style.format("{:,.0f}"), use_container_width=True)
else:
    st.warning("데이터가 없습니다.")
