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

# --- 2. 분석 대상 업체 및 화이트리스트 ---
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

# 화이트리스트 (이 단어가 포함된 품목만 수집)
INCLUDE_KEYWORDS = [
    "CCTV", "IP전화기", "PA", "SSD", "게이트웨이", "경광등", "광분배함", "광송수신", "광점퍼코드", "교통관제", 
    "그래픽용어댑터", "금속상자", "기상전광판", "기억유닛", "네트워크스위치", "랙", "차단기", "축전지", 
    "컴퓨터", "도난방지", "동보장치", "동작분석", "디스크어레이", "디지털비디오레코더", "패널", "랜접속카드", 
    "레이더", "레이드", "레이스웨이", "앰프", "마을무선방송", "마이크로폰", "멀티스크린", "멀티탭", 
    "액세스포인트", "무선중계기", "무선통신", "납축전지", "방송수신기", "방화벽", "벨", "보안소프트웨어", 
    "카메라", "보행자안전", "신호기", "분배기", "과학용소프트웨어", "브래킷", "비디오네트워킹", "비상경보기", 
    "산업관리소프트웨어", "삼각대", "서지흡수기", "유지및지원서비스", "송신기", "스위치박스", "전원공급", 
    "스테이플", "스피커", "시스템관리소프트웨어", "실내환경측정", "안내전광판", "안내판", "액정모니터", 
    "엔코더", "감지기", "영상감시", "영상분배기", "영상정보디스플레이", "트랜스미터", "원격단말", 
    "유틸리티소프트웨어", "음향발생", "인버터", "인증서버", "인터콤", "인터폰", "자동화재속보", "자료수집", 
    "제어보드", "적외선", "탐지기", "전자카드", "종합폴", "지도소프트웨어", "차량검지", "카드인쇄", 
    "컨버터", "망전환", "안면인식", "정맥인식", "지문인식", "홍채인식", "콘솔익스텐더", "태블릿", 
    "태양전지", "텔레비전", "거치대", "통신소프트웨어", "변조기", "통신케이블", "패키지소프트웨어", 
    "풀박스", "하드디스크", "가요전선관", "비닐절연전선", "광케이블", "UTP케이블", "기둥", "전력케이블", 
    "접지봉", "접지판", "정보통신공사", "정보화교육", "제어케이블", "철근콘크리트공사", "토공사", "포장공사", "전선관"
]

# --- 3. 로컬 데이터 로드 (💡 80억 복구 엔진) ---
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
            
            item_col = '세부품명' if '세부품명' in df.columns else ('물품분류명' if '물품분류명' in df.columns else '품명')
            req_col = '납품요구번호' if '납품요구번호' in df.columns else ('주문번호' if '주문번호' in df.columns else None)
            if not req_col: continue 

            # 💡 [슈퍼 금액 파서] 요구금액/증감금액 중 진짜 돈이 들어있는 칸을 찾아냄! (인텔리빅스 80억 복구의 핵심)
            df['amt1'] = pd.to_numeric(df['납품요구금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            df['amt2'] = pd.to_numeric(df['납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            df['amt3'] = pd.to_numeric(df['합계납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            df['금액'] = df[['amt1', 'amt2', 'amt3']].max(axis=1) # 세 칸 중 가장 큰 값을 실적으로 인정

            temp_df = df[['업체명', item_col, '금액', req_col]].copy()
            temp_df.columns = ['업체명', '세부품명', '금액', '납품요구번호']
            temp_df['월'] = target_month
            
            temp_df['업체명'] = temp_df['업체명'].astype(str).apply(lambda x: TARGET_MAP.get(normalize_corp_name(x), None))
            temp_df = temp_df.dropna(subset=['업체명'])
            
            if 'MAS여부' in df.columns: temp_df['MAS여부'] = df['MAS여부'].fillna('N').astype(str).str.strip().str.upper()
            else: temp_df['MAS여부'] = 'Y' 
                
            dfs.append(temp_df)
        except Exception: continue
    
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# --- 4. 실시간 API 수집 (💡 타임밤 제거 엔진) ---
def fetch_api_data_raw():
    now = get_now_kst()
    try:
        import urllib.parse
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
            params = {'serviceKey': API_KEY, 'numOfRows': '999', 'pageNo': str(page_no), 'inqryDiv': '1', 'inqryBgnDate': bgn_date, 'inqryEndDate': end_date}
            try:
                res = requests.get(URL, params=params, timeout=15)
            except Exception: return pd.DataFrame(), f"🚨 통신 실패"
            
            if res.status_code == 401: return pd.DataFrame(), "🚨 HTTP 401: 인증키 동기화 대기 중 (1~2시간 뒤 자동 해결)"
            if res.status_code != 200: return pd.DataFrame(), f"🚨 HTTP {res.status_code} 에러"

            root = ET.fromstring(res.content)
            total_count_str = root.findtext('.//totalCount')
            if total_count_str: total_count = int(total_count_str)
            if total_count == 0: break

            items = root.findall('.//item')
            for item in items:
                date_clean = item.findtext('dlvrReqRcptDate', '').replace('-', '')[:8]
                if not date_clean: date_clean = item.findtext('dlvrReqDate', '').replace('-', '')[:8]
                if date_clean < cutoff_date: continue
                
                cntrct_stle = item.findtext('cntrctCnclsStleNm', '')
                if not any(k in cntrct_stle for k in ['제3자단가', '다수공급자', '우수', 'MAS']): continue

                raw_corp = item.findtext('corpNm', '')
                norm_corp = normalize_corp_name(raw_corp)
                
                if norm_corp in TARGET_MAP:
                    all_new_data.append({
                        '업체명': TARGET_MAP[norm_corp], 
                        '세부품명': item.findtext('dtilPrdctClsfcNm', '') or item.findtext('prdctClsfcNm', ''), 
                        '금액': float(item.findtext('dlvrReqAmt', 0)), 
                        '납품요구번호': item.findtext('dlvrReqNo', '').strip() or f'API_{time.time()}', 
                        '월': f"{int(date_clean[4:6])}월", 'MAS여부': 'Y' 
                    })
                    added_count += 1
            if page_no * 999 >= total_count: break
            page_no += 1
        return pd.DataFrame(all_new_data), f"🟢 4/20 이후 {added_count}건 수집 완료"
    except Exception: return pd.DataFrame(), f"⚠️ 파싱 에러"

# --- 5. 데이터 통합 및 💡 [유연한 필터링] ---
def get_processed_data_raw():
    df_hist = load_historical_data_raw()
    df_api, api_msg = fetch_api_data_raw()

    if not df_api.empty and not df_hist.empty:
        existing_nos = set(df_hist['납품요구번호'].astype(str).unique())
        df_api_clean = df_api[~df_api['납품요구번호'].astype(str).isin(existing_nos)]
        df_total = pd.concat([df_hist, df_api_clean], ignore_index=True)
    else:
        df_total = df_api if not df_api.empty else df_hist

    # 💡 [유연한 필터링 엔진] 리스트의 단어가 "포함"만 되어도 통과시킴!
    if not df_total.empty:
        pattern = '|'.join(INCLUDE_KEYWORDS)
        df_total = df_total[df_total['세부품명'].astype(str).str.contains(pattern, na=False, case=False)]

    return df_total, api_msg

df_total, api_msg = get_processed_data_raw()

# --- 6. UI ---
st.markdown(f"<div class='main-title'>🏆 조달청 제3자단가 통합 분석 v41.0 (실적 복원판)</div>", unsafe_allow_html=True)
st.markdown(f"<div class='update-time'>🕒 상태: {api_msg}</div>", unsafe_allow_html=True)

if st.button("🔄 즉시 새로고침"): st.rerun()

with st.sidebar:
    st.header("🔍 세부품명 필터")
    if df_total.empty:
        st.error("데이터가 없습니다.")
        selected_items = []
    else:
        all_items = sorted(df_total['세부품명'].unique())
        col_s1, col_s2 = st.columns(2)
        if col_s1.button("✅ 전체선택"): 
            for i in all_items: st.session_state[f"cb_{i}"] = True
        if col_s2.button("❌ 전체삭제"): 
            for i in all_items: st.session_state[f"cb_{i}"] = False
        selected_items = [i for i in all_items if st.checkbox(i, value=st.session_state.get(f"cb_{i}", True), key=f"cb_{i}")]

# --- 7. 결과 출력 ---
if selected_items:
    df_f = df_total[df_total['세부품명'].isin(selected_items)].copy()
    
    t_amt = df_f['금액'].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 누적 매출액", f"{t_amt:,.0f} 원")
    c2.metric("📝 총 계약 건수", f"{df_f['납품요구번호'].nunique():,} 건")
    c3.metric("🏢 인텔리빅스 3월", f"{df_f[(df_f['업체명']=='주식회사 인텔리빅스') & (df_f['월']=='3월')]['금액'].sum():,.0f} 원")

    def render_board(df_data, title, cmap):
        st.subheader(title)
        p = pd.pivot_table(df_data, values='금액', index='업체명', columns='월', aggfunc='sum', fill_value=0).reset_index()
        months = sorted([c for c in p.columns if '월' in c], key=lambda x: int(x.replace('월','')))
        p['누적 합계'] = p[months].sum(axis=1)
        p = p.sort_values('누적 합계', ascending=False).reset_index(drop=True)
        p.insert(0, 'No.', range(1, len(p)+1))
        st.dataframe(p.style.format({c: "{:,.0f}" for c in p.columns if c not in ['No.', '업체명']}).background_gradient(subset=['누적 합계'], cmap=cmap), use_container_width=True, hide_index=True)

    st.write("---")
    render_board(df_f, "🏆 업체별 종합 실적 랭킹", "Blues")
else:
    st.info("👈 왼쪽에서 품목을 선택해주세요.")

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim.</center>", unsafe_allow_html=True)
