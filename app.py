import streamlit as st
import pandas as pd
from supabase import create_client
import os

# 페이지 설정
st.set_page_config(layout="wide", page_title="조달청 최종 리포트")
st.title("🏆 조달청 실적 상세 분석 리포트")

# Supabase 연결
@st.cache_resource
def get_supabase():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except:
        return None

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
    if supabase:
        try:
            response = supabase.table("procurement_data").select("*").execute()
            db_df = pd.DataFrame(response.data)
            if not db_df.empty:
                df = pd.concat([df, db_df], ignore_index=True)
        except:
            pass

    # 3. 데이터 정제 (가장 안전한 방식)
    df = df.drop_duplicates(subset=['납품요구번호'], keep='first')
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    df['일자'] = pd.to_datetime(df['일자'].astype(str), format='%Y%m%d', errors='coerce')
    
    # 누락된 데이터는 '기타' 처리
    df['업체명'] = df['업체명'].fillna("알수없음").astype(str).str.strip()
    return df

df = load_data()

# 4. 분석 엔진 (순서대로 1~12월 및 분기 합계 생성)
if not df.empty:
    df['월'] = df['일자'].dt.month
    df['분기'] = df['일자'].dt.quarter
    
    pivot = df.pivot_table(
        index='업체명', 
        columns=['분기', '월'], 
        values='전체계약금액', 
        aggfunc='sum', 
        fill_value=0, 
        margins=True, 
        margins_name='총 합계'
    )
    
    # 컬럼 재구성 (요청한 순서대로)
    cols_order = []
    for q in [1, 2, 3, 4]:
        for m in range(1, 4):
            month_val = (q-1)*3 + m
            if (q, month_val) in pivot.columns:
                cols_order.append((q, month_val))
        cols_order.append((q, '분기 합계')) # 분기 합계 위치
    cols_order.append(('총 합계', '')) # 총 합계 위치
    
    # 5. 최종 데이터프레임 평탄화 및 안전한 문자열 변환
    final_df = pivot.copy()
    
    # 데이터 출력용 안전한 문자열 변환 (포맷팅 에러 방지)
    output_df = pd.DataFrame(index=final_df.index)
    for col in final_pivot_cols := [c for c in pivot.columns if c[0] != '총 합계']:
        name = f"{col[0]}분기 {col[1]}월" if col[1] != '분기 합계' else f"{col[0]}분기 합계"
        output_df[name] = final_df[col].apply(lambda x: f"{int(x):,}원")
    output_df['총 합계'] = final_df[('총 합계', '')].apply(lambda x: f"{int(x):,}원")
    
    st.subheader("📋 업체별 월/분기 실적 종합 분석표")
    st.dataframe(output_df, use_container_width=True)
else:
    st.warning("데이터 로드에 실패했습니다.")
