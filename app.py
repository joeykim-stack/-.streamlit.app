import streamlit as st
from supabase import create_client

# 설정
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("🔍 DB 테이블 진단기")

# API를 통해 실제 존재하는 테이블 목록을 가져오는 코드
if st.button("내 DB에 있는 테이블 목록 보기"):
    try:
        # Supabase API로 정보 스키마 조회
        response = supabase.table("information_schema.tables").select("table_name").eq("table_schema", "public").execute()
        
        # 목록 출력
        st.write("### ✅ 발견된 테이블 목록:")
        st.write(response.data)
        
        st.info("💡 위 목록에서 `procurement_data`라는 이름이 정확히 어떻게 적혀있는지 봐봐!")
    except Exception as e:
        st.error(f"🚨 에러 발생: {str(e)}")
