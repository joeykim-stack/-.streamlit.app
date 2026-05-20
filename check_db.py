import os
import pandas as pd
from datetime import datetime

# 1. 파일 경로 확인
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_DB_FILE = os.path.join(BASE_DIR, "Master_DB.csv")

print(f"📍 시스템이 찾고 있는 DB 위치: {MASTER_DB_FILE}")

# 2. 파일 상태 확인
if not os.path.exists(MASTER_DB_FILE):
    print("🚨 앗! Master_DB.csv 파일이 이 경로에 없습니다!")
else:
    # 3. 파일 정보 출력
    file_stat = os.stat(MASTER_DB_FILE)
    mod_time = datetime.fromtimestamp(file_stat.st_mtime)
    print(f"✅ 파일 찾음! 마지막 수정 시간: {mod_time}")
    
    # 4. 데이터 건수 확인
    try:
        df = pd.read_csv(MASTER_DB_FILE, encoding='utf-8-sig', dtype=str)
        print(f"📊 현재 DB 총 데이터 건수: {len(df):,} 건")
        
        # 5. 마지막 업데이트 날짜 확인
        if '일자' in df.columns:
            last_date = df['일자'].dropna().max()
            print(f"📅 DB에 저장된 가장 최근 일자: {last_date}")
        else:
            print("⚠️ '일자' 컬럼이 없어 날짜 확인이 어렵습니다.")
            
    except Exception as e:
        print(f"🚨 파일 읽기 에러: {e}")
