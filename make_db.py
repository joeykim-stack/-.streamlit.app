import pandas as pd
import os
import warnings
import re

warnings.filterwarnings('ignore')

print("🚀 [오프라인 DB 생성기 V93] 정밀 타격 파서 가동...\n")

# --- 1. 환경 설정 ---
TARGET_FILE = "target_companies.csv"
CCTV_ITEMS_FILE = "cctv_items.txt"
OUTPUT_FILE = "Master_DB.csv"
INPUT_FILES = ["Jan.csv", "Feb.csv", "Mar.csv", "Apr.csv", "May.csv"]

# --- 2. 텍스트 파일(상세품목) 로드 ---
cctv_items = []
if os.path.exists(CCTV_ITEMS_FILE):
    for enc in ['utf-8-sig', 'utf-8', 'cp949']:
        try:
            with open(CCTV_ITEMS_FILE, 'r', encoding=enc) as f:
                cctv_items = [line.strip() for line in f if line.strip()]
            print(f"✅ 영상감시장치 상세품목 리스트 {len(cctv_items)}개 로드 완료!")
            break
        except:
            pass
else:
    print(f"🚨 {CCTV_ITEMS_FILE} 파일이 없습니다! '전체계약금액'만 집계됩니다.")

# --- 3. 타겟 업체 로드 ---
try:
    # 업체 목록 파일은 위에 쓸데없는 4줄이 있었으므로 skiprows=4 유지
    df_target = pd.read_csv(TARGET_FILE, encoding='utf-8-sig', skiprows=4)
    df_target['사업자등록번호'] = df_target['사업자등록번호'].astype(str).str.replace('-', '').str.strip()
    TARGET_MAP = dict(zip(df_target['사업자등록번호'], df_target['계약업체']))
    print(f"✅ 타겟 업체 {len(TARGET_MAP)}개 로드 완료! (사업자등록번호 철통 방어)\n")
except Exception as e:
    print(f"🚨 타겟 업체 파일({TARGET_FILE})을 읽을 수 없습니다: {e}")
    exit()

# --- 4. 데이터 처리 함수 ---
def process_csv_file(file_path):
    if not os.path.exists(file_path):
        print(f"  ➖ {file_path} 파일이 존재하지 않아 건너뜁니다.")
        return pd.DataFrame()

    df = None
    
    # 💡 [핵심 버그 수정] 조달청 원본 엑셀(CSV)은 첫 줄부터 정상이므로 skiprows 제외!
    configs = [
        {'enc': 'utf-8-sig', 'sep': ','},
        {'enc': 'cp949', 'sep': ','},
        {'enc': 'euc-kr', 'sep': ','},
        {'enc': 'utf-8', 'sep': ','}
    ]
    
    for cfg in configs:
        try:
            temp_df = pd.read_csv(
                file_path, 
                encoding=cfg['enc'], 
                sep=cfg['sep'], 
                on_bad_lines='skip',
                low_memory=False, 
                dtype=str # 모든 열을 텍스트로 읽어 오류 최소화
            )
            if len(temp_df.columns) > 3:
                df = temp_df
                break
        except: 
            pass
        
    if df is None or df.empty:
        print(f"  🚨 {file_path} 파일 열기 실패.")
        return pd.DataFrame()

    df_clean = pd.DataFrame()
    
    biz_col = '업체사업자등록번호' if '업체사업자등록번호' in df.columns else ('사업자등록번호' if '사업자등록번호' in df.columns else None)
    if not biz_col: 
        print(f"  🚨 {file_path} 안에 사업자등록번호 칼럼이 없습니다.")
        return pd.DataFrame()
    
    df[biz_col] = df[biz_col].astype(str).str.replace('-', '').str.replace('.0', '', regex=True).str.strip()
    df = df[df[biz_col].isin(TARGET_MAP.keys())].copy()
    if df.empty: 
        print(f"  🔵 {file_path}: 파일은 정상이나, 타겟 업체의 실적이 없습니다.")
        return pd.DataFrame()

    df_clean['사업자등록번호'] = df[biz_col]
    df_clean['업체명'] = df[biz_col].map(TARGET_MAP)

    item_cols = ['세부품명', '품명', '물품분류명']
    df_clean['물품분류명'] = ''
    for col in item_cols:
        if col in df.columns:
            df_clean['물품분류명'] = df[col]
            break

    no_cols = ['납품요구번호', '주문번호']
    df_clean['납품요구번호'] = ''
    for col in no_cols:
        if col in df.columns:
            df_clean['납품요구번호'] = df[col].astype(str).str.replace('nan', '').str.replace(r'\.0$', '', regex=True)
            break

    date_cols = ['납품요구접수일자', '납품요구일자', '일자']
    df_clean['일자'] = ''
    for col in date_cols:
        if col in df.columns:
            df_clean['일자'] = df[col].astype(str).str.replace('-', '').str.replace('.', '').str.strip()
            break
            
    df_clean['월'] = df_clean['일자'].str[:8].str[4:6].apply(lambda x: f"{int(x)}월" if str(x).isdigit() else "미상")

    # 금액 계산
    calc_amt = pd.Series(0.0, index=df.index)
    for col in ['납품금액', '납품요구금액', '금액']:
        if col in df.columns:
            base_amt = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            calc_amt = calc_amt.where(calc_amt != 0, base_amt)
    
    for col in ['합계납품증감금액', '납품증감금액']:
        if col in df.columns:
            mod_amt = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            mask = mod_amt != 0
            calc_amt.loc[mask] = mod_amt[mask]
            
    df_clean['전체계약금액'] = calc_amt
    df_clean['영상감시장치_계약금액'] = 0.0
    df_clean['영상감시여부'] = 'N'

    if cctv_items:
        cctv_pattern = '|'.join([re.escape(item) for item in cctv_items])
        mask_cctv = df_clean['물품분류명'].astype(str).str.contains(cctv_pattern, regex=True, na=False)
        df_clean.loc[mask_cctv, '영상감시여부'] = 'Y'
        df_clean.loc[mask_cctv, '영상감시장치_계약금액'] = calc_amt

    # MAS / 우수조달 추론
    str_cols = df.select_dtypes(include=['object', 'string']).columns
    all_text = df[str_cols].apply(lambda row: ' '.join(row.fillna('').astype(str)), axis=1).str.upper()

    df_clean['MAS여부'] = 'N'
    df_clean['계약종류_상세'] = '기타/미상'

    if 'MAS여부' in df.columns:
        user_mas = df['MAS여부'].fillna('').astype(str).str.strip().str.upper()
        df_clean.loc[user_mas == 'Y', 'MAS여부'] = 'Y'
        df_clean.loc[user_mas == 'Y', '계약종류_상세'] = 'MAS (수동입력)'
        df_clean.loc[user_mas == 'N', 'MAS여부'] = 'N'
        df_clean.loc[user_mas == 'N', '계약종류_상세'] = '우수조달 (수동입력)'

    mas_mask = df_clean['MAS여부'] == 'N' 
    usu_mask = all_text.str.contains('우수|혁신|총액|일반', regex=True)
    pure_mas = all_text.str.contains('다수공급자|MAS', regex=True)
    je3_mas = all_text.str.contains('제3자', regex=True)
    
    df_clean.loc[mas_mask & (pure_mas | je3_mas) & ~usu_mask, 'MAS여부'] = 'Y'
    df_clean.loc[mas_mask & (pure_mas | je3_mas) & ~usu_mask, '계약종류_상세'] = 'MAS (자동추론)'
    df_clean.loc[mas_mask & usu_mask, '계약종류_상세'] = '우수조달/일반경쟁'

    print(f"  🟢 {file_path} 정제 완료: 타겟 실적 {len(df_clean)}건 추출")
    return df_clean

# --- 5. 실행 및 병합 ---
dfs = []
for file in INPUT_FILES:
    print(f"🔍 {file} 스캔 중...")
    res_df = process_csv_file(file)
    if not res_df.empty:
        dfs.append(res_df)

if dfs:
    df_master = pd.concat(dfs, ignore_index=True)
    df_master = df_master.drop_duplicates(subset=['납품요구번호', '물품분류명', '전체계약금액'], keep='last')
    
    df_master.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    print(f"\n🎉 [성공] 총 {len(df_master)}건의 데이터가 '{OUTPUT_FILE}'로 완벽하게 저장되었습니다!")
    print("  👉 이제 대시보드를 띄울 차례입니다! 🚀")
else:
    print("\n🚨 추출된 데이터가 없습니다.")