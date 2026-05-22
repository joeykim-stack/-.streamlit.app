import streamlit as st
import pandas as pd
from supabase import create_client
import os

st.set_page_config(layout="wide", page_title="조달청 실적 상세 리포트")
st.title("🏆 조달청 실적 상세 분석: 월/분기별 랭킹 리포트")

# 1. Supabase 연결 (실시간 데이터)
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# 2. 데이터 통합 및 정제 (데이터 유실 방지 로직)
@st.cache_data(ttl=600)
def get_final_data():
    # 진실의 원천: Master_DB.csv
    if os.path.exists("Master_DB.csv"):
        base_df = pd.read_csv("Master_DB.csv")
    else:
        base_df = pd.DataFrame()
        
    # 실시간 데이터 보충
    try:
        response = supabase.table("procurement_data").select("*").execute()
        db_df = pd.DataFrame(response.data)
    except:
        db_df = pd.DataFrame()
        
    # [데이터 통합 핵심] 
    # 1. 파일 데이터(base_df)를 항상 최우선으로 함
    # 2. 데이터 중복은 납품요구번호 기준, 파일 데이터를 유지(keep='first')
    df = pd.concat([base_df, db_df], ignore_index=True)
    df = df.drop_duplicates(subset=['납품요구번호'], keep='first')
    
    # [데이터 정제]
    df['전체계약금액'] = pd.to_numeric(df['전체계약계약금액'], errors='coerce').fillna(0) # 오타 방지
    # 혹시 컬럼명이 다를 수 있으니 확인: 전체계약금액
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    
    # 날짜 정제
    df['일자'] = pd.to_datetime(df['일자'].astype(str), format='%Y%m%d', errors='coerce')
    
    # 5월 18일 이후 실시간 데이터 업데이트 반영 (필터 적용 안함)
    return df

df = get_final_data()

# 3. 분석 테이블 생성 (월별/분기별/총합계)
if not df.empty:
    df['월'] = df['일자'].dt.month
    df['분기'] = df['일자'].dt.quarter
    
    # 데이터 피벗 (업체명 x [분기, 월])
    pivot_df = df.pivot_table(
        index='업체명',
        columns=['분기', '월'],
        values='전체계약금액',
        aggfunc='sum',
        fill_value=0,
        margins=True,
        margins_name='총 합계'
    )
    
    # 총 합계 기준 정렬
    pivot_df = pivot_df.sort_values(by='총 합계', ascending=False)
    
    # 화면 출력
    st.subheader("🏢 업체별 실적 요약 (단위: 원)")
    st.dataframe(pivot_df.style.format("{:,.0f}"), use_container_width=True)
    
    # 다운로드
    csv = pivot_df.to_csv().encode('utf-8-sig')
    st.download_button("📥 전체 보고서 다운로드", csv, "조달청_상세분석.csv")
else:
    st.warning("데이터 파일이 비어있습니다. Master_DB.csv를 확인하세요.")
