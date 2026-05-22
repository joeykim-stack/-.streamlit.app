import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
import requests
import xml.etree.ElementTree as ET

# --- 1. 페이지 및 Supabase 연결 ---
st.set_page_config(layout="wide", page_title="조달청 실적 분석 대시보드")

@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

# --- 2. 타이틀 및 디자인 구성 ---
st.title("🏆 조달청 54개사 실적 분석 대시보드")
st.markdown("---")

# --- 3. 실시간 데이터 수집 및 DB 저장 로직 (데이터가 없으면 실행) ---
def fetch_and_save():
    API_KEY = "df5a1c97ab56593d5e99889ae1c030bfe0b5e9d924ffba9bae3712c8bb1ad75c"
    # 수집 기간 예시
    url = f"http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList?serviceKey={API_KEY}&numOfRows=500&pageNo=1&inqryDiv=1&inqryBgnDate=20260101&inqryEndDate=20260331"
    
    res = requests.get(url, verify=False)
    items = ET.fromstring(res.content).findall('.//item')
    
    data_list = []
    for item in items:
        data_list.append({
            "사업자등록번호": item.findtext('bizrno'),
            "업체명": "확인필요",
            "물품분류명": item.findtext('prdctClsfcNm'),
            "납품요구번호": item.findtext('dlvrReqNo'),
            "일자": item.findtext('dlvrReqRcptDate'),
            "전체계약금액": float(item.findtext('dlvrReqAmt') or 0)
        })
    
    # DB에 Upsert (중복제거)
    supabase.table("procurement_data").upsert(data_list, on_conflict="납품요구번호").execute()
    return pd.DataFrame(data_list)

# --- 4. 데이터 로드 및 시각화 ---
@st.cache_data(ttl=600)
def load_data():
    response = supabase.table("procurement_data").select("*").execute()
    return pd.DataFrame(response.data)

# 데이터가 없으면 수집 실행
df = load_data()
if df.empty:
    with st.spinner("첫 데이터 적재 중..."):
        df = fetch_and_save()
        st.rerun()

# --- 5. 화면 대시보드 구성 ---
col1, col2, col3 = st.columns(3)
col1.metric("총 등록 데이터", f"{len(df):,} 건")
col2.metric("전체 계약금액 합계", f"{df['전체계약금액'].sum():,.0f} 원")
col3.metric("대상 업체 수", f"{df['사업자등록번호'].nunique()} 개사")

st.markdown("---")

tab1, tab2 = st.tabs(["📊 실적 상세 분석", "🏢 업체별 랭킹"])

with tab1:
    st.dataframe(df.sort_values(by='일자', ascending=False), use_container_width=True)
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 데이터 엑셀(CSV) 다운로드", csv, "조달청_실적_데이터.csv", "text/csv")
    
with tab2:
    st.subheader("🏢 업체별 납품요구액 랭킹")
    ranking = df.groupby('사업자등록번호')['전체계약금액'].sum().reset_index()
    st.bar_chart(ranking.set_index('사업자등록번호'))

st.sidebar.markdown("---")
st.sidebar.markdown("© 2026 조달청 실적 통합 관리 시스템")
