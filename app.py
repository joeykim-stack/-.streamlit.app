import streamlit as st
import pandas as pd
from supabase import create_client
import os

# 페이지 설정
st.set_page_config(layout="wide", page_title="조달청 최종 실적 분석")
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
def load_and_verify_data():
    base_file = "Master_DB.csv"
    if os.path.exists(base_file):
        df = pd.read_csv(base_file)
    else:
        return pd.DataFrame(), None
    
    if supabase:
        try:
            response = supabase.table("procurement_data").select("*").execute()
            db_df = pd.DataFrame(response.data)
            if not db_df.empty:
                df = pd.concat([df, db_df], ignore_index=True)
        except:
            pass

    # [진단용 원본 복사]
    raw_df = df.copy()
    
    # 데이터 정제
    df = df.drop_duplicates(subset=['납품요구번호'], keep='first')
    
    # 정제 과정에서의 손실 파악
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce')
    df['일자_dt'] = pd.to_datetime(df['일자'].astype(str), format='%Y%m%d', errors='coerce')
    
    # 검증 리포트 생성
    report = {
        "총 데이터 행 수": len(raw_df),
        "금액 NaN 건수": df['전체계약금액'].isna().sum(),
        "날짜 변환 실패(NaT) 건수": df['일자_dt'].isna().sum(),
        "실제 계산에 반영된 합계": df['전체계약금액'].sum()
    }
    
    return df, report

df, report = load_and_verify_data()

# 1. 진단 리포트 출력
st.subheader("🔍 데이터 정합성 진단 리포트")
if report:
    cols = st.columns(4)
    for i, (key, value) in enumerate(report.items()):
        cols[i].metric(key, f"{value:,.0f}" if isinstance(value, float) else value)
    st.info("💡 만약 '날짜 변환 실패' 건수가 많다면, 그 데이터들이 피벗 테이블에서 누락되고 있는 겁니다.")

# 2. 분석 테이블 생성
if not df.empty:
    df['월'] = df['일자_dt'].dt.month
    df['분기'] = df['일자_dt'].dt.quarter
    
    # 피벗 테이블 생성
    pivot = df.pivot_table(index='업체명', columns=['분기', '월'], values='전체계약금액', aggfunc='sum', fill_value=0)
    
    # 분기 합계 및 총 합계 로직
    for q in range(1, 5):
        pivot[f'{q}분기 합계'] = pivot.loc[:, q].sum(axis=1) if q in pivot.columns else 0
    pivot['총 합계'] = pivot[[f'{q}분기 합계' for q in range(1, 5)]].sum(axis=1)
    
    # 순서 정렬
    col_order = [1, 2, 3, '1분기 합계', 4, 5, 6, '2분기 합계', 7, 8, 9, '3분기 합계', 10, 11, 12, '4분기 합계', '총 합계']
    # 존재하는 컬럼만 필터링
    existing_cols = [c for c in col_order if c in pivot.columns or (isinstance(c, str) and c in pivot.columns)]
    pivot = pivot[existing_cols]
    pivot = pivot.sort_values(by='총 합계', ascending=False)
    
    # 3. 안전한 출력 (숫자 변환)
    display_df = pivot.map(lambda x: f"{int(x):,}원") if hasattr(pivot, 'map') else pivot.applymap(lambda x: f"{int(x):,}원")
    
    st.subheader("📋 업체별 실적 종합 분석표")
    st.dataframe(display_df, use_container_width=True)
else:
    st.warning("데이터가 없습니다.")
