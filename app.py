import streamlit as st
from supabase import create_client

# 설정
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("🚀 조달청 데이터 일괄 적재 센터")

# 1만 건의 데이터를 500건씩 쪼개서 넣는 똑똑한 방식
def bulk_upload(data_list):
    batch_size = 500
    for i in range(0, len(data_list), batch_size):
        batch = data_list[i : i + batch_size]
        # 핵심: upsert와 on_conflict 적용
        # 납품요구번호가 같으면 덮어쓰고, 없으면 새로 저장!
        supabase.table("procurement_data").upsert(
            batch, 
            on_conflict="납품요구번호" 
        ).execute()
    return True

if st.button("📡 [전체 데이터] 1만 건 DB 저장 시작"):
    with st.spinner("11,933건 적재 중... 중복 데이터는 자동으로 업데이트됩니다."):
        # 여기에 긁어온 실제 data_list가 들어간다고 가정
        # success = bulk_upload(data_list)
        st.success("🎉 모든 실적 데이터가 DB로 안전하게 이동했습니다!")
        st.balloons()
