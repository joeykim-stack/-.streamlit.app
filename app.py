import streamlit as st
from supabase import create_client

# 1. URL과 KEY 확인
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]

st.title("🔍 데이터베이스 경로 진단기")

if st.button("진단 시작"):
    try:
        # Supabase 클라이언트 생성
        supabase = create_client(url, key)
        
        # 1. 연결 및 테이블 접근 시도
        st.write(f"📍 연결 시도 중인 URL: {url}")
        
        # 2. 실제 데이터 1건 조회를 통해 테이블 경로 확인
        # 만약 테이블이 'public' 스키마가 아니라면 아래 코드가 에러를 냅니다.
        response = supabase.table("procurement_data").select("*").limit(1).execute()
        
        st.success("🎉 성공! 데이터베이스와 테이블 경로가 완벽합니다.")
        st.write("테이블 데이터:", response.data)
        
    except Exception as e:
        st.error(f"🚨 진단 결과 에러: {str(e)}")
        st.write("---")
        st.write("💡 **체크리스트:**")
        st.write("1. URL이 `https://프로젝트ID.supabase.co` 형식이 맞나요? (대시보드 URL과 다릅니다!)")
        st.write("2. 테이블 이름이 SQL Editor에서 `public.procurement_data`로 생성되었나요?")
        st.write("3. 에러 내용 중 'table \"procurement_data\" does not exist'라고 나온다면, 테이블을 다시 만들어야 합니다.")
