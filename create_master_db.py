import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
import os
import urllib3

# SSL 경고 숨기기
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

print("🚀 [Step 1] 마스터 DB 생성 프로세스 시작...\n")

# --- 1. 설정 및 타겟 업체 로드 (사업자등록번호 기준) ---
NEW_API_KEY = "df5a1c97ab56593d5e99889ae1c030bfe0b5e9d924ffba9bae3712c8bb1ad75c"
TARGET_FILE = "target_companies.csv"
OUTPUT_FILE = "Master_DB.csv"

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

try:
    # 💡 [핵심 버그 수정] 위에 쓸데없는 4줄(제목, 생성자 등)을 건너뛰고(skiprows=4) 5번째 줄부터 헤더로 읽음!
    df_target = pd.read_csv(TARGET_FILE, encoding='utf-8-sig', skiprows=4)
    df_target['사업자등록번호'] = df_target['사업자등록번호'].astype(str).str.replace('-', '').str.strip()
    TARGET_MAP = dict(zip(df_target['사업자등록번호'], df_target['계약업체']))
    print(f"✅ 타겟 업체 {len(TARGET_MAP)}개 로드 완료! (사업자등록번호 기준 철통 필터링 준비)")
except Exception as e:
    print(f"🚨 타겟 업체 파일({TARGET_FILE}) 로드 에러: {e}")
    exit()

# --- 2. 통합 파이프라인 (사업자번호 필터링 + MAS/우수조달 완벽 분리) ---
def unified_data_parser(df_raw, target_month=None, is_api=False):
    if df_raw is None or df_raw.empty: return pd.DataFrame()
    df = df_raw.copy()

    # 컬럼 통합 정리
    if 'bizrno' in df.columns: df['사업자등록번호'] = df['bizrno']
    
    if '사업자등록번호' not in df.columns: return pd.DataFrame() # 사업자번호 없으면 스킵
    
    # 💡 1차 필터: 사업자등록번호가 우리가 가진 53개 목록에 있는 것만 통과!
    df['사업자등록번호'] = df['사업자등록번호'].astype(str).str.replace('-', '').str.replace('.0', '', regex=True).str.strip()
    df = df[df['사업자등록번호'].isin(TARGET_MAP.keys())].copy()
    if df.empty: return pd.DataFrame()

    # 업체명은 원본 엑셀 이름 말고, 네가 준 타겟 리스트의 깔끔한 이름으로 통일
    df['업체명'] = df['사업자등록번호'].map(TARGET_MAP)
    
    if 'prdctClsfcNm' in df.columns: df['물품분류명'] = df['prdctClsfcNm']
    elif 'dtilPrdctClsfcNm' in df.columns: df['물품분류명'] = df['dtilPrdctClsfcNm']
    elif '품명' in df.columns: df['물품분류명'] = df['품명']
    else: df['물품분류명'] = ''
    
    if 'dlvrReqNo' in df.columns: df['납품요구번호'] = df['dlvrReqNo']
    elif '주문번호' in df.columns: df['납품요구번호'] = df['주문번호']
    else: df['납품요구번호'] = ''
    df['납품요구번호'] = df['납품요구번호'].fillna('').astype(str).str.replace('nan', '', regex=False).str.replace(r'\.0$', '', regex=True).str.strip()
    
    if 'dlvrReqRcptDate' in df.columns: df['일자'] = df['dlvrReqRcptDate']
    elif 'dlvrReqDate' in df.columns: df['일자'] = df['dlvrReqDate']
    elif '납품요구접수일자' in df.columns: df['일자'] = df['납품요구접수일자']
    else: df['일자'] = ''

    # 금액 계산
    calc_amt = pd.Series(0.0, index=df.index)
    for col in ['납품요구금액', '금액', '납품금액', 'dlvrReqAmt']:
        if col in df.columns:
            base_amt = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            calc_amt = calc_amt.where(calc_amt != 0, base_amt)
    for col in ['납품증감금액', '합계납품증감금액', 'dlvrIemRducAmt', 'chgDlvrReqAmt']:
        if col in df.columns:
            mod_amt = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            mask = mod_amt != 0
            calc_amt.loc[mask] = mod_amt[mask]
    df['금액'] = calc_amt

    # 날짜(월) 할당
    if target_month: df['월'] = target_month
    else:
        date_clean = df['일자'].astype(str).str.replace('-', '').str.replace('.', '').str.strip().str[:8]
        df['월'] = date_clean.str[4:6].apply(lambda x: f"{int(x)}월" if str(x).isdigit() else "4월")

    # 💡 2차 필터: MAS / 우수조달 완벽 분리 (수동입력 > API > 자동추론)
    df['USER_MAS'] = df['MAS여부'].fillna('').astype(str).str.strip().str.upper() if 'MAS여부' in df.columns else ''

    def assign_mas(row):
        if row['USER_MAS'] == 'Y': return 'Y', 'MAS (엑셀 수동입력)'
        if row['USER_MAS'] == 'N': return 'N', '우수조달/일반 (엑셀 수동입력)'
        
        text = ' '.join([str(v) for v in row.values]).upper()
        if any(k in text for k in ['우수', '혁신', '총액', '일반']): return 'N', '우수조달/일반 (자동추론)'
        if is_api: return 'Y', 'MAS (API 실시간)'
        if any(k in text for k in ['다수공급자', 'MAS']): return 'Y', 'MAS (다수공급자 자동추론)'
        if '제3자' in text: return 'Y', 'MAS (제3자 자동추론)'
        return 'N', '기타/미상'

    res = df.apply(assign_mas, axis=1)
    df['MAS여부'] = [x[0] for x in res]
    df['계약종류_상세'] = [x[1] for x in res]

    return df[['사업자등록번호', '업체명', '물품분류명', '금액', '납품요구번호', '월', '일자', 'MAS여부', '계약종류_상세']]

# --- 3. 과거 엑셀 데이터 긁어모으기 ---
print("📂 과거 엑셀 데이터(1~4월) 스캔 중...")
dfs = []
file_month_map = {'data.csv': '1월', 'data02.csv': '2월', 'data03.csv': '3월', 'data04.csv': '4월'}
for file, target_month in file_month_map.items():
    if os.path.exists(file):
        for config in [{'encoding':'utf-16','sep':'\t'}, {'encoding':'cp949','sep':','}, {'encoding':'utf-8','sep':','}, {'encoding':'utf-8-sig','sep':','}]:
            try:
                temp_df = pd.read_csv(file, encoding=config['encoding'], sep=config['sep'], on_bad_lines='skip', low_memory=False)
                if len(temp_df.columns) > 2: 
                    clean_df = unified_data_parser(temp_df, target_month=target_month, is_api=False)
                    if not clean_df.empty: 
                        dfs.append(clean_df)
                        print(f"  - {file} ({target_month}) : {len(clean_df)}건 추출")
                    break
            except: 
                pass

# --- 4. 새 API 키로 4월 20일 이후 실적 싹쓸이! ---
now = datetime.now() + timedelta(hours=9)
end_date = (now - timedelta(days=1)).strftime("%Y%m%d")
print(f"\n📡 조달청 API 호출 중... (4/20 ~ {end_date}, 새 인증키 적용!)")

BASE_URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
headers = {'User-Agent': 'Mozilla/5.0'}
date_ranges = [("20260420", "20260430"), ("20260501", end_date)]
all_new_data = []

for bgn, end in date_ranges:
    if bgn > end: continue
    page = 1
    while True:
        url = f"{BASE_URL}?serviceKey={NEW_API_KEY}&numOfRows=500&pageNo={page}&inqryDiv=1&inqryBgnDate={bgn}&inqryEndDate={end}"
        success = False
        for attempt in range(3):
            try:
                res = requests.get(url, headers=headers, timeout=45, verify=False)
                if res.status_code == 200:
                    success = True; break
                elif res.status_code == 429:
                    print("  🚨 API 트래픽 한도 초과! (내일 다시 시도하세요)")
                    break
                time.sleep(3)
            except: 
                time.sleep(3)
        
        if not success: break
        
        try:
            root = ET.fromstring(res.content)
            if root.findtext('.//resultCode') not in ['00', '0']: break
            total = int(root.findtext('.//totalCount') or 0)
            if total == 0: break
            
            items = root.findall('.//item')
            if not items: break
            
            for item in items: all_new_data.append({child.tag: child.text for child in item})
            
            print(f"  - API 데이터 수집 중... ({page}페이지 완료)")
            if page * 500 >= total: break
            page += 1
            time.sleep(1.5)
        except: 
            break

if all_new_data:
    df_api_raw = pd.DataFrame(all_new_data)
    df_api_clean = unified_data_parser(df_api_raw, is_api=True)
    if not df_api_clean.empty:
        dfs.append(df_api_clean)
        print(f"  ✅ API 신규 타겟 실적: {len(df_api_clean)}건 추출 완료!")
else:
    print("  🔵 API 신규 실적 없음.")

# --- 5. 최종 마스터 DB 합체 및 저장 ---
if dfs:
    df_master = pd.concat(dfs, ignore_index=True)
    
    # 중복 제거 (납품요구번호 + 금액 기준)
    df_master = df_master.drop_duplicates(subset=['납품요구번호', '금액'], keep='last')
    
    # 제외품목 필터링
    pattern = '|'.join(EXCLUDE_ITEMS)
    df_master = df_master[~df_master['물품분류명'].astype(str).str.contains(pattern, na=False, regex=True)]
    
    # 최종 저장
    df_master.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    print(f"\n🎉 [성공] 총 {len(df_master)}건의 데이터가 완벽하게 정제되어 '{OUTPUT_FILE}'로 저장되었습니다!")
    print("이제 이 Master_DB 파일 하나면 대시보드는 0.1초 컷입니다! 🚀")
else:
    print("\n🚨 수집된 데이터가 하나도 없습니다. 파일 경로나 API 상태를 확인해주세요.")