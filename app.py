import streamlit as st
import pandas as pd
import requests
import os
import plotly.express as px
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="조달 분석 솔루션 v3.5", layout="wide")

# --- 설정 및 상수 ---
SERVICE_KEY = "c1b3792f-37f0-4d57-897b-3b3614522855"
TARGET_COMPANIES = ["마이크로시스템", "핀텔", "웹게이트", "크리에이티브넷", "두원전자통신", "올인원 코리아", "티제이원", "앤다스", "지성이엔지", "송우인포텍", "렉스젠", "비티에스", "솔디아", "홍석", "비엔에스테크", "디케이앤트", "제이한테크", "그린아이티코리아", "펜타게이트", "한국아이티에스", "미르텍", "포딕스시스템", "명광", "뉴코리아전자통신", "오티에스", "아라드네트웍스", "시큐인포", "센텍", "원우이엔지", "경림이앤지", "진명아이앤씨", "디라직", "알엠텍", "아이엔아이", "지인테크", "다누시스", "에코아이넷", "사이테크놀로지스", "인텔리빅스", "한국씨텍", "아이즈온솔루션", "대신네트웍스", "새움", "이노뎁", "포소드", "에스카", "제노시스", "디지탈라인", "세오", "포커스에이아이", "비알인포텍", "파로스"]

# --- 2. 데이터 수집 (진단 기능 강화) ---
def fetch_api_data():
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    url = "http://apis.data.go.kr/1230000/ShoppingMallPrdctInfoService05/getDlvrReqInfoList"
    
    # 조달청 API는 특수문자가 포함된 인증키를 보낼 때 가끔 디코딩된 키를 요구함
    params = {
        'serviceKey': requests.utils.unquote(SERVICE_KEY), 
        'type': 'json',
        'numOfRows': '999',
        'pageNo': '1',
        'inqryDiv': '1',
        'inqryBgnDate': '20260401', 
        'inqryEndDate': yesterday
    }
    
    try:
        res = requests.get(url, params=params, timeout=15)
        
        # 1차 체크: 통신 성공 여부
        if res.status_code != 200:
            return None, f"통신 에러 (코드: {res.status_code})"
        
        data = res.json()
        header = data.get('response', {}).get('header', {})
        res_code = header.get('resultCode')
        res_msg = header.get('resultMsg')
        
        # 2차 체크: 조달청 서버가 뱉은 에러 (인증키, 트래픽 등)
        if res_code != '00':
            return None, f"조달청 응답: {res_msg} ({res_code})"
            
        body = data.get('response', {}).get('body', {})
        items_container = body.get('items', [])
        
        raw_items = []
        if isinstance(items_container, dict):
            raw_items = items_container.get('item', [])
        elif isinstance(items_container, list):
            raw_items = items_container
            
        if not raw_items:
            return pd.DataFrame(), "4월 데이터가 서버에 아직 없습니다."
            
        df = pd.DataFrame(raw_items)
        df_api = df[['corpNm', 'prdctClsfcNm', 'dlvrReqAmt', 'cntrctCnclsStleNm']].copy()
        df_api.columns = ['업체명', '물품분류명', '금액', '계약유형']
        df_api['금액'] = pd.to_numeric(df_api['금액'], errors='coerce').fillna(0)
        df_api['월'] = "4월"
        df_api['건수'] = 1
        
        # 타겟 업체 필터링
        df_filtered = df_api[df_api['업체명'].str.contains('|'.join(TARGET_COMPANIES), na=False)]
        return df_filtered, "성공"
        
    except Exception as e:
        return None, f"시스템 오류: {str(e)}"

# --- 3. 데이터 통합 로드 ---
def load_data():
    all_dfs = []
    file_map = {"1월": "data.csv", "2월": "data02.csv", "3월": "data03.csv"}
    
    for month, path in file_map.items():
        if os.path.exists(path):
            try:
                tmp = pd.read_csv(path, encoding='utf-8-sig')
                tmp.columns = [str(c).strip() for c in tmp.columns]
                c_corp = next((c for c in tmp.columns if '업체명' in c), None)
                c_item = next((c for c in tmp.columns if '물품분류명' in c), None)
                c_method = next((c for c in tmp.columns if '계약유형' in c or '계약체결형태' in c), None)
                c_amt = next((c for c in tmp.columns if '금액' in c or '납품금액' in c), None)
                
                if all([c_corp, c_item, c_method, c_amt]):
                    df_sub = pd.DataFrame()
                    df_sub['업체명'] = tmp[c_corp].astype(str).str.strip()
                    df_sub['물품분류명'] = tmp[c_item].astype(str).str.strip()
                    df_sub['계약유형'] = tmp[c_method].astype(str).str.strip()
                    df_sub['금액'] = pd.to_numeric(tmp[c_amt].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                    df_sub['월'] = month
                    df_sub['건수'] = 1
                    all_dfs.append(df_sub)
            except: continue
                
    # 4월 API 데이터 진단 모드
    df_api_april, status_msg = fetch_api_data()
    
    if status_msg == "성공":
        if not df_api_april.empty:
            all_dfs.append(df_api_april)
            st.sidebar.success(f"✅ 4월 실시간 데이터 연동 성공 ({len(df_api_april)}건)")
        else:
            st.sidebar.info("ℹ️ 4월 데이터는 있으나, 타겟 업체 실적이 없습니다.")
    else:
        # 🚨 여기서 왜 안되는지 정확한 이유를 보여줌
        st.sidebar.error(f"❌ 4월 연동 실패\n\n사유: {status_msg}")
        
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

df_raw = load_data()

# --- 4. UI/그래프 로직 (v3.3과 동일) ---
# ... (이하 코드는 v3.3과 동일하게 유지 - 분량상 핵심 로직만 표시)
if not df_raw.empty:
    all_k = sorted(df_raw['물품분류명'].unique())
    if 'selected_k' not in st.session_state: st.session_state.selected_k = all_k
    def toggle_k(): st.session_state.selected_k = all_k if st.session_state.master_k else []
    st.title("📊 조달 실적 통합 분석 솔루션 v3.5")
    with st.sidebar:
        st.checkbox("🌟 물품분류 전체 선택", key="master_k", on_change=toggle_k, value=True)
        selected_k = st.multiselect("품목 선택", options=all_k, key="selected_k")
        st.divider()
        unique_r = sorted(df_raw['계약유형'].unique())
        selected_r = [m for m in unique_r if st.sidebar.checkbox(m, value=True, key=f"r_{m}")]
    
    df_f = df_raw[(df_raw['물품분류명'].isin(selected_k)) & (df_raw['계약유형'].isin(selected_r))]
    
    if not df_f.empty:
        st.subheader("📈 월별 매출 추이")
        trend = df_f.groupby('월').agg({'금액':'sum', '건수':'sum'}).reindex(["1월", "2월", "3월", "4월"]).fillna(0)
        st.line_chart(trend['금액'])
        
        st.markdown("---")
        st.subheader("📑 상세 실적")
        st.write(df_f.head(10)) # 샘플 데이터
    else:
        st.warning("조건에 맞는 데이터가 없습니다.")
else:
    st.error("데이터 로드 실패.")
