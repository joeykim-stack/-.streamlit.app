import streamlit as st
import pandas as pd
from supabase import create_client
import os

st.set_page_config(layout="wide")
st.title("🏆 조달청 실적 상세 분석 리포트")

@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

@st.cache_data(ttl=600)
def load_data():
    # 1. 파일 데이터 로드
    if os.path.exists("Master_DB.csv"):
        df = pd.read_csv("Master_DB.csv")
    else:
        st.error("Master_DB.csv 파일을 찾을 수 없습니다.")
        return pd.DataFrame()
    
    # 2. 실시간 데이터 로드
    try:
        response = supabase.table("procurement_data").select("*").execute()
        db_df = pd.DataFrame(response.data)
        if not db_df.empty:
            df = pd.concat([df, db_df], ignore_index=True)
    except:
        pass

    # 3. [핵심] 컬럼명 표준화 (KeyError 원인 제거)
    # 엑셀의 헤더 이름과 Supabase의 컬럼명을 여기서 맞춰줌
    rename_map = {
        '업체명': '업체명',
        '전체계약금액': '전체계약금액',
        '일자': '일자',
        '납품요구번호': '납품요구번호'
    }
    df = df.rename(columns=rename_map)
    
    # 누락된 필수 컬럼이 있으면 0으로 채움 (오류 방지)
    for col in ['업체명', '전체계약금액', '일자', '납품요구번호']:
        if col not in df.columns:
            df[col] = 0 if col == '전체계약금액' else "알수없음"

    # 4. 정제
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    df['일자'] = pd.to_datetime(df['일자'].astype(str), format='%Y%m%d', errors='coerce')
    
    return df

df = load_data()

# 5. 분석 로직
if not df.empty:
    df['월'] = df['일자'].dt.month
    df['분기'] = df['일자'].dt.quarter
    
    # 순위별 피벗 테이블
    report = df.pivot_table(
        index='업체명',
        columns=['분기', '월'],
        values='전체계약금액',
        aggfunc='sum',
        fill_value=0,
        margins=True,
        margins_name='총 합계'
    ).sort_values(by='총 합계', ascending=False)
    
    st.dataframe(report.style.format("{:,.0f}원"), use_container_width=True)
else:
    st.warning("데이터 로드 중 문제가 발생했습니다.")
