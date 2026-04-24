import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import urllib.parse
import time

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

# --- 2. 분석 대상 업체 ---
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

def normalize_corp_name(name):
    if not name: return ""
    return name.replace('주식회사', '').replace('(주)', '').replace(' ', '').strip()

TARGET_MAP = {normalize_corp_name(comp): comp for comp in TARGET_COMPANIES}

# --- 3. [로컬 데이터] ---
@st.cache_data(ttl=3600)
def load_historical_data():
    file_month_map = {
        'data.csv': '1월', 'data02.csv': '2월', 'data02.cvs': '2월', 
        'data03.csv': '3월', 'data04.csv': '4월'
    }
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

            if '납품증감금액' in df.columns: df['금액'] = pd.to_numeric(df['납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '합계납품증감금액' in df.columns: df['금액'] = pd.to_numeric(df['합계납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '납품요구금액' in df.columns: df['금액'] = pd.to_numeric(df['납품요구금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '금액' in df.columns: df['금액'] = pd.to_numeric(df['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            else: continue
            
            temp_df = df[['업체명', '물품분류명', '금액', req_col]].copy()
            temp_df.columns = ['업체명', '물품분류명', '금액', '납품요구번호']
            temp_df['월'] = target_month
            
            temp_df['업체명'] = temp_df['업체명'].astype(str).apply(lambda x: TARGET_MAP.get(normalize_corp_name(x), None))
            temp_df = temp_df.dropna(subset=['업체명'])
            
            if 'MAS여부' in df.columns:
                temp_df['MAS여부'] = df['MAS여부'].fillna('N').astype(str).str.strip().str.upper()
            else:
                temp_df['MAS여부'] = 'Y' 
                
            dfs.append(temp_df)
        except Exception: continue
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# --- 4. [실시간 API] V13 끝장판 엔진 (자동 탐색 + 스텔스) ---
def update_realtime_data():
    if 'api_df' not in st.session_state: st.session_state.api_df = pd.DataFrame()
    if 'last_update' not in st.session_state: st.session_state.last_update = "업데이트 전"
    if 'retry_time' not in st.session_state: st.session_state.retry_time = None
    
    now = get_now_kst()
    if st.session_state.retry_time and now < st.session_state.retry_time:
        return st.session_state.api_df, f"⏳ 대기 중 (다음 시도 KST: {st.session_state.retry_time.strftime('%H:%M:%S')})"
    
    try:
        RAW_KEY = "c1b379f7734c7d624ddefea07510eae71b6e12c5fb89970319d76c5ae8db5248"
        API_KEY = urllib.parse.unquote(RAW_KEY)
        
        # 날짜 세팅 (무조건 어제까지만, D-1 원칙)
        bgn_date = now.strftime('%Y') + '0420'
        yesterday = now - timedelta(days=1)
        end_date = yesterday.strftime('%Y%m%d')
        
        # 💡 [방어 1] 브라우저 위장 (조달청 WAF 방화벽 우회)
        HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        # 💡 [방어 2] 조달청 서버 변덕 대비 다중 경로 자동 탐색 맵
        api_configs = [
            {"url": "http://apis.data.go.kr/1230000/ShoppingMallPrdctInfoService05/getDlvrReqInfoList", "bgn": "inqryBgnDt", "end": "inqryEndDt", "name": "V5신형"},
            {"url": "http://apis.data.go.kr/1230000/ShoppingMallPrdctInfoService05/getDlvrReqInfoList", "bgn": "inqryBgnDate", "end": "inqryEndDate", "name": "V5구형"},
            {"url": "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList", "bgn": "inqryBgnDate", "end": "inqryEndDate", "name": "V1구형"}
        ]
        
        working_config = None
        
        # 0.1초만에 살아있는 서버 찾기
        for config in api_configs:
            test_params = {
                'serviceKey': API_KEY, 'numOfRows': '10', 'pageNo': '1', 'inqryDiv': '1',
                config['bgn']: bgn_date, config['end']: end_date
            }
            # 파이썬 인코딩 개입을 막는 수동 URL 조립
            qs = "&".join([f"{k}={v}" for k, v in test_params.items()])
            test_url = f"{config['url']}?{qs}"
            
            try:
                test_res = requests.get(test_url, headers=HEADERS, timeout=10)
                if test_res.status_code == 200:
                    root = ET.fromstring(test_res.content)
                    if root.findtext('.//resultCode') in ['00', '0']:
                        working_config = config
                        break
            except: pass
            
        # 살아있는 경로를 못 찾으면 방화벽이 아예 차단한 것임
        if not working_config:
            st.session_state.retry_time = now + timedelta(minutes=10)
            return pd.DataFrame(), "🚨 모든 API 경로 차단됨 (조달청 방화벽 점검 중, 10분 후 재시도)"

        # 찾은 경로로 진짜 데이터 수집 시작
        all_new_data = []
        page_no = 1
        raw_scanned_count = 0
        total_count = 0
        
        while True:
            params = {
                'serviceKey': API_KEY, 'numOfRows': '100', 'pageNo': str(page_no), 'inqryDiv': '1',
                working_config['bgn']: bgn_date, working_config['end']: end_date
            }
            qs = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{working_config['url']}?{qs}"
            
            # 강철 멘탈 재시도 로직
            success = False
            for attempt in range(4):
                try:
                    res = requests.get(full_url, headers=HEADERS, timeout=15)
                    if res.status_code == 200:
                        success = True; break
                    else: time.sleep(2 ** attempt)
                except: time.sleep(2 ** attempt)
                    
            if not success:
                break # 실패 시 있는 데까지만 저장하고 탈출

            root = ET.fromstring(res.content)
            if root.findtext('.//resultCode') not in ['00', '0']:
                break

            if page_no == 1:
                tc_str = root.findtext('.//totalCount')
                if tc_str: total_count = int(tc_str)

            if total_count == 0: break

            items = root.findall('.//item')
            if not items: break
            
            for item in items:
                raw_scanned_count += 1
                cntrct_stle = item.findtext('cntrctCnclsStleNm', '')
                if '제3자단가' not in cntrct_stle: continue

                raw_corp = item.findtext('corpNm', '')
                norm_corp = normalize_corp_name(raw_corp)
                
                if norm_corp in TARGET_MAP:
                    matched_corp_name = TARGET_MAP[norm_corp]
                    all_new_data.append({
                        '업체명': matched_corp_name, 
                        '물품분류명': item.findtext('prdctClsfcNm', ''), 
                        '금액': float(item.findtext('dlvrReqAmt', 0)), 
                        '납품요구번호': item.findtext('dlvrReqNo', f'API_{now.timestamp()}'), 
                        '월': '4월',
                        'MAS여부': item.findtext('masYn', 'Y').strip().upper() 
                    })
            
            if page_no * 100 >= total_count: break
            page_no += 1

        st.session_state.last_update = now.strftime('%H:%M:%S')
        if all_new_data:
            st.session_state.api_df = pd.DataFrame(all_new_data)
            return st.session_state.api_df, f"🟢 [{working_config['name']} 접속] 전국 {total_count:,}건 중 타겟 {len(all_new_data)}건 수집 완료!"
        
        return pd.DataFrame(), f"🔵 [{working_config['name']} 접속] 전국 {total_count:,}건 스캔 (타겟 실적 0건)"
        
    except Exception as e:
        st.session_state.retry_time = now + timedelta(minutes=15)
        return pd.DataFrame(), "⚠️ 예기치 않은 통신 오류 (15분 뒤 재시도)"

# --- 5. 데이터 통합 실행 ---
df_hist = load_historical_data()
df_api, api_msg = update_realtime_data()
df_total = pd.concat([df_hist, df_api], ignore_index=True) if not df_api.empty else df_hist.copy()

if not df_total.empty and '물품분류명' in df_total.columns:
    df_total = df_total[~df_total['물품분류명'].astype(str).str.contains('무인교통감시장치', na=False)]

st.markdown(f"<div class='main-title'>🏆 조달청 제3자단가계약 통합 대시보드 v13.0</div>", unsafe_allow_html=True)
st.markdown(f"<div class='update-time'>🕒 마지막 업데이트(KST): {st.session_state.last_update} | 상태: {api_msg}</div>", unsafe_allow_html=True)

# --- 6. 사이드바 필터 ---
with st.sidebar:
    st.header("🔍 품목 상세 필터")
    if df_total.empty:
        st.error("⚠️ 데이터를 찾을 수 없습니다.")
        selected_items = []
    else:
        all_items = sorted(df_total['물품분류명'].dropna().unique())
        col_s1, col_s2 = st.columns(2)
        if col_s1.button("✅ 전체 품목 선택"):
            for item in all_items: st.session_state[f"cb_{item}"] = True
        if col_s2.button("❌ 전체 품목 삭제"):
            for item in all_items: st.session_state[f"cb_{item}"] = False

        st.write("---")
        selected_items = []
        for item in all_items:
            cb_key = f"cb_{item}"
            if cb_key not in st.session_state: st.session_state[cb_key] = True
            if st.checkbox(item, key=cb_key): selected_items.append(item)

# --- 7. 메인 화면 ---
if not selected_items:
    st.info("👈 왼쪽 사이드바에서 분석할 품목을 1개 이상 선택해주세요.")
else:
    df_f = df_total[df_total['물품분류명'].isin(selected_items)].copy()
    df_f['분기'] = df_f['월'].apply(lambda x: '1분기' if x in ['1월', '2월', '3월'] else '2분기')
    df_f['총계'] = '총합계'
    
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
        trend_view = st.radio("조회 기준", ["월별", "분기별", "총합계"], horizontal=True, label_visibility="collapsed")
        time_col = '월' if trend_view == '월별' else ('분기' if trend_view == '분기별' else '총계')
        m_df = df_f.groupby(time_col).agg(금액=('금액', 'sum'), 건수=('납품요구번호', 'nunique')).reset_index()
        if trend_view == '월별': m_df = m_df.sort_values('월')
        elif trend_view == '분기별': m_df = m_df.sort_values('분기')
        fig = go.Figure()
        fig.add_trace(go.Bar(x=m_df[time_col], y=m_df['금액'], name='매출액', marker_color='#3b82f6', yaxis='y1'))
        fig.add_trace(go.Scatter(x=m_df[time_col], y=m_df['건수'], name='건수', mode='lines+markers+text', text=m_df['건수'], textposition='top center', marker_color='#ef4444', yaxis='y2'))
        fig.update_layout(yaxis=dict(title='매출액', showgrid=False), yaxis2=dict(title='건수', overlaying='y', side='right', showgrid=False), legend=dict(orientation="h", y=1.15, x=1), margin=dict(t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)
        
    with col_b:
        st.subheader("🍩 시장 점유율")
        pie_view = st.selectbox("분석 기간 선택", ["총합계 (전체)", "1분기 (1~3월)", "2분기 (4월~)", "1월", "2월", "3월", "4월"], label_visibility="collapsed")
        if pie_view == "총합계 (전체)": pie_df = df_f
        elif "1분기" in pie_view: pie_df = df_f[df_f['분기'] == '1분기']
        elif "2분기" in pie_view: pie_df = df_f[df_f['분기'] == '2분기']
        else: pie_df = df_f[df_f['월'] == pie_view]
        
        if pie_df.empty: st.info(f"선택하신 '{pie_view}' 기간의 실적 데이터가 없습니다.")
        else:
            top10_pie = pie_df.groupby('업체명')['금액'].sum().nlargest(10).reset_index()
            fig_pie = px.pie(top10_pie, names='업체명', values='금액', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(showlegend=False, margin=dict(t=20, b=0))
            st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")

    st.subheader("📋 업체별 종합 실적 랭킹 보드")
    
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1.2, 1.2, 1])
    with ctrl_col1:
        show_cnt = st.checkbox("📝 월/분기별 계약건수 함께 보기", value=False)
    with ctrl_col2:
        include_mas = st.checkbox("🏢 MAS 계약 포함 (해제 시 '우수조달'만 표시)", value=True)
        
    board_df = df_f.copy()
    if not include_mas:
        board_df = board_df[board_df['MAS여부'] == 'N']

    p_amt = pd.pivot_table(board_df, values='금액', index='업체명', columns='월', aggfunc='sum', fill_value=0).reset_index()
    for m in ['1월', '2월', '3월', '4월']:
        if m not in p_amt.columns: p_amt[m] = 0
    p_amt['1분기 합계'] = p_amt['1월'] + p_amt['2월'] + p_amt['3월']
    p_amt['누적 합계'] = p_amt['1분기 합계'] + p_amt['4월']
    
    p_cnt = pd.pivot_table(board_df, values='납품요구번호', index='업체명', columns='월', aggfunc='nunique', fill_value=0).reset_index()
    for m in ['1월', '2월', '3월', '4월']:
        if m not in p_cnt.columns: p_cnt[m] = 0
    p_cnt['1분기(건)'] = p_cnt['1월'] + p_cnt['2월'] + p_cnt['3월']
    p_cnt['누적(건)'] = p_cnt['1분기(건)'] + p_cnt['4월']
    p_cnt.rename(columns={'1월':'1월(건)', '2월':'2월(건)', '3월':'3월(건)', '4월':'4월(건)'}, inplace=True)
    
    final = pd.merge(p_amt, p_cnt, on='업체명', how='outer').fillna(0)
    
    if show_cnt:
        disp_cols = ['업체명', '1월', '1월(건)', '2월', '2월(건)', '3월', '3월(건)', '1분기 합계', '1분기(건)', '4월', '4월(건)', '누적 합계', '누적(건)']
    else:
        disp_cols = ['업체명', '1월', '2월', '3월', '1분기 합계', '4월', '누적 합계']
        
    if final.empty:
        st.warning("선택하신 조건에 해당하는 실적이 없습니다.")
    else:
        final = final[disp_cols]
    
        with ctrl_col3:
            sort_options = [c for c in disp_cols if c != '업체명']
            default_idx = sort_options.index('누적 합계')
            sort_target = st.selectbox("⬇️ 랭킹 정렬 기준", options=sort_options, index=default_idx, label_visibility="collapsed")
        
        final = final.sort_values(sort_target, ascending=False).reset_index(drop=True)
        final.insert(0, '랭킹 No.', range(1, len(final) + 1))
        
        fmt_map = {c: "{:,.0f}" for c in final.columns if c not in ['랭킹 No.', '업체명']}
        styled = final.style.format(fmt_map)
        styled = styled.set_properties(subset=['업체명'], **{'background-color': 'rgba(128, 128, 128, 0.1)', 'font-weight': 'bold'})
        styled = styled.set_properties(subset=[c for c in final.columns if '월' in c and '(' not in c], **{'background-color': 'rgba(54, 162, 235, 0.05)'})
        styled = styled.set_properties(subset=['1분기 합계'], **{'background-color': 'rgba(255, 159, 64, 0.1)', 'font-weight': 'bold'})
        if show_cnt:
            styled = styled.set_properties(subset=[c for c in final.columns if '(건)' in c], **{'background-color': 'rgba(76, 175, 80, 0.05)'})
            
        styled = styled.background_gradient(subset=[sort_target], cmap='Blues')
        
        st.dataframe(styled, use_container_width=True, hide_index=True)

        xlsx = BytesIO()
        with pd.ExcelWriter(xlsx, engine='xlsxwriter') as wr:
            final.to_excel(wr, index=False, sheet_name='실적랭킹')
        st.download_button("💾 엑셀 보고서 다운로드", xlsx.getvalue(), f'조달업체랭킹_{get_now_kst().strftime("%Y%m%d")}.xlsx')

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim. Data from Public Data Portal.</center>", unsafe_allow_html=True)
