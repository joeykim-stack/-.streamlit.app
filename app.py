import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🏆 Master_DB 정밀 분석기")

# 파일 로드
@st.cache_data
def load_clean_data():
    df = pd.read_csv("Master_DB.csv")
    # 마이너스 값을 별도 컬럼으로 구분
    df['계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce')
    df['순수계약액'] = df['계약금액'].apply(lambda x: x if x > 0 else 0)
    df['취소/정정액'] = df['계약금액'].apply(lambda x: x if x < 0 else 0)
    return df

df = load_clean_data()

# 분석
st.subheader("업체별 실적 상세 분석")
report = df.groupby('업체명').agg({
    '순수계약액': 'sum',
    '취소/정정액': 'sum',
    '계약금액': 'sum'
})

st.dataframe(report.style.format("{:,.0f}원"))

# 최종 검증
total_pure = report['순수계약액'].sum()
st.metric("진짜 체결된 계약 총액 (순수)", f"{total_pure:,.0f} 원")
