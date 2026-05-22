import streamlit as st
import pandas as pd
from supabase import create_client
import os

st.set_page_config(layout="wide", page_title="조달청 데이터 정밀 분석")
st.title("🏆 조달청 실적 정밀 분석 대시보드")

# 1. Supabase 연결
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# 2. 데이터 통합 및 정제 (가장 안전한 방식)
@st.cache_data(ttl=600)
def get_final_data():
    # 파일 데이터가 '진실의 원천(Master)'
    base_file = "Master_DB.csv"
    if os.path.exists(base_file):
        df = pd.read_csv(base_file)
    else:
        df = pd.DataFrame()
        
    # 실시간 DB 데이터 가져오기
    try:
        response = supabase.table("procurement_data").select("*").execute()
        db_df = pd.DataFrame(response.data)
        if not db_df.empty:
            df = pd.concat([df, db_df], ignore_index=True)
    except:
        pass
    
    # 3. 정제 프로세스
    df = df.drop_duplicates(subset=['납품요구번호'], keep='first')
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    df['일자'] = pd.to_datetime(df['일자'], format='%Y%m%d', errors='coerce')
    
    return df

# 데이터 로드
df = get_final_data()

# 4. 분석 엔진 (월별, 분기별, 총합계)
if not df.empty:
    df['월'] = df['일자'].dt.month
    df['분기'] = df['일자'].dt.quarter
    
    # 순위별 합계 계산
    analysis = df.pivot_table(
        index='업체명', 
        columns=['분기', '월'], 
        values='전체계약금액', 
        aggfunc='sum', 
        fill_value=0, 
        margins=True, 
        margins_name='총 합계'
    )
    
    # 총 합계 기준 내림차순 정렬
    analysis = analysis.sort_values(by='총 합계', ascending=False)
    
    st.subheader("📋 업체별 월/분기 실적 리포트")
    st.dataframe(analysis.style.format("{:,.0f}원"), use_container_width=True)
else:
    st.warning("데이터가 없습니다. Master_DB.csv 파일을 확인하세요.")
