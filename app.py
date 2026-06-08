import streamlit as st
import pandas as pd
from supabase import create_client
import os

# 1. 페이지 및 환경 설정
st.set_page_config(layout="wide", page_title="조달청 최종 실적 분석")
st.title("🏆 조달청 실적 상세 분석 리포트")

# 2. Supabase 연결 설정
@st.cache_resource
def get_supabase():
    try:
        # secrets에 설정된 SUPABASE_URL, SUPABASE_KEY가 필요해
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except:
        return None

supabase = get_supabase()

# 3. 데이터 로드 및 정제
@st.cache_data(ttl=600)
def load_data():
    # 파일 데이터 로드
    base_file = "Master_DB.csv"
    if os.path.exists(base_file):
        df = pd.read_csv(base_file)
    else:
        return pd.DataFrame()
    
    # 실시간 데이터 병합
    if supabase:
        try:
            response = supabase.table("procurement_data").select("*").execute()
            db_df = pd.DataFrame(response.data)
            if not db_df.empty:
                df = pd.concat([df, db_df], ignore_index=True)
        except:
            pass

    # 중복 제거 및 타입 변환
    df = df.drop_duplicates(subset=['납품요구번호'], keep='first')
    df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    df['일자'] = pd.to_datetime(df['일자'].astype(str), format='%Y%m%d', errors='coerce')
    df['월'] = df['일자'].dt.month
    df['업체명'] = df['업체명'].fillna("알수없음").astype(str).str.strip()
    return df

df = load_data()

# 4. 분석 로직 (월별/분기별 합계)
if not df.empty:
    # 월별 피벗 테이블 생성 (업체별)
    pivot = df.pivot_table(index='업체명', columns='월', values='전체계약금액', aggfunc='sum', fill_value=0)
    
    # 누락된 월 추가 (1~12월이 없으면 0으로 채움)
    for m in range(1, 13):
        if m not in pivot.columns:
            pivot[m] = 0
            
    # 분기 합계 계산
    pivot['1분기 합계'] = pivot[[1, 2, 3]].sum(axis=1)
    pivot['2분기 합계'] = pivot[[4, 5, 6]].sum(axis=1)
    pivot['3분기 합계'] = pivot[[7, 8, 9]].sum(axis=1)
    pivot['4분기 합계'] = pivot[[10, 11, 12]].sum(axis=1)
    pivot['총 합계'] = pivot[[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]].sum(axis=1)
    
    # 요청하신 순서대로 컬럼 재배치
    col_order = [
        1, 2, 3, '1분기 합계', 
        4, 5, 6, '2분기 합계', 
        7, 8, 9, '3분기 합계', 
        10, 11, 12, '4분기 합계', '총 합계'
    ]
    # 존재하는 컬럼만 선택하여 순서 적용
    available_cols = [c for c in col_order if c in pivot.columns]
    pivot = pivot[available_cols]
    
    # 총 합계 기준 정렬
    pivot = pivot.sort_values(by='총 합계', ascending=False)
    
    # 5. 안전한 문자열 포맷팅 출력 (스타일 함수 대신 값 자체를 변환)
    display_df = pivot.copy()
    for col in display_df.columns:
        display_df[col] = display_df[col].apply(lambda x: f"{int(x):,}원")
        
    st.subheader("📋 업체별 월/분기 실적 종합 분석표")
    st.dataframe(display_df, use_container_width=True)
    
    # 데이터 다운로드 버튼
    st.download_button("📥 분석 데이터 CSV 저장", pivot.to_csv().encode('utf-8-sig'), "조달_실적_종합_분석.csv")
else:
    st.warning("데이터가 없습니다.")
