import streamlit as st
import pandas as pd
import os

st.title("🔍 이노뎁 5월 데이터 정밀 진단")

@st.cache_data
def load_and_filter():
    if not os.path.exists("Master_DB.csv"):
        return None, "파일 없음"
    
    df = pd.read_csv("Master_DB.csv")
    
    # 금액 숫자 변환
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    
    # 타겟 데이터 필터링 (이노뎁 + 5월)
    # 업체명 공백 제거 후 비교
    df['업체명_clean'] = df['업체명'].astype(str).str.strip()
    df['월_clean'] = df['월'].astype(str).str.strip()
    
    target_df = df[
        (df['업체명_clean'].str.contains('이노뎁', na=False)) & 
        (df['월_clean'].str.contains('5월', na=False))
    ]
    
    return target_df, None

target_df, error = load_and_filter()

if error:
    st.error(error)
else:
    st.write(f"이노뎁 5월 데이터 건수: {len(target_df)}건")
    st.dataframe(target_df)
    
    # 합계 계산 (마이너스 포함 순액)
    total_val = target_df['전체계약금액'].sum()
    st.metric("추출된 데이터 합계 (순액)", f"{total_val:,.0f} 원")
    
    # 마이너스 데이터만 따로 뽑아보기 (범인 검거용)
    negative_df = target_df[target_df['전체계약금액'] < 0]
    if not negative_df.empty:
        st.warning(f"🚨 마이너스(취소/정정) 데이터 발견 ({len(negative_df)}건)")
        st.dataframe(negative_df)
