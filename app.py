import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import time
import urllib3

# SSL 경고 숨기기
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 1. 기본 설정 및 KST 시계 ---
st.set_page_config(page_title="조달청 실적 분석 대시보드", layout="wide")

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

EXCLUDE_ITEMS = [
    "무인교통감시장치", "교통관제시스템", "구내방송장치", "마이크로폰", "마이크스탠드", 
    "무선마이크장치", "버스승강장", "보행자안전차단기", "산업제어소프트웨어", "생체인식장비", 
    "세탁물건조기", "소프트웨어유지및지원서비스", "스트로보또는경고등", "스피커스탠드", 
    "스피커제어유닛", "업소용세탁기", "오디오모니터", "오디오믹서", "증폭기결합", "오디오앰프", 
    "오디오장비커넥터및스테이지박스", "이퀄라이저", "정보화교육서비스", "주차관제장치", 
    "차량번호판독기", "출입통제시스템", "태양전지조절기", "파일시스템소프트웨어", 
    "패키지소프트웨어개발및도입서비스", "플러그용잭", "해석또는과학소프트웨어", 
    "화재경보장치", "콤팩트디스크재생또는녹음기", "리튬전지", "리셉터클", "라디오튜너"
]

def normalize_corp_name(name):
    if not name: return ""
    return name.replace('주식회사', '').replace('(주)', '').replace(' ', '').strip()

TARGET_MAP = {normalize_corp_name(comp): comp for comp in TARGET_COMPANIES}

# --- 3. 통합 파이프라인 (🔥 오류 수정된 퍼펙트 밸런스 로직) ---
def unified_data_parser(df_raw, target_month=None):
    if df_raw is None or df_raw.empty: return pd.DataFrame()
    df = df_raw.copy()

    for req_col in ['업체명', '물품분류명', '납품요구번호']:
        if req_col not in df.columns: df[req_col] = ''

    if 'corpNm' in df.columns: df['업체명'] = df['corpNm']
    elif '계약업체명' in df.columns: df['업체명'] = df['계약업체명']
    
    if 'prdctClsfcNm' in df.columns: df['물품분류명'] = df['prdctClsfcNm']
    elif 'dtilPrdctClsfcNm' in df.columns: df['물품분류명'] = df['dtilPrdctClsfcNm']
    elif '품명' in df.columns: df['물품분류명'] = df['품명']
    
    if 'dlvrReqNo' in df.columns: df['납품요구번호'] = df['dlvrReqNo']
    elif '주문번호' in df.columns: df['납품요구번호'] = df['주문번호']
    
    if 'dlvrReqRcptDate' in df.columns: df['일자'] = df['dlvrReqRcptDate']
    elif 'dlvrReqDate' in df.columns: df['일자'] = df['dlvrReqDate']
    elif '납품요구접수일자' in df.columns: df['일자'] = df['납품요구접수일자']

    df['업체명'] = df['업체명'].astype(str).apply(lambda x: TARGET_MAP.get(normalize_corp_name(x), None))
    df = df.dropna(subset=['업체명'])
    if df.empty: return pd.DataFrame()

    df['납품요구번호'] = df['납품요구번호'].fillna('').astype(str).str.replace('nan', '', regex=False).str.replace(r'\.0$', '', regex=True).str.strip()

    calc_amt = pd.Series(0.0, index=df.index)
    for col in ['납품요구금액', '금액', '납품금액', 'dlvrReqAmt']:
        if col in df.columns:
            base_amt = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            calc_amt = calc_amt.where(calc_amt != 0, base_amt)

    for col in ['납품증감금액', '합계납품증감금액', 'dlvrIemRducAmt', 'chgDlvrReqAmt']:
        if col in df.columns:
            mod_amt = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            mask = mod_amt != 0
            calc_amt.loc[mask] = mod_amt[mask]

    df['금액'] = calc_amt

    if target_month: df['월'] = target_month
    else:
        if '일자' in df.columns:
            date_clean = df['일자'].astype(str).str.replace('-', '').str.replace('.', '').str.strip().str[:8]
            df['월'] = date_clean.str[4:6].apply(lambda x: f"{int(x)}월" if str(x).isdigit() else "4월")
        else: df['월'] = "5월"

    # 💡 [핵심] API 실시간 데이터를 살리는 MAS 분리 엔진
    df['MAS여부'] = 'N' 
    df['계약종류_상세'] = '기타/미상'
    
    possible_cols = ['계약형태', '계약방법', '계약구분', '계약체결형태명', 'cntrctCnclsStleNm', 'cntrctMthdNm']
    
    for col in possible_cols:
        if col in df.columns:
            # 1. 1차 포용: '제3자단가', '다수공급자', 'MAS'는 무조건 일단 MAS(Y)로 받아들임! (API 실시간 데이터 복구!)
            mas_mask = df[col].astype(str).str.contains('다수공급자|MAS|mas|제3자', case=False, na=False, regex=True)
            df.loc[mas_mask, 'MAS여부'] = 'Y'
            df.loc[mas_mask, '계약종류_상세'] = 'MAS 및 제3자단가'
            
            # 2. 2차 철퇴 (우선순위 덮어쓰기): 단, 그 문장 안에 '우수'나 '혁신'이 있으면 MAS 방에서 쫓아냄! (세오 19억 해결!)
            usu_mask = df[col].astype(str).str.contains('우수|혁신', na=False, regex=True)
            df.loc[usu_mask, 'MAS여부'] = 'N'
            df.loc[usu_mask, '계약종류_상세'] = '우수조달/혁신'
            
            # 3. 총액/일반경쟁 등
            gen_mask = df[col].astype(str).str.contains('총액|일반', na=False, regex=True)
            df.loc[gen_mask, 'MAS여부'] = 'N'
            df.loc[gen_mask, '계약종류_상세'] = '총액/일반경쟁'

    return df[['업체명', '물품분류명', '금액', '납품요구번호', '월', 'MAS여부', '계약종류_상세']]

# 💡 엑셀 데이터 캐싱 (1시간)
@st.cache_data(ttl=3600)
def load_historical_data_raw():
    file_month_map = {'data.csv': '1월', 'data02.csv': '2월', 'data03.csv': '3월', 'data04.csv': '4월'}
    dfs = []
    for file, target_month in file_month_map.items():
        df = None
        for config in [{'encoding':'utf-16','sep':'\t'}, {'encoding':'cp949','sep':','}, {'encoding':'utf-8','sep':','}, {'encoding':'utf-8-sig','sep':','}]:
            try:
                temp_df = pd.read_csv(file, encoding=config['encoding'], sep=config['sep'], on_bad_lines='skip', low_memory=False)
                if len(temp_df.columns) > 2: df = temp_df; break
            except: pass
        if df is not None:
            clean_df = unified_data_parser(df, target_month=target_month)
            if not clean_df.empty: dfs.append(clean_df)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# 💡 API 통신 캐싱 (10분)
@st.cache_data(ttl=600)
def fetch_api_data_raw():
    now = get_now_kst()
    safe_end_date = now - timedelta(days=2) 
    
    RAW_KEY = "d6a789992823ed502e65039680f537b3db0da665bcb00e41330ce78a7c07f466"
    BASE_URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
    headers = {'User-Agent': 'Mozilla/5.0'}

    date_ranges = [("20260420", "20260430"), ("20260501", safe_end_date.strftime("%Y%m%d"))]
    all_new_data = []

    for bgn, end in date_ranges:
        if bgn > end: continue
        page_no = 1
        
        while True:
            req_url = f"{BASE_URL}?serviceKey={RAW_KEY}&numOfRows=500&pageNo={page_no}&inqryDiv=1&inqryBgnDate={bgn}&inqryEndDate={end}"
            
            success = False
            for attempt in range(3): 
                try:
                    res = requests.get(req_url, headers=headers, timeout=45, verify=False)
                    if res.status_code == 200:
                        success = True; break 
                    elif res.status_code == 429:
                        if attempt == 2: return pd.DataFrame(), f"🚨 일일 트래픽 한도 초과! (내일 시도해주세요)"
                        time.sleep(5) 
                    else: time.sleep(3) 
                except: time.sleep(3)
                    
            if not success: return pd.DataFrame(), f"🚨 통신 불안정 (잠시 후 새로고침 하세요)"
            
            try:
                root = ET.fromstring(res.content)
                if root.findtext('.//resultCode') not in ['00', '0']: return pd.DataFrame(), f"🚨 API 거부: {root.findtext('.//resultMsg')}"
                
                total_count_str = root.findtext('.//totalCount')
                if not total_count_str or int(total_count_str) == 0: break
                
                items = root.findall('.//item')
                if not items: break
                
                for item in items: all_new_data.append({child.tag: child.text for child in item})
                
                if page_no * 500 >= int(total_count_str): break
                page_no += 1
                time.sleep(2) 
            except Exception as e: return pd.DataFrame(), f"🚨 파싱 에러: {str(e)}"

    if not all_new_data: return pd.DataFrame(), f"🔵 4/20 이후 신규 실적 없음"
        
    try:
        df_api_raw = pd.DataFrame(all_new_data)
        raw_count = len(df_api_raw)
        df_api_clean = unified_data_parser(df_api_raw)
        if df_api_clean.empty: return pd.DataFrame(), f"🔵 신규 실적 없음"
        return df_api_clean, f"🟢 실시간 데이터 수집 완료! (4/20 이후 신규 {len(df_api_clean)}건 완벽 추출)"
    except Exception as e: return pd.DataFrame(), f"🚨 파이프라인 에러: {str(e)}"

def get_processed_data_raw():
    df_hist = load_historical_data_raw()
    with st.spinner('⏳ 4월 20일 이후 실시간 데이터를 스캔 중입니다... (약 30~60초)'):
        df_api, api_msg = fetch_api_data_raw()
    
    if not df_api.empty and not df_hist.empty:
        existing = set(df_hist['납품요구번호'].unique())
        df_api_clean = df_api[~df_api['납품요구번호'].isin(existing)]
        df_total = pd.concat([df_hist, df_api_clean], ignore_index=True)
    else: df_total = df_api if not df_api.empty else df_hist

    if not df_total.empty:
        pattern = '|'.join(EXCLUDE_ITEMS)
        df_total = df_total[~df_total['물품분류명'].astype(str).str.contains(pattern, na=False, regex=True)]
    return df_total, api_msg

df_total, api_msg = get_processed_data_raw()

# --- 7. UI ---
st.markdown(f"<div class='main-title'>🏆 조달청 통합 대시보드 v81.0 (퍼펙트 밸런스판)</div>", unsafe_allow_html=True)
col_head1, col_head2 = st.columns([5, 2])
with col_head1: st.markdown(f"<div class='update-time'>🕒 상태: {api_msg}</div>", unsafe_allow_html=True)
with col_head2: 
    if st.button("🔄 즉시 새로고침 (메모리 완전 초기화)", use_container_width=True): 
        st.cache_data.clear() 
        st.rerun()

with st.sidebar:
    st.header("🔍 품목 상세 필터")
    if df_total.empty:
        st.error("데이터 없음")
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

# --- 8. 메인 화면 ---
if selected_items:
    df_f = df_total[df_total['물품분류명'].isin(selected_items)].copy()
    def get_quarter(m_str):
        m = int(m_str.replace('월',''))
        return '1분기' if m<=3 else ('2분기' if m<=6 else ('3분기' if m<=9 else '4분기'))
    df_f['분기'] = df_f['월'].apply(get_quarter)
    
    with st.expander("🛠️ [데이터 검증] (주)세오 19억의 진실 (계약 종류별 해부)", expanded=True):
        seo_df = df_f[df_f['업체명'] == '주식회사 세오']
        if not seo_df.empty:
            st.markdown("조달청 원본 데이터에서 세오의 실적을 **계약 종류별**로 쪼개본 결과입니다.")
            seo_sum = seo_df.groupby('계약종류_상세')['금액'].sum().reset_index()
            st.dataframe(seo_sum.style.format({'금액': '{:,.0f} 원'}), hide_index=True)
        else:
            st.info("세오의 실적 데이터가 없습니다.")
            
    t_cnt = df_f['납품요구번호'].nunique()
    t_amt = df_f['금액'].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 누적 매출액 (전체)", f"{t_amt:,.0f} 원")
    c2.metric("📝 총 계약 건수", f"{t_cnt:,} 건")
    c3.metric("📊 건당 평균 실적", f"{(t_amt/t_cnt if t_cnt>0 else 0):,.0f} 원")
    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("📈 실적 추이")
        trend_view = st.radio("조회 기준", ["월별", "분기별"], horizontal=True, label_visibility="collapsed")
        time_col = '월' if trend_view == '월별' else '분기'
        m_df = df_f.groupby(time_col).agg(금액=('금액', 'sum'), 건수=('납품요구번호', 'nunique')).reset_index()
        
        if trend_view == '월별':
            m_df['sort_key'] = m_df['월'].str.replace('월', '').astype(int)
            m_df = m_df.sort_values('sort_key').drop(columns=['sort_key'])
        else: m_df = m_df.sort_values('분기')
            
        fig = go.Figure()
        fig.add_trace(go.Bar(x=m_df[time_col], y=m_df['금액'], name='매출액', marker_color='#3b82f6', yaxis='y1'))
        fig.add_trace(go.Scatter(x=m_df[time_col], y=m_df['건수'], name='건수', mode='lines+markers+text', text=m_df['건수'], textposition='top center', marker_color='#ef4444', yaxis='y2'))
        fig.update_layout(yaxis=dict(title='매출액', showgrid=False), yaxis2=dict(title='건수', overlaying='y', side='right', showgrid=False), legend=dict(orientation="h", y=1.15, x=1), margin=dict(t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)
        
    with col_b:
        st.subheader("🍩 시장 점유율")
        pie_options = ["총합계 (전체)", "1분기", "2분기", "3분기", "4분기"] + sorted(df_f['월'].unique(), key=lambda x: int(x.replace('월','')))
        pie_view = st.selectbox("분석 기간 선택", pie_options, label_visibility="collapsed")
        
        if pie_view == "총합계 (전체)": pie_df = df_f
        elif "분기" in pie_view: pie_df = df_f[df_f['분기'] == pie_view]
        else: pie_df = df_f[df_f['월'] == pie_view]
        
        if pie_df.empty: st.info(f"선택하신 기간의 실적 데이터가 없습니다.")
        else:
            top10_pie = pie_df.groupby('업체명')['금액'].sum().nlargest(10).reset_index()
            fig_pie = px.pie(top10_pie, names='업체명', values='금액', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(showlegend=False, margin=dict(t=20, b=0))
            st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")

    def render_ranking_board(df_data, title, show_count_col, sort_key, dl_key, cmap_color='Blues'):
        st.subheader(title)
        ctrl_col1, ctrl_col2 = st.columns([2.4, 1])
        
        if df_data.empty: return st.warning("해당 조건의 실적이 없습니다.")
            
        p_amt = pd.pivot_table(df_data, values='금액', index='업체명', columns='월', aggfunc='sum', fill_value=0).reset_index()
        p_cnt = pd.pivot_table(df_data, values='납품요구번호', index='업체명', columns='월', aggfunc='nunique', fill_value=0).reset_index()
        
        all_months = [f"{m}월" for m in range(1, 13)]
        for m in all_months:
            if m not in p_amt.columns: p_amt[m] = 0
            if m not in p_cnt.columns: p_cnt[m] = 0
            
        q1 = ['1월', '2월', '3월']; q2 = ['4월', '5월', '6월']
        q3 = ['7월', '8월', '9월']; q4 = ['10월', '11월', '12월']
        
        p_amt['1분기 합계'] = p_amt[q1].sum(axis=1); p_amt['2분기 합계'] = p_amt[q2].sum(axis=1)
        p_amt['3분기 합계'] = p_amt[q3].sum(axis=1); p_amt['4분기 합계'] = p_amt[q4].sum(axis=1)
        p_amt['전체 합계'] = p_amt[all_months].sum(axis=1)
        
        p_cnt['1분기(건)'] = p_cnt[q1].sum(axis=1); p_cnt['2분기(건)'] = p_cnt[q2].sum(axis=1)
        p_cnt['3분기(건)'] = p_cnt[q3].sum(axis=1); p_cnt['4분기(건)'] = p_cnt[q4].sum(axis=1)
        p_cnt['전체 합계(건)'] = p_cnt[all_months].sum(axis=1)
        p_cnt.rename(columns={m: f'{m}(건)' for m in all_months}, inplace=True)
        
        final = pd.merge(p_amt, p_cnt, on='업체명', how='outer').fillna(0)
        
        disp_cols = ['업체명']
        for q_m, q_a, q_c in [(q1, '1분기 합계', '1분기(건)'), (q2, '2분기 합계', '2분기(건)'), (q3, '3분기 합계', '3분기(건)'), (q4, '4분기 합계', '4분기(건)')]:
            for m in q_m:
                disp_cols.append(m)
                if show_count_col: disp_cols.append(f'{m}(건)')
            disp_cols.append(q_a)
            if show_count_col: disp_cols.append(q_c)
        disp_cols.append('전체 합계')
        if show_count_col: disp_cols.append('전체 합계(건)')
            
        final = final[disp_cols]
        
        with ctrl_col2:
            sort_options = [c for c in disp_cols if c != '업체명']
            sort_target = st.selectbox("⬇️ 정렬 기준", options=sort_options, index=sort_options.index('전체 합계'), label_visibility="collapsed", key=sort_key)
            
        final = final.sort_values(sort_target, ascending=False).reset_index(drop=True)
        final.insert(0, '랭킹 No.', range(1, len(final) + 1))
        
        fmt_map = {c: "{:,.0f}" for c in final.columns if c not in ['랭킹 No.', '업체명']}
        styled = final.style.format(fmt_map)
        styled = styled.set_properties(subset=['업체명'], **{'background-color': 'rgba(128, 128, 128, 0.1)', 'font-weight': 'bold'})
        
        month_cols = [c for c in final.columns if '월' in c and '(' not in c]
        q_amt_cols = [c for c in final.columns if '분기 합계' in c]
        cnt_cols = [c for c in final.columns if '(건)' in c]
        
        styled = styled.set_properties(subset=month_cols, **{'background-color': 'rgba(54, 162, 235, 0.05)'})
        styled = styled.set_properties(subset=q_amt_cols, **{'background-color': 'rgba(255, 159, 64, 0.1)', 'font-weight': 'bold'})
        styled = styled.set_properties(subset=['전체 합계'], **{'background-color': 'rgba(255, 99, 132, 0.1)', 'font-weight': 'bold', 'color':'#1e3a8a'})

        if show_count_col: styled = styled.set_properties(subset=cnt_cols, **{'background-color': 'rgba(76, 175, 80, 0.05)'})
        styled = styled.background_gradient(subset=[sort_target], cmap=cmap_color)
        
        st.dataframe(styled, use_container_width=True, hide_index=True, height=600)

        xlsx = BytesIO()
        with pd.ExcelWriter(xlsx, engine='xlsxwriter') as wr:
            final.to_excel(wr, index=False, sheet_name='실적랭킹')
        st.download_button("💾 엑셀 다운로드", xlsx.getvalue(), f'조달랭킹_{dl_key}_{get_now_kst().strftime("%Y%m%d")}.xlsx', key=dl_key)

    st.subheader("⚙️ 랭킹 보드 컨트롤")
    ctrl_col_a, ctrl_col_b = st.columns(2)
    with ctrl_col_a: show_cnt = st.checkbox("📝 월/분기별 계약건수 함께 보기", value=False)
    with ctrl_col_b: include_mas = st.checkbox("🏢 종합 랭킹에 MAS 계약 포함 (해제 시 '우수조달'만 표시)", value=True)
    st.markdown("---")

    board_df_total = df_f.copy()
    if not include_mas: board_df_total = board_df_total[board_df_total['MAS여부'] == 'N']
    render_ranking_board(board_df_total, "🏆 업체별 종합 실적 랭킹 (우수조달 + MAS 전체)", show_cnt, 'sort_total', 'dl_total', 'Blues')

    st.markdown("<br><br>", unsafe_allow_html=True)
    board_df_mas = df_f[df_f['MAS여부'] == 'Y'].copy()
    render_ranking_board(board_df_mas, "🏢 순수 MAS(다수공급자) 전용 실적 랭킹", show_cnt, 'sort_mas', 'dl_mas', 'Greens')

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim. Data from Public Data Portal.</center>", unsafe_allow_html=True)
