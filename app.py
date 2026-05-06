import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import time
import re
import urllib.parse

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

# --- 2. 분석 대상 업체 및 화이트리스트 세팅 ---
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

# 사용자가 지정한 '반드시 포함할' 120개 타겟 리스트
INCLUDE_ITEMS_RAW = [
    "CCTV카메라용렌즈", "IP전화기", "PA용스피커", "SSD저장장치", "게이트웨이", "경광등", 
    "광분배함", "광송수신기", "광송수신모듈", "광점퍼코드", "교통관제시스템", "그래픽용어댑터", 
    "금속상자", "기상전광판", "기억유닛", "네트워크스위치", "네트워크시스템장비용랙", 
    "누전차단기", "니켈카드뮴축전지", "데스크톱컴퓨터", "도난방지기", "동보장치", "동작분석기", 
    "디스크어레이", "디지털비디오레코더", "랙캐비닛용패널", "랜접속카드", "레이더", 
    "레이드저장장치", "레이드컨트롤러", "레이스웨이", "리모트앰프", "리튬2차전지", 
    "마을무선방송장치", "마이크로폰", "멀티스크린컴퓨터", "멀티탭", "무선랜액세스포인트", 
    "무선중계기", "무선통신장치", "밀폐고정형납축전지", "방송수신기", "방화벽장치", 
    "베어본컴퓨터", "벨", "보안소프트웨어", "보안용카메라", "보행자안전차단기", 
    "보행자작동신호기", "분배기", "분석및과학용소프트웨어", "브래킷", "비디오네트워킹장비", 
    "비상경보기", "산업관리소프트웨어", "삼각대", "서지흡수기", "소프트웨어유지및지원서비스", 
    "송신기", "스위치박스", "스위칭모드전원공급장치", "스테이플", "스피커", 
    "시스템관리소프트웨어", "실내환경측정장치", "안내전광판", "안내판", "액정모니터", 
    "엔코더", "연기감지기", "열감지기", "열선감지기", "영상감시장치", "영상분배기", 
    "영상정보디스플레이장치", "오디오앰프", "온도트랜스미터", "온습도트랜스미터", 
    "원격단말장치(RTU)", "유틸리티소프트웨어", "음향발생장치", "인버터", "인증서버소프트웨어", 
    "인터콤장비", "인터폰", "자동화재속보기", "자료수집장치", "장치제어보드", "적외선방사기", 
    "적외선수신기", "적외선카메라", "적외선탐지기", "전력공급장치", "전원공급장치", "전자카드", 
    "종합폴", "지도소프트웨어", "차량검지기", "차량차단기", "카드인쇄기", "카메라브래킷", 
    "카메라컨트롤러", "카메라하우징", "카메라회전대", "컨버터", "컴퓨터망전환장치", 
    "컴퓨터서버", "컴퓨터안면인식장치", "컴퓨터정맥인식장치", "컴퓨터지문인식장치", 
    "컴퓨터홍채인식장치", "콘솔익스텐더", "태블릿컴퓨터", "태양전지조절기", "텔레비전", 
    "텔레비전거치대", "통신소프트웨어", "통신용변조기", "통신케이블어셈블리", "특수목적컴퓨터", 
    "패키지소프트웨어개발및도입서비스", "풀박스", "하드디스크드라이브", "호온스피커", 
    "1종금속제가요전선관", "450/750V 일반용유연성단심비닐절연전선", "LAP외피광케이블", "UTP케이블", 
    "경광등", "고주파동축케이블", "광분배함", "광점퍼코드", "금속기둥", "난연전력케이블", 
    "난연접지용비닐절연전선", "네트워크스위치", "네트워크시스템장비용랙", "디지털비디오레코더", 
    "방송수신기", "벨", "보안용카메라", "브래킷", "서지흡수기", "안내전광판", "안내판", 
    "영상감시장치", "영상정보디스플레이장치", "오디오모니터", "오디오앰프", "전원공급장치", 
    "접지봉", "접지판", "정보통신공사", "정보화교육서비스", "제어케이블", "철근콘크리트공사", 
    "카메라브래킷", "컴퓨터서버", "토공사", "통신용변조기", "포장공사", "폴리에틸렌전선관", "풀박스"
]
INCLUDE_ITEMS = [x.strip() for x in list(set(INCLUDE_ITEMS_RAW)) if x.strip()]

# --- 3. 로컬 데이터 로드 (💡 자폭 버그 완벽 해결!) ---
def load_historical_data_raw():
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
            
            target_item_col = None
            if '세부품명' in df.columns: target_item_col = '세부품명'
            elif '물품분류명' in df.columns: target_item_col = '물품분류명'
            elif '품명' in df.columns: target_item_col = '품명'
            
            req_col = '납품요구번호' if '납품요구번호' in df.columns else ('주문번호' if '주문번호' in df.columns else None)
            if not req_col or not target_item_col: continue 

            df[req_col] = df[req_col].fillna('').astype(str).str.replace('nan', '', regex=False).str.replace(r'\.0$', '', regex=True).str.strip()

            # 💡 [슈퍼 금액 파서] 원본 컬럼(df['금액'])을 절대 덮어쓰지 않음! 'calc_amt'라는 임시 변수 사용
            calc_amt = pd.Series(0.0, index=df.index)
            
            # 1. 기본 금액 세팅
            for col in ['납품요구금액', '금액', '납품금액']:
                if col in df.columns:
                    base_amt = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                    calc_amt = calc_amt.where(calc_amt != 0, base_amt)
            
            # 2. 증감금액 덮어쓰기 (진짜 0원이 아닐 때만 덮어씀 -> 인텔리빅스 80억 보호)
            for col in ['납품증감금액', '합계납품증감금액']:
                if col in df.columns:
                    mod_amt = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                    mask = mod_amt != 0
                    calc_amt.loc[mask] = mod_amt[mask]
            
            df['최종파싱금액'] = calc_amt
            
            temp_df = df[['업체명', target_item_col, '최종파싱금액', req_col]].copy()
            temp_df.columns = ['업체명', '세부품명', '금액', '납품요구번호']
            temp_df['월'] = target_month
            
            temp_df['업체명'] = temp_df['업체명'].astype(str).apply(lambda x: TARGET_MAP.get(normalize_corp_name(x), None))
            temp_df = temp_df.dropna(subset=['업체명'])
            
            if 'MAS여부' in df.columns: temp_df['MAS여부'] = df['MAS여부'].fillna('N').astype(str).str.strip().str.upper()
            else: temp_df['MAS여부'] = 'Y' 
                
            dfs.append(temp_df)
        except Exception: continue
    
    result_df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    if not result_df.empty: result_df = result_df.drop_duplicates()
    return result_df

# --- 4. 실시간 API 수집 ---
def fetch_api_data_raw():
    now = get_now_kst()
    try:
        RAW_KEY = "15bc460106a7359afdd54c91410a8dd94c17076ba2aa7d4308cfb8e07e9ce5ae"
        API_KEY = urllib.parse.unquote(RAW_KEY)
        URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
        
        bgn_date = "20260401"
        end_date = now.strftime('%Y%m%d')
        cutoff_date = "20260420"
        
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
            
            if res.status_code == 429: return pd.DataFrame(), "🚨 API 일일 한도 초과 (내일 초기화. 로컬 데이터만 표시)"
            if res.status_code == 401: return pd.DataFrame(), "🚨 HTTP 401: 새 인증키 서버 동기화 대기 중 (1~2시간 소요)"
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
                req_date = item.findtext('dlvrReqDate', '')
                rcpt_date = item.findtext('dlvrReqRcptDate', '')
                target_date = rcpt_date if rcpt_date else req_date
                date_clean = target_date.replace('-', '').replace('.', '').strip()[:8]
                
                if date_clean and date_clean < cutoff_date: continue
                
                cntrct_stle = item.findtext('cntrctCnclsStleNm', '')
                if not cntrct_stle: continue
                if not any(k in cntrct_stle for k in ['제3자단가', '다수공급자', '우수', 'MAS']): continue

                raw_corp = item.findtext('corpNm', '')
                norm_corp = normalize_corp_name(raw_corp)
                
                if norm_corp in TARGET_MAP:
                    req_no = item.findtext('dlvrReqNo', '').strip()
                    item_name = item.findtext('dtilPrdctClsfcNm', '')
                    if not item_name: item_name = item.findtext('prdctClsfcNm', '')
                    
                    api_month_str = f"{int(date_clean[4:6])}월"
                    
                    # 💡 빈 문자열("") 에러 방지 처리
                    amt_str = item.findtext('dlvrReqAmt', '0')
                    if not amt_str or str(amt_str).strip() == '': amt_str = '0'
                    
                    all_new_data.append({
                        '업체명': TARGET_MAP[norm_corp], 
                        '세부품명': item_name, 
                        '금액': float(amt_str), 
                        '납품요구번호': req_no if req_no else f'API_{time.time()}', 
                        '월': api_month_str,
                        'MAS여부': 'Y' 
                    })
                    added_count += 1
            
            if page_no * 999 >= total_count: break
            page_no += 1

        if all_new_data:
            return pd.DataFrame(all_new_data), f"🟢 4/20 이후 실적 {added_count}건 수집!"
        return pd.DataFrame(), f"🔵 스캔 완료 (4/20 이후 타겟 실적 없음)"
        
    except Exception: return pd.DataFrame(), f"⚠️ 파싱 에러"

# --- 5. 데이터 통합 및 정제 (💡 지능형 화이트리스트 적용) ---
def get_processed_data_raw():
    df_hist = load_historical_data_raw()
    df_api, api_msg = fetch_api_data_raw()

    if not df_hist.empty: df_hist['납품요구번호'] = df_hist['납품요구번호'].astype(str).str.strip()
    if not df_api.empty: df_api['납품요구번호'] = df_api['납품요구번호'].astype(str).str.strip()

    if not df_api.empty and not df_hist.empty:
        existing_nos = set(df_hist['납품요구번호'].unique())
        existing_nos.discard('') 
        existing_nos.discard('nan')
        
        df_api_clean = df_api[~df_api['납품요구번호'].isin(existing_nos)]
        df_total = pd.concat([df_hist, df_api_clean], ignore_index=True)
    elif not df_api.empty:
        df_total = df_api.copy()
    else:
        df_total = df_hist.copy()

    # 💡 [진짜 Contains 필터] 
    if not df_total.empty and '세부품명' in df_total.columns:
        escaped_items = [re.escape(x) for x in INCLUDE_ITEMS]
        pattern = '|'.join(escaped_items)
        df_total = df_total[df_total['세부품명'].astype(str).str.contains(pattern, na=False, case=False)]

    return df_total, api_msg

df_total, api_msg = get_processed_data_raw()

# --- 6. UI 및 새로고침 버튼 ---
st.markdown(f"<div class='main-title'>🏆 조달청 실적 분석 v44.0 (금액 오류 완전 픽스)</div>", unsafe_allow_html=True)

col_head1, col_head2 = st.columns([5, 1])
with col_head1:
    st.markdown(f"<div class='update-time'>🕒 상태: {api_msg}</div>", unsafe_allow_html=True)
with col_head2:
    if st.button("🔄 즉시 새로고침", use_container_width=True):
        st.rerun()

# --- 7. 사이드바 필터 ---
with st.sidebar:
    st.header("🔍 세부품명 상세 필터")
    if df_total.empty:
        st.error("⚠️ 조건에 맞는 데이터가 없습니다.")
        selected_items = []
    else:
        all_items = sorted(df_total['세부품명'].dropna().unique())
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

# --- 8. 메인 화면 ---
if not selected_items:
    st.info("👈 왼쪽 사이드바에서 분석할 세부품명을 1개 이상 선택해주세요.")
else:
    df_f = df_total[df_total['세부품명'].isin(selected_items)].copy()
    
    df_f['분기'] = df_f['월'].apply(lambda x: '1분기' if x in ['1월', '2월', '3월'] else '2분기')
    df_f['총계'] = '총합계'
    
    t_cnt = df_f['납품요구번호'].nunique()
    t_amt = df_f['금액'].sum()
    
    # 💡 인텔리빅스 80억 확인용
    intellivix_amt = df_f[df_f['업체명'] == '주식회사 인텔리빅스']['금액'].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("💰 누적 매출액", f"{t_amt:,.0f} 원")
    c2.metric("📝 총 계약 건수", f"{t_cnt:,} 건")
    c3.metric("🏢 인텔리빅스 총실적(확인용)", f"{intellivix_amt:,.0f} 원")
    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("📈 실적 추이")
        trend_view = st.radio("조회 기준", ["월별", "분기별", "총합계"], horizontal=True, label_visibility="collapsed")
        time_col = '월' if trend_view == '월별' else ('분기' if trend_view == '분기별' else '총계')
        m_df = df_f.groupby(time_col).agg(금액=('금액', 'sum'), 건수=('납품요구번호', 'nunique')).reset_index()
        
        if trend_view == '월별':
            m_df['sort_key'] = m_df['월'].str.replace('월', '').astype(int)
            m_df = m_df.sort_values('sort_key').drop(columns=['sort_key'])
        elif trend_view == '분기별': 
            m_df = m_df.sort_values('분기')
            
        fig = go.Figure()
        fig.add_trace(go.Bar(x=m_df[time_col], y=m_df['금액'], name='매출액', marker_color='#3b82f6', yaxis='y1'))
        fig.add_trace(go.Scatter(x=m_df[time_col], y=m_df['건수'], name='건수', mode='lines+markers+text', text=m_df['건수'], textposition='top center', marker_color='#ef4444', yaxis='y2'))
        fig.update_layout(yaxis=dict(title='매출액', showgrid=False), yaxis2=dict(title='건수', overlaying='y', side='right', showgrid=False), legend=dict(orientation="h", y=1.15, x=1), margin=dict(t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)
        
    with col_b:
        st.subheader("🍩 시장 점유율")
        avail_months = sorted(df_f['월'].unique(), key=lambda x: int(x.replace('월', '')))
        pie_options = ["총합계 (전체)", "1분기 (1~3월)", "2분기 (4월~)"] + avail_months
        pie_view = st.selectbox("분석 기간 선택", pie_options, label_visibility="collapsed")
        
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
        
        all_months = sorted(df_data['월'].unique(), key=lambda x: int(x.replace('월', '')))
        if not all_months: return st.warning("해당 조건의 실적이 없습니다.")
            
        p_amt = pd.pivot_table(df_data, values='금액', index='업체명', columns='월', aggfunc='sum', fill_value=0).reset_index()
        p_cnt = pd.pivot_table(df_data, values='납품요구번호', index='업체명', columns='월', aggfunc='nunique', fill_value=0).reset_index()
        
        for m in all_months:
            if m not in p_amt.columns: p_amt[m] = 0
            if m not in p_cnt.columns: p_cnt[m] = 0
            
        q1_months = [m for m in all_months if m in ['1월', '2월', '3월']]
        
        p_amt['1분기 합계'] = p_amt[q1_months].sum(axis=1) if q1_months else 0
        p_amt['누적 합계'] = p_amt[all_months].sum(axis=1)
        
        p_cnt['1분기(건)'] = p_cnt[q1_months].sum(axis=1) if q1_months else 0
        p_cnt['누적(건)'] = p_cnt[all_months].sum(axis=1)
        
        p_cnt.rename(columns={m: f'{m}(건)' for m in all_months}, inplace=True)
        
        final = pd.merge(p_amt, p_cnt, on='업체명', how='outer').fillna(0)
        
        disp_cols = ['업체명']
        for m in all_months:
            disp_cols.append(m)
            if show_count_col: disp_cols.append(f'{m}(건)')
        disp_cols.append('1분기 합계')
        if show_count_col: disp_cols.append('1분기(건)')
        disp_cols.append('누적 합계')
        if show_count_col: disp_cols.append('누적(건)')
            
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

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim. Data from Public Data Portal.</center>", unsafe_allow_html=True)
