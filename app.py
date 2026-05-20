import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
import os

# --- [1. 수집 봇: 결과 리포트 방식] ---
def run_crawler_and_report():
    API_KEY = "df5a1c97ab56593d5e99889ae1c030bfe0b5e9d924ffba9bae3712c8bb1ad75c" 
    bgn_date = (datetime.now() - timedelta(days=2)).strftime("%Y%m%d")
    end_date = (today := datetime.now().strftime("%Y%m%d"))
    
    BASE_URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
    
    # 조달청 API 호출 (일단 1페이지 딱 하나만 호출해서 데이터 있는지 없는지부터 찔러봄)
    url = f"{BASE_URL}?serviceKey={API_KEY}&numOfRows=10&pageNo=1&inqryDiv=1&inqryBgnDate={bgn_date}&inqryEndDate={end_date}"
    
    try:
        res = requests.get(url, timeout=30)
        root = ET.fromstring(res.content)
        total_count = int(root.findtext('.//totalCount') or 0)
        
        if total_count > 0:
            return f"🟢 데이터 확인됨! {bgn_date}~{end_date} 사이에 총 {total_count}건의 조달 실적이 존재합니다. (수집 가능!)"
        else:
            return f"🔵 해당 기간({bgn_date}~{end_date})에 신규 실적이 0건입니다."
    except Exception as e:
        return f"🚨 에러 발생: {e}"

# --- [2. 대시보드 화면] ---
st.title("🛠 시스템 상태 진단 및 수집")

if st.button("🔍 데이터 있는지 확인하기"):
    msg = run_crawler_and_report()
    st.write(msg)

st.markdown("---")
st.subheader("현재 DB 파일 미리보기")
if os.path.exists("Master_DB.csv"):
    df = pd.read_csv("Master_DB.csv", encoding='utf-8-sig', dtype=str)
    st.write(f"현재 Master_DB 건수: {len(df):,} 건")
    st.dataframe(df.tail(5))
else:
    st.error("Master_DB.csv 파일이 없습니다!")
