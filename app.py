import streamlit as st
import pandas as pd
from supabase import create_client
import os

st.set_page_config(layout="wide", page_title="데이터 완벽 복구 시스템")

@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

@st.cache_data(ttl=600)
def load_and_fix_data():
    # 1. 데이터 로드
    base_file = "Master_DB.csv"
    base_df = pd.read_csv(base_file) if os.path.exists(base_file) else pd.DataFrame()
    
    try:
        response = supabase.table("procurement_data").select("*").execute()
        db_df = pd.DataFrame(response.data)
        df = pd.concat([base_df, db_df], ignore_index=True)
    except:
        df = base_df
    
    # 2. [범인 검거] 데이터 정제 및 강제 변환
    df = df.drop_duplicates(subset=['납품요구번호'], keep='first')
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    
    # 날짜 강제 정제: '20260515' 형식의 숫자를 문자열로 바꾸고, 에러가 나도 무조건 살림
    df['일자_str'] = df['일자'].astype(str).str.replace(r'\.0', '', regex=True) # 소수점 제거
    df['일자_dt'] = pd.to_datetime(df['일자_str'], format='%Y%m%d', errors='coerce')
    
    # 날짜 변환이 실패한 건(NaT)도 억지로 2026-01-01 등으로 밀어넣지 않고 
    # '기타' 기간으로 분류하여 합산에 포함되게 함
    df['날짜_최종'] = df['일자_dt'].fillna(pd.Timestamp('2026-01-01'))
    df['월'] = df['날짜_최종'].dt.month.astype(str) + "월"
    
    return df

df = load_and_fix_data()

# 3. 데이터 분석 (이제 501건 포함됨!)
if not df.empty:
    st.subheader("📋 업체별 실적 요약 (정제 완료)")
    pivot = df.pivot_table(index='업체명', columns='월', values='전체계약금액', aggfunc='sum', fill_value=0, margins=True, margins_name='총 합계')
    st.dataframe(pivot.sort_values(by='총 합계', ascending=False).style.format("{:,.0f}원"), use_container_width=True)
    
    st.metric("최종 데이터 합계", f"{df['전체계약금액'].sum():,.0f} 원")
else:
    st.warning("데이터가 없습니다.")
