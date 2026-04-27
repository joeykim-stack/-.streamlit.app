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
    .main-title { font-size: 2.2rem; font-weight: 800; color: #1e3a8a; margin-bottom: 0.5rem; }
    .update-time { color: #6c757d; font-size: 0.9rem; margin-bottom: 2rem; }
    .stCheckbox { margin-bottom: -15px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 분석 대상 업체 및 💡 [신규] 포함 세부품명(화이트리스트) 세팅 ---
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

# 💡 사용자가 지정한 '반드시 포함할' 세부품명 리스트 (중복 알아서 제거됨)
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
INCLUDE_ITEMS = list(set(INCLUDE_ITEMS_RAW)) # 리스트 내 중복 요소 완벽 제거

# --- 3. 로컬 데이터 로드 (💡 V31 베이스 + 세부품명 추출) ---
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
            
            # 💡 [핵심] '세부품명' 최우선 추출 (없으면 품명으로 대체)
            target_item_col = None
            if '세부품명' in df.columns: target_item_col = '세부품명'
            elif '물품분류명' in df.columns: target_item_col = '물품분류명'
            elif '품명' in df.columns: target_item_col = '품명'
