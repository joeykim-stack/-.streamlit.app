import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import plotly.express as px
from io import BytesIO
import time
import urllib.parse

# --- 1. 기본 설정 ---
st.set_page_config(page_title="조달청 MAS+혁신 통합 분석", layout="wide")

def get_now_kst():
    return datetime.now() + timedelta(hours=9)

st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: 800; color: #1e3a8a; margin-bottom: 0.5rem; }
    .update-time { color: #6c757d; font-size: 0.9rem; margin-bottom: 2rem; }
    .stCheckbox { margin-bottom: -15px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 분석 대상 업체 및 제외 품목 ---
TARGET_COMPANIES = [
    "주식회사 티제이원", "주식회사 파로스", "주식회사 포딕스시스템", "주식회사 세오", 
    "주식회사 펜타게이트", "주식회사 홍석", "주식회사 솔디아", "주식회사 정현씨앤씨", "주식회사 디라직", 
    "주식회사 새움", "주식회사 디지탈라인", "주식회사 지인테크", "(주)비엔에스테크", 
    "주식회사 시큐인포", "주식회사 명광", "주식회사 올인원 코리아(ALL-IN-ONE KOREA CO., LTD.)", 
    "주식회사 포커스에이아이", "주식회사 한국아이티에스", "(주)앤다스", "주식회사 다누시스", 
    "이노뎁(주)", "주식회사 핀텔", "주식회사 오티에스", "주식회사 에스카", "에코아이넷(주)", 
    "미르텍 주식회사", "주식회사 아이즈온솔루션", "주식회사 그린아이티코리아", "주식회사 제노시스", 
    "(주)지성이엔지", "주식회사 알엠텍", "(주)원우이엔지", "(주)포소드", "주식회사 두원전자통신", 
    "대신네트웍스주식회사", "주식회사 마이크로시스템", "주식회사 크리에이티브넷", "주식회사센텍", 
    "(주)경림이앤지", "주식회사 웹게이트", "한국씨텍(주)", "뉴코리아전자통신 주식회사", 
    "주식회사 제이한테크", "주식회사 아라드네트웍스", "주식회사 진명아이앤씨", "렉스젠 주식회사", 
    "주식회사 디케이앤트", "사이테크놀로지스 주식회사", "주식회사 송우인포텍", "주식회사 아이엔아이", 
    "비티에스 주식회사", "주식회사 인텔리빅스", "주식회사 비알인포텍"
]

EXCLUDE_ITEMS = ["무인교통감시장치", "교통관제시스템", "구내방송장치", "마이크로폰", "주차관제장치", "출입통제시스템", "차량번호판독기", "화재경보장치"]

def normalize_corp_name(name):
    if not name: return ""
    return name.replace('주식회사', '').replace('(주)', '').replace(' ', '').strip()

TARGET_MAP = {normalize_corp_name(comp): comp for comp in TARGET_COMPANIES}

# --- 3. [공통] CSV 데이터 클리닝 함수 ---
def clean_and_parse_df(df, target_month, label):
    df.rename(columns=lambda x: str(x).strip(), inplace=True)
    if '계약업체명' in df.columns: df.rename(columns={'계약업체명': '업체명'}, inplace=True)
    if '품명' in df.columns: df.rename(columns={'품명': '물품분류명'}, inplace=True)
    req_col = '납품요구번호' if '납품요구번호' in df.columns else ('주문번호' if '주문번호' in df.columns else None)
    
    # 금액 파싱: 납품증감금액(개별단가) 우선
    if '납품증감금액' in df.columns: 
        df['금액'] = pd.to_numeric(df['납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    elif '납품요구금액' in df.columns: 
        df['금액'] = pd.to_numeric(df['납품요구금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    else: df['금액'] = 0

    temp_df = df[['업체명', '물품분류명', '금액', req_col]].copy()
    temp_df.columns = ['업체명', '물품분류명', '금액', '납품요구번호']
    temp_df['월'] = target_month
    temp_df['구분'] = label
    
    temp_df['업체명'] = temp_df['업체명'].astype(str).apply(lambda x: TARGET_MAP.get(normalize_corp_name(x), None))
    temp_df = temp_df.dropna(subset=['업체명'])
    return temp_df

# --- 4. 데이터 로드 (MAS + 혁신) ---
def load_all_data_v35():
    all_dfs = []
    
    # 1. 기존 MAS/우수조달 데이터 로드
    mas_files = {'data.csv': '1월', 'data02.csv': '2월', 'data03.csv': '3월', 'data04.csv': '4월'}
    for file, month in mas_files.items():
        try:
            for config in [{'encoding':'utf-16','sep':'\t'}, {'encoding':'cp949','sep':','}, {'encoding':'utf-8-sig','sep':','}]:
                try:
                    df = pd.read_csv(file, encoding=config['encoding'], sep=config['sep'], on_bad_lines='skip', low_memory=False)
                    if len(df.columns) > 5:
                        all_dfs.append(clean_and_parse_df(df, month, 'MAS/우수조달'))
                        break
                except: pass
        except: continue

    # 2. 신규 혁신제품 데이터 로드 (data_all.csv)
    try:
        inno_file = 'data_all.csv'
        for config in [{'encoding':'utf-16','sep':'\t'}, {'encoding':'cp949','sep':','}, {'encoding':'utf-8-sig','sep':','}]:
            try:
                df_inno = pd.read_csv(inno_file, encoding=config['encoding'], sep=config['sep'], on_bad_lines='skip', low_memory=False)
                if len(df_inno.columns) > 5:
                    # 혁신제품 파일은 1~4월이 섞여있으므로 날짜 컬럼에서 월을 추출
                    df_inno.rename(columns=lambda x: str(x).strip(), inplace=True)
                    date_col = '납품요구일자' if '납품요구일자' in df_inno.columns else '접수일자'
                    df_inno['extracted_month'] = pd.to_datetime(df_inno[date_col].astype(str).str[:10], errors='coerce').dt.month.fillna(0).astype(int).astype(str) + "월"
                    
                    # 데이터 정리
                    inno_cleaned = clean_and_parse_df(df_inno, '월', '혁신제품')
                    inno_cleaned['월'] = df_inno['extracted_month'] # 위 clean_and_parse_df에서 설정된 '월'을 실제 월로 덮어씀
                    all_dfs.append(inno_cleaned)
                    break
            except: pass
    except: pass

    result = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    return result.drop_duplicates()

# --- 5. 대시보드 구동 ---
df_total = load_all_data_v35()

st.markdown(f"<div class='main-title'>🏆 조달 통합 분석 v35.0 (MAS + 혁신제품 파일 통합)</div>", unsafe_allow_html=True)

# 품목 필터
with st.sidebar:
    st.header("🔍 품목 필터")
    if df_total.empty:
        st.error("데이터 파일을 찾을 수 없습니다.")
        selected_items = []
    else:
        all_items = sorted(df_total['물품분류명'].unique())
        selected_items = [i for i in all_items if st.checkbox(i, value=True, key=f"sidebar_{i}")]

if not selected_items:
    st.info("👈 분석할 품목을 선택해주세요.")
else:
    df_f = df_total[df_total['물품분류명'].isin(selected_items)]
    
    # 제외 품목 필터
    pattern = '|'.join(EXCLUDE_ITEMS)
    df_f = df_f[~df_f['물품분류명'].astype(str).str.contains(pattern, na=False, regex=True)]

    # 상단 요약
    t_amt = df_f['금액'].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 누적 전체 매출", f"{t_amt:,.0f} 원")
    c2.metric("💡 혁신제품 합계", f"{df_f[df_f['구분']=='혁신제품']['금액'].sum():,.0f} 원")
    c3.metric("🏢 MAS/우수 합계", f"{df_f[df_f['구분']=='MAS/우수조달']['금액'].sum():,.0f} 원")

    def render_board(df_data, title, cmap):
        st.subheader(title)
        if df_data.empty: st.write("데이터 없음"); return
        p = pd.pivot_table(df_data, values='금액', index='업체명', columns='월', aggfunc='sum', fill_value=0).reset_index()
        months = [m for m in ['1월', '2월', '3월', '4월'] if m in p.columns]
        p['누적 합계'] = p[months].sum(axis=1)
        p = p.sort_values('누적 합계', ascending=False).reset_index(drop=True)
        p.insert(0, 'No.', range(1, len(p)+1))
        st.dataframe(p.style.format({c: "{:,.0f}" for c in p.columns if c not in ['No.', '업체명']}).background_gradient(subset=['누적 합계'], cmap=cmap), use_container_width=True, hide_index=True)

    # 테이블 렌더링
    st.write("---")
    inc_inno = st.checkbox("✅ 종합 랭킹에 '혁신제품' 데이터 합산", value=True)
    board_total = df_f if inc_inno else df_f[df_f['구분'] != '혁신제품']
    render_board(board_total, "🏆 업체별 종합 조달 랭킹 (MAS + 우수 + 혁신)", "Blues")

    st.write("---")
    render_board(df_f[df_f['구분'] == 'MAS/우수조달'], "🏢 MAS / 우수조달 전용 실적", "Greens")

    st.write("---")
    render_board(df_f[df_f['구분'] == '혁신제품'], "💡 혁신제품 전용 실적", "Oranges")

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim. Data from data.csv ~ data04.csv & data_all.csv</center>", unsafe_allow_html=True)
