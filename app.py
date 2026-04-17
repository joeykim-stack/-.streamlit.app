import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="데이터 진단 시스템", layout="wide")

st.markdown("# 🚨 긴급 진단 모드: 데이터가 왜 안 보일까?")
st.markdown("파이썬이 혼자 숨기고 있던 에러와 파일 상태를 전부 화면에 출력합니다.")
st.markdown("---")

# 1. 파일 존재 여부 확인
st.markdown("### 🔍 1단계: 현재 폴더 파일 목록 확인")
current_files = os.listdir('.')
st.write("현재 파이썬이 보고 있는 폴더 안의 파일들:", current_files)

st.markdown("---")
st.markdown("### 🛠️ 2단계: CSV 파일 정밀 분석")
target_files = ['data.csv', 'data02.csv', 'data02.cvs', 'data03.csv', 'data04.csv']

for file in target_files:
    if file in current_files:
        st.success(f"🟢 **{file}** 파일이 존재합니다!")
        
        try:
            # 인코딩 테스트
            try:
                df = pd.read_csv(file, encoding='utf-8')
                enc = 'UTF-8'
            except UnicodeDecodeError:
                df = pd.read_csv(file, encoding='cp949')
                enc = 'CP949(윈도우 한글)'
                
            st.info(f"✅ 인코딩 '{enc}' 형식으로 파일 읽기 성공! (데이터 크기: 총 {df.shape[0]}줄)")
            
            # 컬럼명 출력 (가장 의심되는 부분!)
            df.rename(columns=lambda x: str(x).strip(), inplace=True)
            columns = list(df.columns)
            st.write(f"**[{file} 파일의 실제 컬럼명 목록]** (여기서 이름이 다르면 데이터를 못 가져옵니다)")
            st.write(columns)
            
            # 필수 컬럼 검사
            missing_cols = []
            if '업체명' not in columns and '계약업체명' not in columns: missing_cols.append("업체명")
            if '물품분류명' not in columns and '품명' not in columns: missing_cols.append("물품분류명")
            if '납품요구금액' not in columns and '금액' not in columns: missing_cols.append("납품요구금액")
            
            if missing_cols:
                st.error(f"❌ 우리 코드에 필요한 컬럼({missing_cols})이 이 파일에 없습니다. 위 컬럼 목록을 보고 진짜 이름을 알려주세요!")
            else:
                st.success("✅ 필수 컬럼이 모두 정상적으로 존재합니다!")
                
        except Exception as e:
            st.error(f"❌ {file} 파일을 여는 중 알 수 없는 에러 발생: {e}")
            
    else:
        st.warning(f"🔴 **{file}** 파일이 이 폴더에 없습니다. (업로드가 안 되었거나 이름이 다릅니다)")

st.markdown("---")
st.info("💡 **중찬아, 이 화면이 뜨면 캡처해서 보여주거나, 빨간색(❌, 🔴)으로 뜬 에러 내용만 긁어서 나한테 꼭 알려줘! 10초 만에 원인 찾아줄게!**")
