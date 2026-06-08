import streamlit as st
import pandas as pd
from supabase import create_client
import os

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="조달청 최종 실적 분석")
st.markdown("""<style>.main-title { font-size:32px; font-weight:800; color:#1E3A8A; }</style>""", unsafe_allow_html=True)
st.markdown('<div class="main-title">🏆 조달청 실적 상세 분석 리포트</div>', unsafe_allow_html=True)

# 2. Supabase 연결
@st.cache_resource
def get_supabase():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except:
        return None

supabase = get_supabase()

# 3. 데이터 로드 및 정제
@st.cache_data(ttl=600)
def load_and_process():
    base_file = "Master_DB.csv"
    if os.path.exists(base_file):
        df = pd.read_csv(base_file)
    else:
        return pd.DataFrame()
    
    if supabase:
        try:
            response = supabase.table("procurement_data").select("*").execute()
            db_df = pd.DataFrame(response.data)
            if not db_df.empty:
                df = pd.concat([df, db_df], ignore_index=True)
        except:
            pass

    df = df.drop_duplicates(subset=['납품요구번호'], keep='first')
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    df['DateTime'] = pd.to_datetime(df['일자'].astype(str), format='%Y%m%d', errors='coerce')
    df['업체명'] = df['업체명'].fillna("알수없음").astype(str).str.strip()
    return df

df = load_and_process()

# 4. 분석 엔진 (테이블 구조 재정의)
if not df.empty:
    df['월'] = df['DateTime'].dt.month
    
    # 기초 피벗
    pivot = df.pivot_table(index='업체명', columns='월', values='전체계약금액', aggfunc='sum', fill_value=0)
    
    # 1~12월 컬럼 강제 생성 (데이터 없어도 0으로 채움)
    for m in range(1, 13):
        if m not in pivot.columns:
            pivot[m] = 0
            
    # 분기 합계 계산
    pivot['1분기 합계'] = pivot[[1, 2, 3]].sum(axis=1)
    pivot['2분기 합계'] = pivot[[4, 5, 6]].sum(axis=1)
    pivot['3분기 합계'] = pivot[[7, 8, 9]].sum(axis=1)
    pivot['4분기 합계'] = pivot[[10, 11, 12]].sum(axis=1)
    
    # 총 합계
    pivot['총 합계'] = pivot[[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]].sum(axis=1)
    
    # 컬럼 이름 예쁘게 변경 및 순서 정렬
    col_mapping = {
        1: '1월', 2: '2월', 3: '3월', 4: '4월', 5: '5월', 6: '6월',
        7: '7월', 8: '8월', 9: '9월', 10: '10월', 11: '11월', 12: '12월'
    }
    pivot = pivot.rename(columns=col_mapping)
    
    desired_order = [
        '1월', '2월', '3월', '1분기 합계',
        '4월', '5월', '6월', '2분기 합계',
        '7월', '8월', '9월', '3분기 합계',
        '10월', '11월', '12월', '4분기 합계', '총 합계'
    ]
    pivot = pivot[desired_order]
    pivot = pivot.sort_values(by='총 합계', ascending=False)
    
    # 5. 최종 출력 (안전하게 문자열 변환)
    display_df = pivot.map(lambda x: f"{int(x):,}원") if hasattr(pivot, 'map') else pivot.applymap(lambda x: f"{int(x):,}원")
    
    st.subheader("📋 업체별 월/분기 실적 종합 분석표")
    st.dataframe(display_df, use_container_width=True)
    
    # 데이터 다운로드
    st.download_button("📥 분석 데이터 CSV 저장", pivot.to_csv().encode('utf-8-sig'), "조달_실적_종합.csv")
else:
    st.warning("데이터 로드에 실패했습니다.")
