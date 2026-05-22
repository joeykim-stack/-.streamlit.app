# [검증용] 세오 업체 데이터 정밀 추적 코드
st.subheader("🔍 업체 데이터 정밀 검증")
if st.button("세오 업체 데이터 분석"):
    # 1. Master_DB에서 세오 찾기
    df_base = pd.read_csv("Master_DB.csv")
    seo_base = df_base[df_base['업체명'].str.contains("세오", na=False)]
    st.write(f"Master_DB 세오 건수: {len(seo_base)}, 합계: {seo_base['전체계약금액'].sum():,.0f}")
    
    # 2. 실시간 DB에서 세오 찾기
    seo_db = df[df['업체명'].str.contains("세오", na=False)]
    st.write(f"실시간 DB 세오 건수: {len(seo_db)}, 합계: {seo_db['전체계약금액'].sum():,.0f}")
