import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# --- 1. 기본 설정 ---
st.set_page_config(page_title="조달청 MAS + 혁신 통합 분석", layout="wide")

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

# --- 3. [기존 데이터] MAS / 우수조달 로드 (네가 확인했던 V19 완벽 로직) ---
def load_base_data():
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

            # 💡 아무것도 안 건드린 순정 V19 로직!
            if '납품증감금액' in df.columns: df['금액'] = pd.to_numeric(df['납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '합계납품증감금액' in df.columns: df['금액'] = pd.to_numeric(df['합계납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '납품요구금액' in df.columns: df['금액'] = pd.to_numeric(df['납품요구금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '금액' in df.columns: df['금액'] = pd.to_numeric(df['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            else: continue
            
            temp_df = df[['업체명', '물품분류명', '금액', req_col]].copy()
            temp_df.columns = ['업체명', '물품분류명', '금액', '납품요구번호']
            temp_df['월'] = target_month
            temp_df['구분'] = 'MAS/우수조달' # 👈 기존 데이터는 무조건 MAS로 태깅
            
            temp_df['업체명'] = temp_df['업체명'].astype(str).apply(lambda x: TARGET_MAP.get(normalize_corp_name(x), None))
            temp_df = temp_df.dropna(subset=['업체명'])
                
            dfs.append(temp_df)
        except Exception: continue
    
    result_df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    if not result_df.empty: result_df = result_df.drop_duplicates()
    return result_df

# --- 4. [신규 데이터] 혁신제품 로드 (data_all.csv 에서 단순 추출) ---
def load_innovation_data():
    try:
        df = None
        for config in [{'encoding':'utf-16','sep':'\t'}, {'encoding':'cp949','sep':','}, {'encoding':'utf-8','sep':','}, {'encoding':'utf-8-sig','sep':','}]:
            try:
                temp_df = pd.read_csv('data_all.csv', encoding=config['encoding'], sep=config['sep'], on_bad_lines='skip', low_memory=False)
                if len(temp_df.columns) > 2:
                    df = temp_df; break
            except: pass
        if df is None: return pd.DataFrame()
        
        df.rename(columns=lambda x: str(x).strip(), inplace=True)
        if '계약업체명' in df.columns: df.rename(columns={'계약업체명': '업체명'}, inplace=True)
        if '품명' in df.columns: df.rename(columns={'품명': '물품분류명'}, inplace=True)
        req_col = '납품요구번호' if '납품요구번호' in df.columns else ('주문번호' if '주문번호' in df.columns else None)
        if not req_col: return pd.DataFrame()

        df[req_col] = df[req_col].fillna('').astype(str).str.replace('nan', '', regex=False).str.replace(r'\.0$', '', regex=True).str.strip()

        if '납품증감금액' in df.columns: df['금액'] = pd.to_numeric(df['납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        elif '합계납품증감금액' in df.columns: df['금액'] = pd.to_numeric(df['합계납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        elif '납품요구금액' in df.columns: df['금액'] = pd.to_numeric(df['납품요구금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        elif '금액' in df.columns: df['금액'] = pd.to_numeric(df['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        else: return pd.DataFrame()

        # 💡 [핵심] '혁신' 이라는 글자가 들어간 계약만 골라낸다!
        stle_col = '계약체결형태명' if '계약체결형태명' in df.columns else ('계약형태' if '계약형태' in df.columns else None)
        if stle_col:
            df = df[df[stle_col].astype(str).str.contains('혁신', na=False)]

        # 날짜에서 월(Month) 추출
        date_col = '납품요구일자' if '납품요구일자' in df.columns else ('접수일자' if '접수일자' in df.columns else None)
        if date_col:
            df['월'] = pd.to_datetime(df[date_col].astype(str).str[:10], errors='coerce').dt.month.fillna(4).astype(int).astype(str) + "월"
        else:
            df['월'] = '4월'

        temp_df = df[['업체명', '물품분류명', '금액', req_col, '월']].copy()
        temp_df.columns = ['업체명', '물품분류명', '금액', '납품요구번호', '월']
        temp_df['구분'] = '혁신제품' # 👈 혁신제품으로 태깅
        
        temp_df['업체명'] = temp_df['업체명'].astype(str).apply(lambda x: TARGET_MAP.get(normalize_corp_name(x), None))
        temp_df = temp_df.dropna(subset=['업체명'])
        
        return temp_df.drop_duplicates()
    except: 
        return pd.DataFrame()

# --- 5. 단순 병합 ---
def get_final_data():
    df_base = load_base_data()
    df_inno = load_innovation_data()
    
    # 💡 무식하고 안전하게 그냥 위아래로 이어붙임
    df_total = pd.concat([df_base, df_inno], ignore_index=True)
    
    # 37개 쓰레기 품목 차단
    if not df_total.empty and '물품분류명' in df_total.columns:
        pattern = '|'.join(EXCLUDE_ITEMS)
        df_total = df_total[~df_total['물품분류명'].astype(str).str.contains(pattern, na=False, regex=True)]
        
    return df_total

df_total = get_final_data()

# --- 6. UI 구성 ---
st.markdown(f"<div class='main-title'>🏆 조달청 통합 실적 분석 v37.0 (기존 완벽 복원 + 혁신 추가)</div>", unsafe_allow_html=True)
col_head1, col_head2 = st.columns([5, 1])
with col_head1:
    st.markdown(f"<div class='update-time'>🕒 데이터: 로컬 파일(기존 1~4월 CSV) + 혁신제품(data_all.csv) 병합 완료!</div>", unsafe_allow_html=True)
with col_head2:
    if st.button("🔄 즉시 새로고침", use_container_width=True):
        st.rerun()

# 사이드바 필터
with st.sidebar:
    st.header("🔍 품목 필터")
    if df_total.empty:
        st.error("데이터를 찾을 수 없습니다. (CSV 파일을 확인해주세요)")
        selected_items = []
    else:
        all_items = sorted(df_total['물품분류명'].dropna().unique())
        col_s1, col_s2 = st.columns(2)
        if col_s1.button("✅ 전체 선택"):
            for item in all_items: st.session_state[f"cb_{item}"] = True
        if col_s2.button("❌ 전체 삭제"):
            for item in all_items: st.session_state[f"cb_{item}"] = False
        st.write("---")
        selected_items = [i for i in all_items if st.checkbox(i, value=st.session_state.get(f"cb_{i}", True), key=f"cb_{i}")]

# --- 7. 메인 대시보드 ---
if not selected_items:
    st.info("👈 분석할 품목을 선택해주세요.")
else:
    df_f = df_total[df_total['물품분류명'].isin(selected_items)].copy()
    
    # 상단 요약 지표
    t_amt = df_f['금액'].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 누적 합계 매출 (1~4월)", f"{t_amt:,.0f} 원")
    c2.metric("💡 혁신제품 매출", f"{df_f[df_f['구분']=='혁신제품']['금액'].sum():,.0f} 원")
    c3.metric("🏢 MAS/우수 매출", f"{df_f[df_f['구분']=='MAS/우수조달']['금액'].sum():,.0f} 원")

    def render_board(df_data, title, dl_key, cmap_color='Blues'):
        st.subheader(title)
        if df_data.empty: 
            st.info("해당 데이터가 없습니다.")
            return
        
        p = pd.pivot_table(df_data, values='금액', index='업체명', columns='월', aggfunc='sum', fill_value=0).reset_index()
        months = [m for m in ['1월', '2월', '3월', '4월'] if m in p.columns]
        p['누적 합계'] = p[months].sum(axis=1)
        p = p[['업체명'] + months + ['누적 합계']].sort_values('누적 합계', ascending=False).reset_index(drop=True)
        p.insert(0, 'No.', range(1, len(p) + 1))
        
        fmt_map = {c: "{:,.0f}" for c in p.columns if c not in ['No.', '업체명']}
        st.dataframe(p.style.format(fmt_map).background_gradient(subset=['누적 합계'], cmap=cmap_color), use_container_width=True, hide_index=True)

        xlsx = BytesIO()
        with pd.ExcelWriter(xlsx, engine='xlsxwriter') as wr:
            p.to_excel(wr, index=False, sheet_name='Ranking')
        st.download_button(f"💾 {title} 엑셀 다운로드", xlsx.getvalue(), f'{dl_key}.xlsx', key=dl_key)

    # 1. 종합 랭킹
    st.write("---")
    inc_inno = st.checkbox("✅ 종합 랭킹에 '혁신제품' 데이터 포함하기", value=True)
    board_total = df_f if inc_inno else df_f[df_f['구분'] != '혁신제품']
    render_board(board_total, "🏆 업체별 종합 조달 랭킹 (MAS + 우수 + 혁신)", "total_ranking", "Blues")

    # 2. MAS/우수 전용
    st.write("---")
    render_board(df_f[df_f['구분'] == 'MAS/우수조달'], "🏢 MAS / 우수제품 전용 실적 랭킹", "mas_ranking", "Greens")

    # 3. 혁신제품 전용
    st.write("---")
    render_board(df_f[df_f['구분'] == '혁신제품'], "💡 혁신제품 전용 실적 랭킹", "inno_ranking", "Oranges")

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim. Data from Base CSVs & data_all.csv</center>", unsafe_allow_html=True)
