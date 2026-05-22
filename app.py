import streamlit as st
from supabase import create_client

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

if st.button("데이터 딱 1건만 넣어보기"):
    # 우리가 Supabase SQL Editor에서 만든 테이블 컬럼명을 맞춰야 해
    test_data = {
        "사업자등록번호": "1234567890", 
        "업체명": "테스트업체",
        "물품분류명": "영상감시장치",
        "납품요구번호": "TEST_00001",
        "일자": "20260522",
        "전체계약금액": 100000
    }
    
    try:
        # insert 대신 upsert 사용 (중복 시 업데이트)
        response = supabase.table("procurement_data").upsert(test_data).execute()
        st.success("🎉 성공! 이제 이 형식대로 1만 건을 밀어넣으면 돼!")
    except Exception as e:
        # 에러 내용을 화면에 출력
        st.error(f"🚨 에러 내용: {str(e)}")
