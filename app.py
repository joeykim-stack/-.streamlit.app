# --- 6. 사이드바 필터 (초강력 방어 로직 적용) ---
with st.sidebar:
    st.header("🔍 분석 필터")
    
    # 1. 데이터가 있는지 확실하게 체크하고 리스트 만들기
    if df_total.empty:
        st.error("⚠️ 데이터를 찾을 수 없습니다. (CSV 파일 누락 또는 API 대기 중)")
        all_items = []
    else:
        # 빈 값 제거하고 문자열로 변환 후 정렬 (에러 원천 차단)
        all_items = sorted(df_total['물품분류명'].dropna().astype(str).unique())
    
    # 2. 세션 스테이트 안전 초기화 (꼬임 방지)
    if 'filter_items' not in st.session_state:
        st.session_state.filter_items = all_items
    else:
        # 기존 세션에 있던 값 중, 현재 all_items에 '실제로 있는 것만' 남기기 (스트림릿 에러 방지)
        valid_items = [item for item in st.session_state.filter_items if item in all_items]
        st.session_state.filter_items = valid_items

    # 3. 전체 / 해제 버튼
    col1, col2 = st.columns(2)
    if col1.button("✅ 전체"): 
        st.session_state.filter_items = all_items
    if col2.button("❌ 해제"): 
        st.session_state.filter_items = []

    # 4. 품목 선택 위젯 (데이터가 없어도 무조건 화면에 보이도록 고정)
    selected = st.multiselect(
        "품목 상세 선택", 
        options=all_items, 
        default=st.session_state.filter_items
    )

# --- 7. 메인 차트 및 데이터 화면 ---
if df_total.empty:
    st.warning("🚨 현재 분석할 데이터가 없습니다. 폴더에 'data_mini.csv', 'data04.csv' 파일이 있는지 확인하거나, 조달청 실시간 API가 연동될 때까지 기다려주세요.")

elif not selected:
    st.info("👈 왼쪽 필터에서 분석할 품목을 1개 이상 선택해주세요.")

else:
    # 선택된 품목만 필터링
    df_f = df_total[df_total['물품분류명'].isin(selected)]
    
    # 지표 요약
    c1, c2 = st.columns(2)
    c1.metric("💰 누적 매출액", f"{df_f['금액'].sum():,.0f}원")
    c2.metric("📝 총 계약 건수", f"{len(df_f):,}건")

    st.markdown("---")

    # 시각화 차트
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🏆 업체별 매출 순위")
        top10 = df_f.groupby('업체명')['금액'].sum().nlargest(10).reset_index()
        fig_bar = px.bar(top10, x='업체명', y='금액', text_auto='.2s', color='금액')
        fig_bar.update_layout(xaxis_title="업체명", yaxis_title="매출액")
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with col_b:
        st.subheader("🍩 품목별 점유율")
        fig_pie = px.pie(df_f, names='물품분류명', values='금액', hole=0.4)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")

    # 상세 데이터 표
    st.subheader("📋 상세 분석 데이터")
    st.dataframe(df_f.sort_values('금액', ascending=False), use_container_width=True)

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim. Data from Public Data Portal.</center>", unsafe_allow_html=True)
