import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 1. 타겟 업체 및 매핑 ---
TARGET_COMPANIES = ["주식회사 티제이원", "주식회사 파로스", "주식회사 포딕스시스템", "주식회사 세오", "주식회사 펜타게이트", "주식회사 홍석", "주식회사 솔디아", "주식회사 정현씨앤씨", "주식회사 디라직", "주식회사 새움", "주식회사 디지탈라인", "주식회사 지인테크", "(주)비엔에스테크", "주식회사 시큐인포", "주식회사 명광", "주식회사 올인원 코리아(ALL-IN-ONE KOREA CO., LTD.)", "주식회사 포커스에이아이", "주식회사 한국아이티에스", "(주)앤다스", "주식회사 다누시스", "이노뎁(주)", "주식회사 핀텔", "주식회사 오티에스", "주식회사 에스카", "에코아이넷(주)", "미르텍 주식회사", "주식회사 아이즈온솔루션", "주식회사 그린아이티코리아", "주식회사 제노시스", "(주)지성이엔지", "주식회사 알엠텍", "(주)원우이엔지", "(주)포소드", "주식회사 두원전자통신", "대신네트웍스주식회사", "주식회사 마이크로시스템", "주식회사 크리에이티브넷", "주식회사센텍", "(주)경림이앤지", "주식회사 웹게이트", "한국씨텍(주)", "뉴코리아전자통신 주식회사", "주식회사 제이한테크", "주식회사 아라드네트웍스", "주식회사 진명아이앤씨", "렉스젠 주식회사", "주식회사 디케이앤트", "사이테크놀로지스 주식회사", "주식회사 송우인포텍", "주식회사 아이엔아이", "비티에스 주식회사", "주식회사 인텔리빅스", "주식회사 비알인포텍"]
def normalize_corp_name(name): return name.replace('주식회사', '').replace('(주)', '').replace(' ', '').strip() if name else ""
TARGET_MAP = {normalize_corp_name(comp): comp for comp in TARGET_COMPANIES}

# --- 2. 데이터 파서 ---
def unified_data_parser(df_raw):
    if df_raw.empty: return pd.DataFrame()
    df = df_raw.copy()
    for req_col in ['업체명', '물품분류명', '납품요구번호']:
        if req_col not in df.columns: df[req_col] = ''
    if 'corpNm' in df.columns: df['업체명'] = df['corpNm']
    if 'prdctClsfcNm' in df.columns: df['물품분류명'] = df['prdctClsfcNm']
    if 'dlvrReqNo' in df.columns: df['납품요구번호'] = df['dlvrReqNo']
    if 'dlvrReqRcptDate' in df.columns: df['일자'] = df['dlvrReqRcptDate']

    df['업체명'] = df['업체명'].astype(str).apply(lambda x: TARGET_MAP.get(normalize_corp_name(x), None))
    df = df.dropna(subset=['업체명'])
    if df.empty: return pd.DataFrame()

    df['납품요구번호'] = df['납품요구번호'].fillna('').astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    
    calc_amt = pd.Series(0.0, index=df.index)
    for col in ['dlvrReqAmt']:
        if col in df.columns:
            base_amt = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            calc_amt = calc_amt.where(calc_amt != 0, base_amt)
    for col in ['chgDlvrReqAmt', 'dlvrIemRducAmt']:
        if col in df.columns:
            mod_amt = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            mask = mod_amt != 0
            calc_amt.loc[mask] = mod_amt[mask]
    df['금액'] = calc_amt

    if '일자' in df.columns:
        date_clean = df['일자'].astype(str).str.replace('-', '').str.replace('.', '').str.strip().str[:8]
        df['월'] = date_clean.str[4:6].apply(lambda x: f"{int(x)}월" if str(x).isdigit() else "5월")
    else: df['월'] = "5월"

    cntrct_col = 'cntrctCnclsStleNm' if 'cntrctCnclsStleNm' in df.columns else None
    if cntrct_col: df['MAS여부'] = df[cntrct_col].astype(str).apply(lambda x: 'Y' if any(k in x for k in ['다수공급자', 'MAS', 'mas', '제3자']) else 'N')
    else: df['MAS여부'] = 'Y'

    return df[['업체명', '물품분류명', '금액', '납품요구번호', '월', 'MAS여부']]

# --- 3. 실행 로직 ---
def run_daily_update():
    now = datetime.now() + timedelta(hours=9)
    target_date = (now - timedelta(days=2)).strftime("%Y%m%d") # 안전하게 이틀 전(어제 새벽 마감분) 데이터 하루치만 수집
    
    print(f"🔄 [조달청 일일 배치] {target_date} 실적 수집을 시작합니다...")
    
    RAW_KEY = "d6a789992823ed502e65039680f537b3db0da665bcb00e41330ce78a7c07f466"
    BASE_URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
    headers = {'User-Agent': 'Mozilla/5.0'}

    all_new_data = []
    page_no = 1
    
    while True:
        req_url = f"{BASE_URL}?serviceKey={RAW_KEY}&numOfRows=500&pageNo={page_no}&inqryDiv=1&inqryBgnDate={target_date}&inqryEndDate={target_date}"
        try:
            res = requests.get(req_url, headers=headers, timeout=45, verify=False)
            if res.status_code != 200: break
            root = ET.fromstring(res.content)
            if root.findtext('.//resultCode') not in ['00', '0']: break
            
            total_count = int(root.findtext('.//totalCount') or 0)
            if total_count == 0: break
            
            items = root.findall('.//item')
            if not items: break
            
            for item in items:
                all_new_data.append({child.tag: child.text for child in item})
                
            if page_no * 500 >= total_count: break
            page_no += 1
        except: break

    if all_new_data:
        df_clean = unified_data_parser(pd.DataFrame(all_new_data))
        if not df_clean.empty:
            cache_file = "api_data_cache.csv"
            if os.path.exists(cache_file):
                old_df = pd.read_csv(cache_file, encoding='utf-8-sig')
                combined = pd.concat([old_df, df_clean]).drop_duplicates(subset=['납품요구번호'], keep='last')
            else:
                combined = df_clean
            combined.to_csv(cache_file, index=False, encoding='utf-8-sig')
            print(f"✅ 수집 완료! 신규 {len(df_clean)}건이 DB에 저장되었습니다.")
            return
    print("🔵 오늘 업데이트된 타겟 업체의 신규 실적이 없습니다.")

if __name__ == "__main__":
    run_daily_update()
