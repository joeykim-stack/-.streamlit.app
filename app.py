import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# --- 1. 기본 설정 ---
st.set_page_config(page_title="조달청 초고속 실적 대시보드", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: 800; color: #1e3a8a; margin-bottom: 0.5rem; }
    .sub-title { font-size: 1.1rem; color: #6c757d; margin-bottom: 2rem; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>🏆 조달청 영상감시장치 타겟 랭킹 대시보드</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>⚡ 오프라인 마스터 DB 연동 (로딩 속도: 0.1초)</div>", unsafe_allow_html=True)

# --- 2. 데이터 로드 (캐시 사용으로 빛의 속도) ---
@st.cache_data
def load_master_db():
    if not os.path.exists("Master_DB.csv"):
        return pd.DataFrame()
    
    df = pd.read_csv("Master_DB.csv", encoding='utf-8-sig', dtype={'사업자등록번호': str})
    
    # 텍스트로 읽힌 금액을 다시 숫자로 변환
    for col in ['전체계약금액', '영상감시장치_계약금액']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

with st.spinner("마스터 DB를 불러오는 중입니다..."):
    df = load_master_db()

if df.empty:
    st.error("🚨 Master_DB.csv 파일이 같은 폴더에 없습니다. make_db.py를 먼저 실행해주세요!")
    st.stop()

# 분기 컬럼 추가
def get_quarter(m_str):
    if not isinstance(m_str, str): return '기타'
    m_str = m_str.replace('월', '')
    if not m_str.isdigit(): return '기타'
    m = int(m_str)
    return '1분기' if m<=3 else ('2분기' if m<=6 else ('3분기' if m<=9 else '4분기'))

df['분기'] = df['월'].apply(get_quarter)

# --- 3. 사이드바 필터 ---
with st.sidebar:
    st.header("🔍 분석 필터")
    
    # 계약 종류 필터 (MAS vs 우수조달)
    mas_filter = st.radio("계약 종류 선택", ["전체 보기", "MAS (다수공급자/제3자)", "우수조달/일반경쟁"])
    
    if mas_filter == "MAS (다수공급자/제3자)":
        df = df[df['MAS여부'] == 'Y']
    elif mas_filter == "우수조달/일반경쟁":
        df = df[df['MAS여부'] == 'N']
        
    st.markdown("---")
    st.write(f"📊 현재 분석 데이터: **{len(df):,} 건**")

# --- 4. 요약 메트릭 ---
total_all = df['전체계약금액'].sum()
total_cctv = df['영상감시장치_계약금액'].sum()
cctv_ratio = (total_cctv / total_all * 100) if total_all > 0 else 0

c1, c2, c3 = st.columns(3)
c1.metric("💰 53개사 전체 계약금액", f"{total_all:,.0f} 원")
c2.metric("📷 영상감시장치 타겟 금액", f"{total_cctv:,.0f} 원")
c3.metric("🎯 영상감시장치 매출 비중", f"{cctv_ratio:.1f} %")
st.markdown("---")

# --- 5. 핵심: 기업별 랭킹 보드 (전체매출 vs CCTV 찐매출) ---
st.subheader("🏢 기업별 종합 실적 랭킹 (CCTV 매출 비중 분석)")

# 피벗 테이블 생성
pivot_df = df.groupby('업체명').agg(
    계약건수=('납품요구번호', 'nunique'),
    전체매출=('전체계약금액', 'sum'),
    CCTV매출=('영상감시장치_계약금액', 'sum')
).reset_index()

# 기타 품목 매출 (방송장비 등)
pivot_df['기타품목매출'] = pivot_df['전체매출'] - pivot_df['CCTV매출']
pivot_df['CCTV비중(%)'] = (pivot_df['CCTV매출'] / pivot_df['전체매출'] * 100).fillna(0).round(1)

# 정렬
sort_col = st.selectbox("⬇️ 정렬 기준", ["CCTV매출", "전체매출", "계약건수"], index=0)
pivot_df = pivot_df.sort_values(by=sort_col, ascending=False).reset_index(drop=True)
pivot_df.insert(0, '랭킹', range(1, len(pivot_df) + 1))

# 스타일링 (숫자 포맷팅 및 그라데이션)
styled_df = pivot_df.style.format({
    '전체매출': '{:,.0f}',
    'CCTV매출': '{:,.0f}',
    '기타품목매출': '{:,.0f}',
    'CCTV비중(%)': '{:.1f}%'
}).background_gradient(subset=['CCTV매출'], cmap='Blues'
).background_gradient(subset=['전체매출'], cmap='Greys'
).background_gradient(subset=['CCTV비중(%)'], cmap='Greens')

st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)

# --- 6. 시각화 (그래프) ---
st.markdown("---")
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("🍩 타겟(CCTV) 매출 시장 점유율 (Top 10)")
    top10_cctv = pivot_df.nlargest(10, 'CCTV매출')
    fig_pie = px.pie(top10_cctv, names='업체명', values='CCTV매출', hole=0.4,
                     color_discrete_sequence=px.colors.qualitative.Set2)
    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_pie, use_container_width=True)

with col_chart2:
    st.subheader("📊 상위 10개사 포트폴리오 (CCTV vs 기타)")
    top10_total = pivot_df.nlargest(10, '전체매출')
    
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(x=top10_total['업체명'], y=top10_total['CCTV매출'], name='CCTV 매출', marker_color='#3b82f6'))
    fig_bar.add_trace(go.Bar(x=top10_total['업체명'], y=top10_total['기타품목매출'], name='기타 품목', marker_color='#cbd5e1'))
    
    fig_bar.update_layout(barmode='stack', legend=dict(orientation="h", y=1.1, x=0.8), margin=dict(t=20, b=0))
    st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("<br><center style='color:gray;'>Data Powered by Local Master DB. Dashboard v100.</center>", unsafe_allow_html=True)