import requests
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

print("🤖 [오토 머지 봇 V2.2] 조달청 신규 실적 수집 및 Master DB 업데이트 시작...\n")

# --- 1. 설정 ---
API_KEY = "df5a1c97ab56593d5e99889ae1c030bfe0b5e9d924ffba9bae3712c8bb1ad75c" 
TARGET_FILE = "target_companies.csv"
MASTER_DB_FILE = "Master_DB.csv"

# 오늘 기준으로 어제(D-1)와 그제(D-2) 이틀 치 데이터를 긁어와서 누락 방지!
today = datetime.now()
bgn_date = (today - timedelta(days=2)).strftime("%Y%m%d")
end_date = (today - timedelta(days=1)).strftime("%Y%m%d")

print(f"📅 타겟 스캔 기간: {bgn_date} ~ {end_date}")

# --- 2. 54개 타겟 업체 로드 ---
TARGET_MAP = {}
try:
    for enc in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
        try:
            raw_target = pd.read_csv(TARGET_FILE, encoding=enc, header=None, dtype=str)
            break
        except: pass
        
    header_idx = None
    for idx, row in raw_target.iterrows():
        if row.astype(str).str.contains('사업자등록번호').any():
            header_idx = idx; break
            
    columns = [str(c).strip() for c in raw_target.iloc[header_idx].tolist()]
    df_target = raw_target.iloc[header_idx+1:].copy()
    df_target.columns = columns
    
    biz_col = [c for c in df_target.columns if '사업자등록번호' in c][0]
    name_col = [c for c in df_target.columns if '계약업체' in c or '업체명' in c][0]
    
    df_target[biz_col] = df_target[biz_col].fillna('').str.replace('-', '', regex=False).str.replace(r'\.0$', '', regex=True).str.strip()
    TARGET_MAP = dict(zip(df_target[biz_col], df_target[name_col]))
    print(f"✅ 타겟 업체 {len(TARGET_MAP)}개사 레이더 장착 완료!\n")
except Exception as e:
    print(f"🚨 타겟 업체 파일 로드 실패: {e}")
    exit()

# --- 3. 조달청 API 호출 ---
# 💡 [핵심 버그 수정] 주소에서 '05' 제거! 진짜 열려있는 대문으로 접속.
BASE_URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
headers = {'User-Agent': 'Mozilla/5.0'}
all_new_data = []

page = 1
while True:
    url = f"{BASE_URL}?serviceKey={API_KEY}&numOfRows=500&pageNo={page}&inqryDiv=1&inqryBgnDate={bgn_date}&inqryEndDate={end_date}"
    success = False
    
    for attempt, wait_time in enumerate([2, 4, 8]):
        try:
            res = requests.get(url, headers=headers, timeout=45, verify=False)
            if res.status_code == 200:
                success = True; break
            elif res.status_code == 429:
                print("  🚨 트래픽 한도 초과(429)! 스크립트를 종료합니다.")
                exit()
        except: pass
        time.sleep(wait_time)
        
    if not success:
        print(f"  ⚠️ {page}페이지 통신 실패. 지금까지 모은 것만 처리합니다.")
        break
        
    try:
        root = ET.fromstring(res.content)
        if root.findtext('.//resultCode') not in ['00', '0']: break
        
        total = int(root.findtext('.//totalCount') or 0)
        if total == 0: 
            print("  🔵 해당 기간에 전국 조달청 신규 실적이 없습니다.")
            break
            
        items = root.findall('.//item')
        if not items: break
        
        for item in items:
            all_new_data.append({child.tag: child.text for child in item})
            
        print(f"  📡 스캔 중... ({page}페이지 / 전체 {total}건 중)")
        
        if page * 500 >= total: break
        page += 1
        time.sleep(1.5)
    except Exception as e:
        print(f"  🚨 파싱 에러 발생: {e}")
        break

# --- 4. 데이터 정제 및 Master DB 자동 합체 ---
if all_new_data:
    df_api = pd.DataFrame(all_new_data)
    biz_col = 'bizrno' if 'bizrno' in df_api.columns else None
    
    if biz_col:
        df_api[biz_col] = df_api[biz_col].fillna('').str.replace('-', '', regex=False).str.strip()
        df_target_only = df_api[df_api[biz_col].isin(TARGET_MAP.keys())].copy()
        
        if not df_target_only.empty:
            df_target_only['업체명'] = df_target_only[biz_col].map(TARGET_MAP)
            
            # API 영문 컬럼명을 Master DB 한글 컬럼명에 맞게 매핑
            df_target_only = df_target_only.rename(columns={
                'bizrno': '사업자등록번호',
                'prdctClsfcNm': '물품분류명',
                'dlvrReqNo': '납품요구번호',
                'dlvrReqRcptDate': '일자',
                'dlvrReqAmt': '전체계약금액'
            })
            
            if '전체계약금액' in df_target_only.columns:
                df_target_only['전체계약금액'] = pd.to_numeric(df_target_only['전체계약금액'], errors='coerce').fillna(0)
            
            if '일자' in df_target_only.columns:
                df_target_only['일자'] = df_target_only['일자'].astype(str).str.replace('-', '').str[:8]
                df_target_only['월'] = df_target_only['일자'].str[4:6].apply(lambda x: f"{int(x)}월" if x.isdigit() else "미상")

            if os.path.exists(MASTER_DB_FILE):
                df_master = pd.read_csv(MASTER_DB_FILE, encoding='utf-8-sig', dtype=str)
                df_combined = pd.concat([df_master, df_target_only], ignore_index=True)
                
                if '납품요구번호' in df_combined.columns and '전체계약금액' in df_combined.columns:
                    df_combined = df_combined.drop_duplicates(subset=['납품요구번호', '물품분류명', '전체계약금액'], keep='last')
                
                df_combined.to_csv(MASTER_DB_FILE, index=False, encoding='utf-8-sig')
                print(f"\n🎉 [업데이트 성공] 기존 Master DB에 신규 실적 {len(df_target_only)}건을 성공적으로 이어 붙였습니다!")
            else:
                df_target_only.to_csv(MASTER_DB_FILE, index=False, encoding='utf-8-sig')
                print(f"\n🎉 [새 DB 생성] Master DB 파일이 없어서 새로 만들고 {len(df_target_only)}건을 저장했습니다!")
                
            print("👉 이제 대시보드(Streamlit)에서 [캐시 비우기] 버튼만 누르면 최신 실적이 반영됩니다!")
        else:
            print("\n🔵 스캔 완료. 타겟 54개사의 새로운 실적이 없습니다.")
else:
    print("\n🔵 조달청에 업데이트된 새로운 데이터가 없습니다.")