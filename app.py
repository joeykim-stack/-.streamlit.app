import streamlit as st
import pandas as pd
from supabase import create_client
import os

st.set_page_config(layout="wide", page_title="조달청 데이터 정밀 분석")
st.title("🏆 조달청 실적 상세 분석 리포트")

# Supabase 연결
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

@st.cache_data(ttl=600)
def load_data():
    # 1. 파일 데이터 로드
    base_file = "Master_DB.csv"
    if os.path.exists(base_file):
        df = pd.read_csv(base_file)
    else:
        return pd.DataFrame()
    
    # 2. 실시간 데이터 로드
    try:
        response = supabase.table("procurement_data").select("*").execute()
        db_df = pd.DataFrame(response.data)
        if not db_df.empty:
            df = pd.concat([df, db_df], ignore_index=True)
    except:
        pass

    # 3. 데이터 정제
    df = df.drop_duplicates(subset=['납품요구번호'], keep='first')
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    df['일자'] = pd.to_datetime(df['일자'].astype(str), format='%Y%m%d', errors='coerce')
    return df

df = load_data()

# [중요] 여기 들여쓰기를 확실하게 맞췄어!
if not df.empty:
    df['월'] = df['일자'].dt.month
    df['분기'] = df['일자'].dt.quarter
    
    # 피벗 테이블 생성
    pivot_table = df.pivot_table(
        index='업체명',
        columns=['분기', '월'],
        values='전체계약금액',
        aggfunc='sum',
        fill_value=0,
        margins=True,
        margins_name='총 합계'
    )
    
    # 컬럼명 평탄화 (튜플 -> 문자열)
    new_cols = []
    for col in pivot_table.columns:
        if isinstance(col, tuple):
            new_cols.append(f"{col[0]}분기 {col[1]}월".strip() if col[0] != '총 합계' else "총 합계")
        else:
            new_cols.append(str(col))
    pivot_table.columns = new_cols
    
    # 정렬
    if '총 합계' in pivot_table.index:
        companies_only = pivot_table.drop('총 합계')
        total_row = pivot_table.loc[['총 합계']]
        sorted_companies = companies_only.sort_values(by='총 합계', ascending=False)
        final_pivot = pd.concat([sorted_companies, total_row])
    else:
        final_pivot = pivot_table.sort_values(by='총 합계', ascending=False)
        
    # 문자열로 변환하여 출력 (에러 방지)
    display_df = final_pivot.applymap(lambda x: f"{int(x):,}원" if pd.notnull(x) else "0원")
    
    st.subheader("📋 업체별 월/분기 실적 종합 분석표")
    st.dataframe(display_df, use_container_width=True)
else:
    st.warning("데이터가 없습니다.")
