import pandas as pd

# 1. 파일 불러오기 (공공데이터는 보통 cp949 인코딩)
file_name = 'raw04.csv' # 다운받은 파일 이름으로 변경
try:
    df = pd.read_csv(file_name, encoding='cp949')
except:
    df = pd.read_csv(file_name, encoding='utf-8-sig')

# 2. 타겟 업체 리스트
TARGET_COMPANIES = ["마이크로시스템", "핀텔", "웹게이트", "크리에이티브넷", "두원전자통신", "올인원 코리아", "티제이원", "앤다스", "지성이엔지", "송우인포텍", "렉스젠", "비티에스", "솔디아", "홍석", "비엔에스테크", "디케이앤트", "제이한테크", "그린아이티코리아", "펜타게이트", "한국아이티에스", "미르텍", "포딕스시스템", "명광", "뉴코리아전자통신", "오티에스", "아라드네트웍스", "시큐인포", "센텍", "원우이엔지", "경림이앤지", "진명아이앤씨", "디라직", "알엠텍", "아이엔아이", "지인테크", "다누시스", "에코아이넷", "사이테크놀로지스", "인텔리빅스", "한국씨텍", "아이즈온솔루션", "대신네트웍스", "새움", "이노뎁", "포소드", "에스카", "제노시스", "디지탈라인", "세오", "포커스에이아이", "비알인포텍"]

# 3. 필요한 컬럼 추출 및 정제
# (실제 컬럼명이 조금씩 다를 수 있으니 유연하게 찾기)
c_corp = next((c for c in df.columns if '업체명' in c), None)
c_item = next((c for c in df.columns if '물품분류명' in c), None)
c_method = next((c for c in df.columns if '계약체결형태' in c or '계약유형' in c), None)
c_amt = next((c for c in df.columns if '납품요구금액' in c or '금액' in c), None)

if all([c_corp, c_item, c_method, c_amt]):
    # '제3자단가' 필터링 (필요 시)
    df = df[df[c_method].astype(str).str.contains('제3자단가', na=False)]
    
    # 타겟 업체 필터링
    df_filtered = df[df[c_corp].astype(str).str.contains('|'.join(TARGET_COMPANIES), na=False)].copy()
    
    # 최종 데이터프레임 조립
    final_df = pd.DataFrame()
    final_df['업체명'] = df_filtered[c_corp].astype(str).str.strip()
    final_df['물품분류명'] = df_filtered[c_item].astype(str).str.strip()
    final_df['계약유형'] = df_filtered[c_method].astype(str).str.strip()
    final_df['금액'] = pd.to_numeric(df_filtered[c_amt].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # 4. 결과 저장
    save_name = 'data04.csv'
    final_df.to_csv(save_name, index=False, encoding='utf-8-sig')
    print(f"✅ 다이어트 성공! 총 {len(final_df)}건의 데이터가 {save_name}로 저장되었습니다.")
else:
    print("❌ 컬럼을 찾지 못했습니다. 원본 파일의 컬럼명을 확인해주세요.")
