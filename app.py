import streamlit as st
import pandas as pd
from supabase import create_client
import os

st.set_page_config(layout="wide", page_title="조달청 최종 분석 대시보드")
st.title("🏆 조달청 실적 정밀 분석 리포트")

@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

@st.cache_data(ttl=600)
def load_and_verify_data():
    # 1. Master_DB 로드 (절대적 기준)
    if os.path.exists("Master_DB.csv"):
        # low_memory=False로 대량 데이터 타입 강제 고정
        df = pd.read_csv("Master_DB.csv", dtype={'납품요구번호': str, '사업자등록번호': str}, low_memory=False)
    else:
        df = pd.DataFrame()

    # 2. 실시간 DB 데이터 로드
    try:
        response = supabase.table("procurement_data").select("*").execute()
        db_df = pd.DataFrame(response.data)
        if not db_df.empty:
            # 병합: 실시간 데이터 중 Master에 없는 것만 추가
            df = pd.concat([df, db_df], ignore_index=True)
    except:
        pass
    
    # 3. [핵심 정제] 데이터 유실 방지
    # 1) 중복 제거: 납품요구번호 기준, 원본(Master) 데이터 우선 유지
    df = df.drop_duplicates(subset=['납품요구번호'], keep='first')
    
    # 2) 타입 강제 변환
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    
    # 3) 일자 포맷팅 (20260515 형식 강제 변환)
    df['일자'] = pd.to_datetime(df['일자'].astype(str), format='%Y%m%d', errors='coerce')
    
    # NaT(날짜 변환 실패)된 데이터가 있다면 경고 표시 (이게 데이터가 사라지는 주범)
    if df['일자'].isna().any():
        st.sidebar.warning(f"⚠️ 날짜 변환 실패 건수: {df['일자'].isna().sum()}건 확인 필요")
    
    return df

df = load_and_verify_data()

# 4. 구조화 분석 (월/분기별 피벗)
if not df.empty:
    df['월'] = df['일자'].dt.month
    df['분기'] = df['일자'].dt.quarter
    
    # 테이블 구조화
    analysis = df.pivot_table(
        index='업체명', 
        columns=['분기', '월'], 
        values='전체계약금액', 
        aggfunc='sum', 
        fill_value=0, 
        margins=True, 
        margins_name='총 합계'
    )
    
    # 총 합계 기준 내림차순
    analysis = analysis.sort_values(by='총 합계', ascending=False)
    
    st.subheader("📋 업체별 실적 요약 (전체 건 기준)")
    st.dataframe(analysis.style.format("{:,.0f}원"), use_container_width=True)
else:
    st.warning("Master_DB.csv 파일이 없습니다.")
