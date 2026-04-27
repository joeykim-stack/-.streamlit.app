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

# --- 3. [캐싱] 로컬 데이터 로드 (V19 심장 이식) ---
@st.cache_data(ttl=3600, show_spinner="로컬 데이터를 불러오는 중...")
def load_historical_data():
    file_month_map = {'data.csv': '1월', 'data02.csv': '2월', 'data02.cvs': '2월', 'data03.csv': '3월', 'data04.csv': '4월'}
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

            df[req_col] = df[req_col].fillna('').astype(str).str.replace('nan', '', regex=False).str.strip().str.replace(r'\.0$', '', regex=True)

            # 💡 [핵심 복구] 파로스 50억을 굳건히 지켜냈던 V19의 금액 파싱 로직!
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
    
    result_df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    
    # 중복 파일(data02.csv / data02.cvs)만 잡아내고 다중 품목은 절대 건드리지 않음
    if not result_df.empty:
        result_df = result_df.drop_duplicates()
        
    return result_df

# --- 4. [캐싱] 실시간 API 수집 ---
@st.cache_data(ttl=1800, show_spinner="조달청 실시간 API 스캔 중...")
def fetch_api_data():
    now = get_now_kst()
    try:
        RAW_KEY = "c1b379f7734c7d624ddefea07510eae71b6e12c5fb89970319d76c5ae8db5248"
        API_KEY = urllib.parse.unquote(RAW_KEY)
        URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
        
        # 날짜 필터의 구멍을 없애기 위해 무조건 4월 전체를 요청함 (중복 필터링은 파이썬이 완벽히 수행)
        bgn_date = now.strftime('%Y%m') + '01'
        end_date = now.strftime('%Y%m%d')
        
        all_new_data = []
        page_no = 1
        total_count = 0
        added_count = 0
        
        while True:
            params = {
                'serviceKey': API_KEY, 'numOfRows': '999', 'pageNo': str(page_no),
                'inqryDiv': '1', 'inqryBgnDate': bgn_date, 'inqryEndDate': end_date
            }
            
            try:
                res = requests.get(URL, params=params, timeout=15)
            except Exception: return pd.DataFrame(), f"🚨 통신 실패 (네트워크 끊김)"
            
            if res.status_code != 200: return pd.DataFrame(), f"🚨 HTTP {res.status_code} 에러"

            root = ET.fromstring(res.content)
            result_code = root.findtext('.//resultCode')
            if result_code and result_code not in ['00', '0']:
                return pd.DataFrame(), f"🚨 API 거부: [{result_code}]"

            total_count_str = root.findtext('.//totalCount')
            if total_count_str: total_count = int(total_count_str)

            if total_count == 0: break

            items = root.findall('.//item')
            if not items: break
            
            for item in items:
                # 💡 [V19 복원] 오직 순수 '제3자단가'만 통과! 잡계약 철벽 방어!
                cntrct_stle = item.findtext('cntrctCnclsStleNm', '')
                if '제3자단가' not in cntrct_stle: 
                    continue

                raw_corp = item.findtext('corpNm', '')
                norm_corp = normalize_corp_name(raw_corp)
                
                if norm_corp in TARGET_MAP:
                    req_no = item.findtext('dlvrReqNo', '').strip()
                    
                    all_new_data.append({
                        '업체명': TARGET_MAP[norm_corp], 
                        '물품분류명': item.findtext('prdctClsfcNm', ''), 
                        '금액': float(item.findtext('dlvrReqAmt', 0)), 
                        '납품요구번호': req_no if req_no else f'API_{time.time()}', 
                        '월': '4월',
                        'MAS여부': 'Y' 
                    })
                    added_count += 1
            
            if page_no * 999 >= total_count: break
            page_no += 1

        if all_new_data:
            return pd.DataFrame(all_new_data), f"🟢 4월 스캔 완료 -> API 신규 실적 {added_count}건 수집!"
        return pd.DataFrame(), f"🔵 4월 스캔 완료 (타겟 실적 없음)"
        
    except Exception: return pd.DataFrame(), f"⚠️ 파싱 에러"

# --- 5. [캐싱] 데이터 통합 및 정제 (💡 4월 뻥튀기 완전 박살 로직) ---
@st.cache_data(ttl=1800, show_spinner="데이터 통합 및 분석 중...")
def get_processed_data():
    df_hist = load_historical_data()
    df_api, api_msg = fetch_api_data()

    if not df_hist.empty: df_hist['납품요구번호'] = df_hist['납품요구번호'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    if not df_api.empty: df_api['납품요구번호'] = df_api['납품요구번호'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

    if not df_api.empty and not df_hist.empty:
        # API 자체의 중복 주문번호 제거 (API는 1주문 1행 원칙)
        df_api = df_api.drop_duplicates(subset=['납품요구번호'])
        
        # 💡 [절대 방어막] 엑셀에 이미 존재하는 '납품요구번호' 수만 개를 전부 추출해서 블랙리스트 생성!
        existing_req_nos = set(df_hist['납품요구번호'].unique())
        existing_req_nos.discard('') 
        existing_req_nos.discard('nan')
        
        # 💡 API 데이터 중에서 엑셀에 이미 있는 번호는 0.001초 만에 모조리 튕겨냄! (4월 뻥튀기 100% 불가)
        df_api_new = df_api[~df_api['납품요구번호'].isin(existing_req_nos)]
        
        # 엑셀 원본(1원도 안 건드림) + 완벽히 새로운 API 데이터만 합체!
        df_total = pd.concat([df_hist, df_api_new], ignore_index=True)
    elif not df_api.empty:
        df_total = df_api.copy()
    else:
        df_total = df_hist.copy()

    # 37개 쓰레기 품목 차단 필터
    if not df_total.empty and '물품분류명' in df_total.columns:
        pattern = '|'.join(EXCLUDE_ITEMS)
        df_total = df_total[~df_total['물품분류명'].astype(str).str.contains(pattern, na=False, regex=True)]

    return df_total, api_msg

# 데이터 로드 실행
df_total, api_msg = get_processed_data()

# --- 6. UI 및 새로고침 버튼 ---
st.markdown(f"<div class='main-title'>🏆 조달청 제3자단가계약 통합 대시보드 v29.0 (절대 방어막 패치)</div>", unsafe_allow_html=True)

col_head1, col_head2 = st.columns([5, 1])
with col_head1:
    st.markdown(f"<div class='update-time'>🕒 상태: {api_msg}</div>", unsafe_allow_html=True)
with col_head2:
    if st.button("🔄 실시간 데이터 새로고침", use_container_width=True):
        fetch_api_data.clear()
        get_processed_data.clear()
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

# --- 8. 메인 화면 (요약 & 차트) ---
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

    def render_ranking_board(df_data, title, show_count_col, sort_key, dl_key, cmap_color='Blues'):
        st.subheader(title)
        
        ctrl_col1, ctrl_col2 = st.columns([2.4, 1])
        
        p_amt = pd.pivot_table(df_data, values='금액', index='업체명', columns='월', aggfunc='sum', fill_value=0).reset_index()
        for m in ['1월', '2월', '3월', '4월']:
            if m not in p_amt.columns: p_amt[m] = 0
        p_amt['1분기 합계'] = p_amt['1월'] + p_amt['2월'] + p_amt['3월']
        p_amt['누적 합계'] = p_amt['1분기 합계'] + p_amt['4월']
        
        p_cnt = pd.pivot_table(df_data, values='납품요구번호', index='업체명', columns='월', aggfunc='nunique', fill_value=0).reset_index()
        for m in ['1월', '2월', '3월', '4월']:
            if m not in p_cnt.columns: p_cnt[m] = 0
        p_cnt['1분기(건)'] = p_cnt['1월'] + p_cnt['2월'] + p_cnt['3월']
        p_cnt['누적(건)'] = p_cnt['1분기(건)'] + p_cnt['4월']
        p_cnt.rename(columns={'1월':'1월(건)', '2월':'2월(건)', '3월':'3월(건)', '4월':'4월(건)'}, inplace=True)
        
        final = pd.merge(p_amt, p_cnt, on='업체명', how='outer').fillna(0)
        
        if show_count_col:
            disp_cols = ['업체명', '1월', '1월(건)', '2월', '2월(건)', '3월', '3월(건)', '1분기 합계', '1분기(건)', '4월', '4월(건)', '누적 합계', '누적(건)']
        else:
            disp_cols = ['업체명', '1월', '2월', '3월', '1분기 합계', '4월', '누적 합계']
            
        if final.empty:
            st.warning("해당 조건의 실적이 없습니다.")
            return
            
        final = final[disp_cols]
        
        with ctrl_col2:
            sort_options = [c for c in disp_cols if c != '업체명']
            default_idx = sort_options.index('누적 합계')
            sort_target = st.selectbox("⬇️ 정렬 기준", options=sort_options, index=default_idx, label_visibility="collapsed", key=sort_key)
            
        final = final.sort_values(sort_target, ascending=False).reset_index(drop=True)
        final.insert(0, '랭킹 No.', range(1, len(final) + 1))
        
        fmt_map = {c: "{:,.0f}" for c in final.columns if c not in ['랭킹 No.', '업체명']}
        styled = final.style.format(fmt_map)
        styled = styled.set_properties(subset=['업체명'], **{'background-color': 'rgba(128, 128, 128, 0.1)', 'font-weight': 'bold'})
        styled = styled.set_properties(subset=[c for c in final.columns if '월' in c and '(' not in c], **{'background-color': 'rgba(54, 162, 235, 0.05)'})
        styled = styled.set_properties(subset=['1분기 합계'], **{'background-color': 'rgba(255, 159, 64, 0.1)', 'font-weight': 'bold'})
        if show_count_col:
            styled = styled.set_properties(subset=[c for c in final.columns if '(건)' in c], **{'background-color': 'rgba(76, 175, 80, 0.05)'})
            
        styled = styled.background_gradient(subset=[sort_target], cmap=cmap_color)
        
        st.dataframe(styled, use_container_width=True, hide_index=True, height=600)

        xlsx = BytesIO()
        with pd.ExcelWriter(xlsx, engine='xlsxwriter') as wr:
            final.to_excel(wr, index=False, sheet_name='실적랭킹')
        st.download_button("💾 엑셀 다운로드", xlsx.getvalue(), f'조달랭킹_{dl_key}_{get_now_kst().strftime("%Y%m%d")}.xlsx', key=dl_key)

    st.subheader("⚙️ 랭킹 보드 컨트롤")
    ctrl_col_a, ctrl_col_b = st.columns(2)
    with ctrl_col_a:
        show_cnt = st.checkbox("📝 월/분기별 계약건수 함께 보기", value=False)
    with ctrl_col_b:
        include_mas = st.checkbox("🏢 종합 랭킹에 MAS 계약 포함 (해제 시 '우수조달'만 표시)", value=True)

    st.markdown("---")

    board_df_total = df_f.copy()
    if not include_mas:
        board_df_total = board_df_total[board_df_total['MAS여부'] == 'N']
        
    render_ranking_board(
        df_data=board_df_total, 
        title="🏆 업체별 종합 실적 랭킹 (우수조달 + MAS 전체)", 
        show_count_col=show_cnt, 
        sort_key='sort_total', 
        dl_key='dl_total', 
        cmap_color='Blues'
    )

    st.markdown("<br><br>", unsafe_allow_html=True)

    board_df_mas = df_f[df_f['MAS여부'] == 'Y'].copy()
    render_ranking_board(
        df_data=board_df_mas, 
        title="🏢 MAS 계약 전용 실적 랭킹", 
        show_count_col=show_cnt, 
        sort_key='sort_mas', 
        dl_key='dl_mas', 
        cmap_color='Greens'
    )

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim. Data from Public Data Portal.</center>", unsafe_allow_html=True)
