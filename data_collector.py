import requests
import xml.etree.ElementTree as ET
import pandas as pd
import time
import calendar
import os
from datetime import datetime

# --- 1. 환경 설정 ---
API_KEY = "c1b379f7734c7d624ddefea07510eae71b6e12c5fb89970319d76c5ae8db5248"
URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"

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

def get_monthly_data(year, month):
    # 해당 월의 마지막 날짜 계산 (예: 5월 -> 31일, 2월 -> 28일)
    last_day = calendar.monthrange(year, month)[1]
    start_date = f"{year}{month:02d}01"
    end_date = f"{year}{month:02d}{last_day}"
    
    print(f"\n🚀 [수집 시작] {year}년 {month}월 조달청 제3자단가계약 데이터 수집을 시작합니다. ({start_date} ~ {end_date})")
    
    all_data = []
    page_no = 1
    total_count = 0
    
    while True:
        params = {
            'serviceKey': API_KEY, 
            'numOfRows': '999', 
            'pageNo': str(page_no),
            'inqryDiv': '1', 
            'inqryBgnDate': start_date, 
            'inqryEndDate': end_date
        }
        
        # 💡 강철 멘탈 로직 (500 에러나 통신 장애 시 자동 재시도)
        retries = 0
        success = False
        while retries < 5:
            try:
                res = requests.get(URL, params=params, timeout=15)
                if res.status_code == 200:
                    success = True
                    break
                else:
                    print(f"   ⚠️ 서버 에러({res.status_code}). 5초 후 재시도합니다... ({retries+1}/5)")
                    time.sleep(5)
                    retries += 1
            except requests.exceptions.RequestException as e:
                print(f"   ⚠️ 통신 지연. 5초 후 재시도합니다... ({retries+1}/5)")
                time.sleep(5)
                retries += 1
                
        if not success:
            print("🚨 5회 이상 재시도 실패. 수집을 일시 중단합니다. 나중에 다시 시도해주세요.")
            break

        # XML 파싱
        root = ET.fromstring(res.content)
        items = root.findall('.//item')
        
        if not items:
            print("✅ 수집 완료: 더 이상 데이터가 없습니다.")
            break
            
        if page_no == 1:
            total_count = int(root.findtext('.//totalCount', '0'))
            print(f"📡 조달청 서버 확인 완료: 해당 기간 총 {total_count:,}건의 전국 계약 데이터가 존재합니다.")
            
        # 데이터 필터링
        matched_count = 0
        for item in items:
            corp = item.findtext('corpNm', '').strip()
            if corp in TARGET_COMPANIES:
                all_data.append({
                    '업체명': corp, 
                    '물품분류명': item.findtext('prdctClsfcNm', ''), 
                    # 💡 app.py가 즉시 인식할 수 있도록 컬럼명을 '납품증감금액'으로 위장!
                    '납품증감금액': float(item.findtext('dlvrReqAmt', 0)), 
                    '납품요구번호': item.findtext('dlvrReqNo', f'API_{datetime.now().timestamp()}')
                })
                matched_count += 1
                
        print(f"   ... {page_no}페이지 검색 완료 (타겟 업체 {matched_count}건 발견)")
        
        # 페이지 진행도 체크
        if page_no * 999 >= total_count:
            print("✅ 수집 완료: 마지막 페이지까지 모두 스캔했습니다.")
            break
            
        page_no += 1
        time.sleep(1) # API 서버 과부하 방지 매너 휴식 (1초)

    return pd.DataFrame(all_data)

# --- 2. 메인 실행부 ---
if __name__ == "__main__":
    print("-" * 50)
    print("🤖 조달 데이터 자동 수집 봇")
    print("-" * 50)
    
    try:
        y_input = input("수집할 연도를 입력하세요 (예: 2024): ")
        m_input = input("수집할 월을 입력하세요 (예: 5): ")
        
        target_year = int(y_input)
        target_month = int(m_input)
        
        # 수집 실행
        df = get_monthly_data(target_year, target_month)
        
        if not df.empty:
            # 💡 파일명을 data05.csv, data06.csv 형태로 자동 생성
            filename = f"data{target_month:02d}.csv"
            
            # UTF-8-SIG로 저장하여 엑셀에서 한글이 깨지지 않게 방어
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            
            print("-" * 50)
            print(f"🎉 성공! 총 {len(df):,}건의 타겟 업체 데이터를 찾았습니다.")
            print(f"📁 파일 저장 완료: {filename}")
            print("💡 이제 app.py 대시보드 코드를 열어서 읽어올 파일 목록에 이 파일을 추가만 해주시면 됩니다!")
        else:
            print("🤷‍♂️ 해당 월에 타겟 52개 업체의 계약 실적이 0건입니다.")
            
    except ValueError:
        print("❌ 잘못된 입력입니다. 숫자로만 입력해주세요.")
