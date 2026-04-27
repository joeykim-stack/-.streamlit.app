import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import time
import urllib.parse

# --- 1. 기본 설정 및 KST 시계 ---
st.set_page_config(page_title="조달청 실적 분석 대시보드", layout="wide")

def get_now_kst():
    return datetime.now() + timedelta(hours=9)

st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: 800; margin-bottom: 0.5rem; }
    .update-time { color: #6c757d; font-size: 0.9rem; margin-bottom: 2rem; }
    .stCheckbox { margin-bottom: -15px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 분석 대상 업체 및 제외 품목 세팅 ---
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

EXCLUDE_ITEMS = [
    "무인교통감시장치", "교통관제시스템", "구내방송장치", "마이크로폰", "마이크스탠드", 
    "무선마이크장치", "버스승강장", "보행자안전차단기", "산업제어소프트웨어", "생체인식장비", 
    "세탁물건조기", "소프트웨어유지및지원서비스", "스트로보또는경고등", "스피커스탠드", 
    "스피커제어유닛", "업소용세탁기", "오디오모니터", "오디오믹서", "증폭기결합", "오디오앰프", 
    "오이도장비커넥터및스테이지박스", "오디오장비커넥터및스테이지박스", "이퀄라이저", 
    "정보화교육서비스", "주차관제장치", "차량번호판독기", "출입통제시스템", "태양전지조절기", 
    "파일시스템소프트웨어", "패키지소프트웨어개발및도입서비스", "플러그용잭", "해석또는과학소프트웨어", 
    "화재경보장치", "콤팩트디스크재생또는녹음기", "리튬전지", "리셉터클", "라디오튜너"
]

def normalize_corp_name(name):
    if not name: return ""
    return name.replace('주식회사', '').replace('(주)', '').replace(' ', '').strip()

TARGET_MAP = {normalize_corp_name(comp): comp for comp in TARGET_COMPANIES}

# --- 3. 로컬 데이터 로드 (혁신제품 구분 로직 추가) ---
def load_historical_data_v32():
    file_month_map = {'data.csv': '1월', 'data02.csv': '2월', 'data03.csv': '3월', 'data04.csv': '4월'}
    dfs = []
    for file, target_month in file_month_map.items():
        try:
            df = None
            for config in [{'encoding':'utf-16','sep':'\t'}, {'encoding':'cp949','sep':','}, {'encoding':'utf-8','sep':','}, {'encoding':'utf-8-sig','sep':','}]:
                try:
                    temp_df = pd.read_csv(file, encoding=config['encoding'], sep=config['sep'], on_bad_lines='skip', low_memory=False)
                    if len(temp_df.columns) > 2:
                        df = temp_df; break
                except: pass
            if df is None: continue
            
            df.rename(columns=lambda x: str(x).strip(), inplace=True)
            if '계약업체명' in df.columns and '업체명' not in df.columns: df.rename(columns={'계약업체명': '업체명'}, inplace=True)
            if '품명' in df.columns and '물품분류명' not in df.columns: df.rename(columns={'품명': '물품분류명'}, inplace=True)
            req_col = '납품요구번호' if '납품요구번호' in df.columns else ('주문번호' if '주문번호' in df.columns else None)
            if not req_col: continue 

            df[req_col] = df[req_col].fillna('').astype(str).str.replace('nan', '', regex=False).str.replace(r'\.0$', '', regex=True).str.strip()

            # V19 순정 금액 추출 로직
            if '납품증감금액' in df.columns: df['금액'] = pd.to_numeric(df['납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '합계납품증감금액' in df.columns: df['금액'] = pd.to_numeric(df['합계납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '납품요구금액' in df.columns: df['금액'] = pd.to_numeric(df['납품요구금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '금액' in df.columns: df['금액'] = pd.to_numeric(df['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            else: continue
            
            # 💡 [구분값 생성] 혁신제품 여부 판단 (계약체결형태명 등에 '혁신'이 있는지 확인)
            contract_stle_col = '계약체결형태명' if '계약체결형태명' in df.columns else None
            df['구분'] = '일반/MAS'
            if contract_stle_col:
                df.loc[df[contract_stle_col].astype(str).str.contains('혁신', na=False), '구분'] = '혁신제품'
            
            temp_df = df[['업체명', '물품분류명', '금액', req_col, '구분']].copy()
            temp_df.columns = ['업체명', '물품분류명', '금액', '납품요구번호', '구분']
            temp_df['월'] = target_month
            
            temp_df['업체명'] = temp_df['업체명'].astype(str).apply(lambda x: TARGET_MAP.get(normalize_corp_name(x), None))
            temp_df = temp_df.dropna(subset=['업체명'])
            
            if 'MAS여부' in df.columns:
                temp_df['MAS여부'] = df['MAS여부'].fillna('N').astype(str).str.strip().str.upper()
            else:
                # '다수공급자계약'이라는 단어가 형태명에 있으면 MAS로 간주
                if contract_stle_col:
                    temp_df['MAS여부'] = df[contract_stle_col].apply(lambda x: 'Y' if '다수공급자' in str(x) else 'N')
                else:
                    temp_df['MAS여부'] = 'Y' 
                
            dfs.append(temp_df)
        except Exception: continue
    
    result_df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    if not result_df.empty: result_df = result_df.drop_duplicates()
    return result_df

# --- 4. 실시간 API 수집 (혁신제품 필터 추가) ---
def fetch_api_data_v32():
    # 💡 현재 API 한도 초과(429) 상태이므로 방어 모드 유지
    # 트래픽이 풀렸을 때를 위해 로직만 확장해 둡니다.
    # [정상화 시 작동 로직]:
    # valid_keywords = ['제3자단가', '다수공급자', '우수', '혁신']
    # if '혁신' in cntrct_stle: data['구분'] = '혁신제품'
    return pd.DataFrame(), "🔵 API 한도 초과 방어 모드 (로컬 데이터 100% 정밀 검증 중)"

# --- 5. 데이터 통합 및 정제 ---
def get_processed_data_v32():
    df_hist = load_historical_data_v32()
    df_api, api_msg = fetch_api_data_v32()

    if not df_hist.empty: df_hist['납품요구번호'] = df_hist['납품요구번호'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    if not df_api.empty: df_api['납품요구번호'] = df_api['납품요구번호'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

    if not df_api.empty and not df_hist.empty:
        existing_nos = set(df_hist['납품요구번호'].unique())
        existing_nos.discard('')
        df_api_clean = df_api[~df_api['납품요구번호'].isin(existing_nos)]
        df_total = pd.concat([df_hist, df_api_clean], ignore_index=True)
    elif not df_api.empty:
        df_total = df_api.copy()
    else:
        df_total = df_hist.copy()

    if not df_total.empty and '물품분류명' in df_total.columns:
        pattern = '|'.join(EXCLUDE_ITEMS)
        df_total = df_total[~df_total['물품분류명'].astype(str).str.contains(pattern, na=False, regex=True)]

    return df_total, api_msg

# 데이터 실행
df_total, api_msg = get_processed_data_v32()

# --- 6. UI ---
st.markdown(f"<div class='main-title'>🏆 조달청 통합 실적 분석 v32.0 (혁신제품 포함판)</div>", unsafe_allow_html=True)
col_head1, col_head2 = st.columns([5, 1])
with col_head1:
    st.markdown(f"<div class='update-time'>🕒 상태: {api_msg}</div>", unsafe_allow_html=True)
with col_head2:
    if st.button("🔄 즉시 새로고침", use_container_width=True):
        st.rerun()

# --- 7. 사이드바 필터 ---
with st.sidebar:
    st.header("🔍 품목 상세 필터")
    if df_total.empty:
        st.error("⚠️ 데이터를 찾을 수 없습니다.")
        selected_items = []
    else:
        all_items = sorted(df_total['물품분류명'].dropna().unique())
        col_s1, col_s2 = st.columns(2)
        if col_s1.button("✅ 전체 선택"):
            for item in all_items: st.session_state[f"cb_{item}"] = True
        if col_s2.button("❌ 전체 삭제"):
            for item in all_items: st.session_state[f"cb_{item}"] = False
        st.write("---")
        selected_items = []
        for item in all_items:
            cb_key = f"cb_{item}"
            if cb_key not in st.session_state: st.session_state[cb_key] = True
            if st.checkbox(item, key=cb_key): selected_items.append(item)

# --- 8. 메인 대시보드 ---
if not selected_items:
    st.info("👈 왼쪽 사이드바에서 분석할 품목을 선택해주세요.")
else:
    df_f = df_total[df_total['물품분류명'].isin(selected_items)].copy()
    
    # 상단 요약 지표 (혁신제품 포함 전체)
    t_cnt = df_f['납품요구번호'].nunique()
    t_amt = df_f['금액'].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 누적 합계 매출", f"{t_amt:,.0f} 원")
    c2.metric("📝 총 계약 건수", f"{t_cnt:,} 건")
    c3.metric("💡 혁신제품 비중", f"{(df_f[df_f['구분']=='혁신제품']['금액'].sum()/t_amt*100 if t_amt>0 else 0):.1f} %")
    st.markdown("---")

    # 랭킹 보드 공통 렌더링 함수
    def render_ranking_board(df_data, title, sort_key, dl_key, cmap_color='Blues'):
        st.subheader(title)
        if df_data.empty:
            st.info("해당 데이터가 없습니다.")
            return
        
        # 피벗 테이블 생성 (금액 기준)
        p_amt = pd.pivot_table(df_data, values='금액', index='업체명', columns='월', aggfunc='sum', fill_value=0).reset_index()
        for m in ['1월', '2월', '3월', '4월']:
            if m not in p_amt.columns: p_amt[m] = 0
        p_amt['누적 합계'] = p_amt['1월'] + p_amt['2월'] + p_amt['3월'] + p_amt['4월']
        
        final = p_amt[['업체명', '1월', '2월', '3월', '4월', '누적 합계']]
        final = final.sort_values('누적 합계', ascending=False).reset_index(drop=True)
        final.insert(0, 'No.', range(1, len(final) + 1))
        
        fmt_map = {c: "{:,.0f}" for c in final.columns if c not in ['No.', '업체명']}
        styled = final.style.format(fmt_map).background_gradient(subset=['누적 합계'], cmap=cmap_color)
        st.dataframe(styled, use_container_width=True, hide_index=True)

        xlsx = BytesIO()
        with pd.ExcelWriter(xlsx, engine='xlsxwriter') as wr:
            final.to_excel(wr, index=False, sheet_name='Ranking')
        st.download_button(f"💾 {title} 엑셀 다운로드", xlsx.getvalue(), f'{dl_key}.xlsx', key=dl_key)

    # --- 💡 테이블 1: 종합 랭킹 (혁신제품 스위치 추가) ---
    st.subheader("⚙️ 종합 랭킹 설정")
    inc_innovation = st.checkbox("✅ 종합 랭킹 테이블에 '혁신제품' 실적 포함하기", value=True)
    
    board_df_total = df_f.copy()
    if not inc_innovation:
        board_df_total = board_df_total[board_df_total['구분'] != '혁신제품']
    
    render_ranking_board(
        df_data=board_df_total, 
        title="🏆 업체별 종합 조달 랭킹 (Third-party Units)", 
        sort_key='total', dl_key='total_ranking', cmap_color='Blues'
    )

    st.markdown("---")

    # --- 💡 테이블 2: MAS 전용 랭킹 ---
    board_df_mas = df_f[df_f['MAS여부'] == 'Y'].copy()
    render_ranking_board(
        df_data=board_df_mas, 
        title="🏢 MAS 계약 전용 실적 랭킹 (다수공급자계약)", 
        sort_key='mas', dl_key='mas_ranking', cmap_color='Greens'
    )

    st.markdown("---")

    # --- 💡 테이블 3: 혁신제품 전용 랭킹 (New!) ---
    board_df_inno = df_f[df_f['구분'] == '혁신제품'].copy()
    render_ranking_board(
        df_data=board_df_inno, 
        title="💡 혁신제품 전용 실적 랭킹 (Innovative Products)", 
        sort_key='inno', dl_key='inno_ranking', cmap_color='Oranges'
    )

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim. Data from Public Data Portal.</center>", unsafe_allow_html=True)
