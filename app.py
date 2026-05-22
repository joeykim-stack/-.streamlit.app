# 1. 데이터 로드 엔진 (가장 안전한 방식)
@st.cache_data(ttl=600)
def load_analysis_data():
    # 1. Master_DB 로드 (기초 체력)
    base_df = pd.read_csv("Master_DB.csv") if os.path.exists("Master_DB.csv") else pd.DataFrame()
    
    # 2. Supabase 실시간 데이터 로드
    try:
        response = supabase.table("procurement_data").select("*").execute()
        db_df = pd.DataFrame(response.data)
    except:
        db_df = pd.DataFrame()
    
    # 3. [구조 개선] 베이스를 살리고 최신 데이터를 덧붙임
    if not db_df.empty:
        # 두 데이터를 합치되, API 데이터로 보완함
        combined_df = pd.concat([base_df, db_df], ignore_index=True)
        # 납품요구번호 기준 중복 제거 (파일 데이터와 DB 데이터를 통합)
        combined_df = combined_df.drop_duplicates(subset=['납품요구번호'], keep='last')
    else:
        combined_df = base_df
        
    # 데이터 정제 (테스트 데이터 제거)
    trash_data = ["테스트업체", "테스트", "확인필요", "000"]
    combined_df = combined_df[~combined_df['업체명'].isin(trash_data)]
    
    return combined_df
