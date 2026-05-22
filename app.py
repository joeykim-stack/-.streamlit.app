import streamlit as st
from supabase import create_client

# 설정 (Secrets에서 불러옴)
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("🔍 데이터베이스 경로 및 권한 진단기")

if st.button("진단 실행"):
    try:
        # 테이블 접근 테스트
        response = supabase.table("procurement_data").select("count").limit(1).execute()
        st.success("🎉 테이블 접근 성공! 권한도 정상입니다.")
    except Exception as e:
        st.error(f"🚨 에러 상세 내용: {str(e)}")
        st.info("💡 힌트: 'Table ... does not exist'라고 나오면, 테이블 이름을 확인하세요.")
        st.info("💡 힌트: 'permission denied'라고 나오면, RLS 정책을 Disable 해야 합니다.")
