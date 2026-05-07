import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import time

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

# --- 2. 분석 대상 업체 및 제외 품목 세팅 (V31 블랙리스트) ---
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

# --- 3. 로컬 데이터 로드 ---
def load_historical_data_raw():
    file_month_map = {'data.csv': '1월', 'data02.csv': '2월', 'data03.csv': '3월', 'data04.csv': '4월'}
    dfs = []
    for file, target_month in file_month_map.items():
        try:
            df = None
            for config in [{'encoding':'utf-16','sep':'\t'}, {'encoding':'cp949','sep':','}, {'encoding':'utf-8','sep':','}, {'encoding':'utf-8-sig','sep':','}]:
                try:
                    temp_df = pd.read_csv(file, encoding=config['encoding'], sep=config['sep'], on_bad_lines='skip', low_memory=False)
                    if len(temp_df.columns) > 2: df = temp_df; break
                except: pass
            if df is None: continue
            df.rename(columns=lambda x: str(x).strip(), inplace=True)
            if '계약업체명' in df.columns and '업체명' not in df.columns: df.rename(columns={'계약업체명': '업체명'}, inplace=True)
            if '품명' in df.columns and '물품분류명' not in df.columns: df.rename(columns={'품명': '물품분류명'}, inplace=True)
            req_col = '납품요구번호' if '납품요구번호' in df.columns else ('주문번호' if '주문번호' in df.columns else None)
            if not req_col or '물품분류명' not in df.columns: continue 

            df[req_col] = df[req_col].fillna('').astype(str).str.replace('nan', '', regex=False).str.replace(r'\.0$', '', regex=True).str.strip()

            calc_amt = pd.Series(0.0, index=df.index)
            for col in ['납품요구금액', '금액', '납품금액']:
                if col in df.columns:
                    base_amt = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                    calc_amt = calc_amt.where(calc_amt != 0, base_amt)
            for col in ['납품증감금액', '합계납품증감금액']:
                if col in df.columns:
                    mod_amt = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                    mask = mod_amt != 0
                    calc_amt.loc[mask] = mod_amt[mask]
            
            df['최종금액'] = calc_amt
            temp_df = df[['업체명', '물품분류명', '최종금액', req_col]].copy()
            temp_df.columns = ['업체명', '물품분류명', '금액', '납품요구번호']
            temp_df['월'] = target_month
            temp_df['업체명'] = temp_df['업체명'].astype(str).apply(lambda x: TARGET_MAP.get(normalize_corp_name(x), None))
            temp_df = temp_df.dropna(subset=['업체명'])
            
            if 'MAS여부' in df.columns: temp_df['MAS여부'] = df['MAS여부'].fillna('N').astype(str).str.strip().str.upper()
            else: temp_df['MAS여부'] = 'Y' 
                
            dfs.append(temp_df)
        except Exception: continue
    
    result_df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    return result_df.drop_duplicates() if not result_df.empty else result_df

# --- 4. 실시간 API 수집 (💡 과거 해법 100% 적용!) ---
def fetch_api_data_raw():
    now = get_now_kst()
    RAW_KEY = "15bc460106a7359afdd54c91410a8dd94c17076ba2aa7d4308cfb8e07e9ce5ae"
    BASE_URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
    
    # 💡 [핵심 1] 쓸데없는 1일 데이터 버리고 정확히 4월 20일부터만 핀포인트 조회! (서버 부하 대폭 감소)
    bgn_date = "20260420"
    end_date = now.strftime('%Y%m%d')
    
    all_new_data = []
    added_count = 0
    page_no = 1
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}

    while True:
        req_url = f"{BASE_URL}?serviceKey={RAW_KEY}&numOfRows=100&pageNo={page_no}&inqryDiv=1&inqryBgnDate={bgn_date}&inqryEndDate={end_date}"
        
        # 💡 [핵심 2] 과거 550페이지 실패를 극복했던 "지독한 좀비 모드 (Exponential Backoff)" 부활!
        success = False
        res = None
        for retry in range(3):
            try:
                res = requests.get(req_url, headers=headers, timeout=15)
                if res.status_code == 200:
                    success = True
                    break
                else:
                    time.sleep(2 ** retry) # 1초, 2초, 4초 대기 후 재시도
            except Exception:
                time.sleep(2 ** retry)
        
        if not success or not res: break # 3번 다 실패하면 그제서야 눈물을 머금고 포기
        
        try:
            root = ET.fromstring(res.content)
            result_code = root.findtext('.//resultCode')
            if result_code not in ['00', '0']: break

            total_count = int(root.findtext('.//totalCount') or 0)
            if total_count == 0: break

            items = root.findall('.//item')
            if not items: break
            
            for item in items:
                # 💡 [핵심 3] 네 말대로 어차피 3자단가 계약이니 조건문 다 철거! 타겟 업체면 무조건 쓸어담음.
                norm_corp = normalize_corp_name(item.findtext('corpNm', ''))
                
                if norm_corp in TARGET_MAP:
                    date_val = (item.findtext('dlvrReqRcptDate') or item.findtext('dlvrReqDate', '')).replace('-', '')[:8]
                    api_month_str = f"{int(date_val[4:6])}월" if len(date_val) >= 6 else "4월"
                    
                    amt_str = item.findtext('dlvrReqAmt', '0')
                    if not amt_str or str(amt_str).strip() == '': amt_str = '0'
                    
                    req_no = item.findtext('dlvrReqNo', '').strip()
                    item_name = item.findtext('prdctClsfcNm', '') or item.findtext('dtilPrdctClsfcNm', '')
                    
                    all_new_data.append({
                        '업체명': TARGET_MAP[norm_corp], 
                        '물품분류명': item_name, 
                        '금액': float(amt_str), 
                        '납품요구번호': req_no if req_no else f'API_{time.time()}', 
                        '월': api_month_str,
                        'MAS여부': 'Y' 
                    })
                    added_count += 1
            
            if page_no * 100 >= total_count: break
            page_no += 1
            
        except Exception: break

    if all_new_data:
        return pd.DataFrame(all_new_data), f"🟢 실시간 데이터 수집 성공! (신규 {added_count}건)"
    return pd.DataFrame(), f"🔵 최신화 완료 (4/20 이후 추가 실적 없음)"

# --- 5. 데이터 통합 및 정제 ---
def get_processed_data_raw():
    df_hist = load_historical_data_raw()
    df_api, api_msg = fetch_api_data_raw()
    
    if not df_api.empty and not df_hist.empty:
        existing = set(df_hist['납품요구번호'].unique())
        df_api_clean = df_api[~df_api['납품요구번호'].isin(existing)]
        df_total = pd.concat([df_hist, df_api_clean], ignore_index=True)
    else:
        df_total = df_api if not df_api.empty else df_hist

    if not df_total.empty:
        pattern = '|'.join(EXCLUDE_ITEMS)
        df_total = df_total[~df_total['물품분류명'].astype(str).str.contains(pattern, na=False, regex=True)]
    return df_total, api_msg

df_total, api_msg = get_processed_data_raw()

# --- 6. UI ---
st.markdown(f"<div class='main-title'>🏆 조달청 통합 대시보드 v58.0 (과거 해법 완벽 적용)</div>", unsafe_allow_html=True)
col_head1, col_head2 = st.columns([5, 1])
with col_head1: st.markdown(f"<div class='update-time'>🕒 상태: {api_msg}</div>", unsafe_allow_html=True)
with col_head2: 
    if st.button("🔄 즉시 새로고침", use_container_width=True): st.rerun()

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

# --- 7. 메인 화면 ---
if selected_items:
    df_f = df_total[df_total['물품분류명'].isin(selected_items)].copy()
    def get_quarter(m_str):
        m = int(m_str.replace('월',''))
        return '1분기' if m<=3 else ('2분기' if m<=6 else ('3분기' if m<=9 else '4분기'))
    df_f['분기'] = df_f['월'].apply(get_quarter)
    
    t_cnt = df_f['납품요구번호'].nunique()
    t_amt = df_f['금액'].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 누적 매출액", f"{t_amt:,.0f} 원")
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
        with pd.ExcelWriter(xlsx, engine='xlsxwriter') as wr: final.to_excel(wr, index=False, sheet_name='실적랭킹')
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
    render_ranking_board(board_df_mas, "🏢 MAS 계약 전용 실적 랭킹", show_cnt, 'sort_mas', 'dl_mas', 'Greens')

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim. Data from Public Data Portal.</center>", unsafe_allow_html=True)
