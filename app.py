import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import os

# --- 1. 기본 설정 및 명품 디자인 CSS ---
st.set_page_config(page_title="조달청 타겟 전수 분석 대시보드", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 2.3rem; font-weight: 800; color: #1e3a8a; margin-bottom: 0.2rem; }
    .sub-title { font-size: 1.05rem; color: #4b5563; margin-bottom: 2rem; }
    .stCheckbox { margin-bottom: -12px; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 700; color: #1e3a8a; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>🏆 조달청 타겟 54개사 전수 실적 분석기</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>⚡ 오프라인 마스터 DB 연동형 | 트래픽 리스크 0% 초고속 아키텍처</div>", unsafe_allow_html=True)

# --- 2. 강력한 캐시 데이터 로드 ---
@st.cache_data
def load_master_db():
    if not os.path.exists("Master_DB.csv"):
        return pd.DataFrame()
    df = pd.read_csv("Master_DB.csv", encoding='utf-8-sig', dtype={'사업자등록번호': str, '일자': str})
    if '전체계약금액' in df.columns:
        df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    return df

df_raw = load_master_db()

if df_raw.empty:
    st.error("🚨 폴더 내에 'Master_DB.csv' 파일이 없습니다! make_db.py를 먼저 돌려주세요.")
    st.stop()

# 분기 컬럼 자동 매핑
def get_quarter(m_str):
    if not isinstance(m_str, str): return '기타'
    m = int(m_str.replace('월', ''))
    return '1분기' if m <= 3 else ('2분기' if m <= 6 else ('3분기' if m <= 9 else '4분기'))
df_raw['분기'] = df_raw['월'].apply(get_quarter)

# --- 3. 사이드바 컨트롤 & 품목 상세 필터 ---
with st.sidebar:
    st.header("⚙️ 대시보드 마스터 컨트롤")
    
    # 캐시 완전 초기화 버튼
    if st.button("🔄 최신 데이터 강제 동기화 (캐시 초기화)", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
        
    st.markdown("---")
    st.subheader("📦 품목 상세 필터")
    
    all_items = sorted(df_raw['물품분류명'].dropna().unique())
    
    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("✅ 전체 선택"):
        for item in all_items: st.session_state[f"item_{item}"] = True
    if col_btn2.button("❌ 전체 해제"):
        for item in all_items: st.session_state[f"item_{item}"] = False
        
    selected_items = [i for i in all_items if st.checkbox(i, value=st.session_state.get(f"item_{i}", True), key=f"item_{i}")]

# 필터링 적용
if not selected_items:
    st.warning("⚠️ 품목 필터에서 최소 한 개 이상의 품목을 선택해 주세요.")
    st.stop()

df_filtered = df_raw[df_raw['물품분류명'].isin(selected_items)].copy()

# --- 4. 요약 메트릭 대시보드 ---
total_amt = df_filtered['전체계약금액'].sum()
total_cnt = df_filtered['납품요구번호'].nunique()
avg_amt = (total_amt / total_cnt) if total_cnt > 0 else 0

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("💰 분석 대상 누적 매출액", f"{total_amt:,.0f} 원")
col_m2.metric("📝 총 유효 계약 건수", f"{total_cnt:,} 건")
col_m3.metric("📊 계약 건당 평균 실적", f"{avg_amt:,.0f} 원")
st.markdown("---")

# --- 5. 실적 추이 바 & 마켓쉐어 파이 차트 ---
col_ch1, col_ch2 = st.columns(2)

with col_ch1:
    st.subheader("📈 월별/분기별 실적 추이")
    trend_type = st.radio("조회 기준", ["월별", "분기별"], horizontal=True, label_visibility="collapsed")
    time_col = '월' if trend_type == "월별" else '분기'
    
    g_df = df_filtered.groupby(time_col).agg(금액=('전체계약금액', 'sum'), 건수=('납품요구번호', 'nunique')).reset_index()
    if trend_type == "월별":
        g_df['sort_key'] = g_df['월'].str.replace('월', '').astype(int)
        g_df = g_df.sort_values('sort_key').drop(columns=['sort_key'])
    else:
        g_df = g_df.sort_values('분기')
        
    fig = go.Figure()
    fig.add_trace(go.Bar(x=g_df[time_col], y=g_df['금액'], name='매출액(원)', marker_color='#3b82f6', yaxis='y1'))
    fig.add_trace(go.Scatter(x=g_df[time_col], y=g_df['건수'], name='계약건수(건)', mode='lines+markers+text', text=g_df['건수'], textposition='top center', marker_color='#ef4444', yaxis='y2'))
    fig.update_layout(
        yaxis=dict(title='매출액 (원)', showgrid=False),
        yaxis2=dict(title='계약건수 (건)', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", y=1.15, x=0.7),
        margin=dict(t=10, b=10, l=10, r=10)
    )
    st.plotly_chart(fig, use_container_width=True)

with col_ch2:
    st.subheader("🍩 기간별 시장 점유율 (M/S Top 10)")
    pie_options = ["전체 기간"] + sorted(df_filtered['월'].unique(), key=lambda x: int(x.replace('월','')))
    pie_select = st.selectbox("분석 기간 선택", pie_options, label_visibility="collapsed")
    
    pie_data = df_filtered if pie_select == "전체 기간" else df_filtered[df_filtered['월'] == pie_select]
    
    if pie_data.empty:
        st.info("선택 기간에 실적이 없습니다.")
    else:
        top10_share = pie_data.groupby('업체명')['전체계약금액'].sum().nlargest(10).reset_index()
        fig_pie = px.pie(top10_share, names='업체명', values='전체계약금액', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig_pie, use_container_width=True)

st.markdown("---")

# --- 6. 조달 랭킹 보드 세팅 컨트롤 ---
st.subheader("🛠️ 조달 랭킹 테이블 컨트롤")
col_ctrl1, col_ctrl2 = st.columns(2)
with col_ctrl1:
    show_count_col = st.checkbox("📝 월별/분기별 계약 건수(건) 함께 표시", value=False)
with col_ctrl2:
    include_mas_only = st.checkbox("🏢 종합 랭킹에 MAS 계약만 포함 (해제 시 우수조달 포함 전체 표시)", value=False)

if include_mas_only:
    df_board = df_filtered[df_filtered['MAS여부'] == 'Y']
else:
    df_board = df_filtered

# --- 7. 대망의 입체 다이내믹 피벗 랭킹 보드 생성 ---
if df_board.empty:
    st.warning("선택 조건에 맞는 실적 데이터가 없습니다.")
else:
    # 데이터 피벗팅
    p_amt = pd.pivot_table(df_board, values='전체계약금액', index='업체명', columns='월', aggfunc='sum', fill_value=0).reset_index()
    p_cnt = pd.pivot_table(df_board, values='납품요구번호', index='업체명', columns='월', aggfunc='nunique', fill_value=0).reset_index()
    
    # 12개월 틀 강제 생성
    all_months = [f"{m}월" for m in range(1, 13)]
    for m in all_months:
        if m not in p_amt.columns: p_amt[m] = 0
        if m not in p_cnt.columns: p_cnt[m] = 0
        
    q1, q2 = ['1월', '2월', '3월'], ['4월', '5월', '6월']
    q3, q4 = ['7월', '8월', '9월'], ['10월', '11월', '12월']
    
    # 금액 합계 계산
    p_amt['1분기 합계'] = p_amt[q1].sum(axis=1)
    p_amt['2분기 합계'] = p_amt[q2].sum(axis=1)
    p_amt['3분기 합계'] = p_amt[q3].sum(axis=1)
    p_amt['4분기 합계'] = p_amt[q4].sum(axis=1)
    p_amt['전체 합계'] = p_amt[all_months].sum(axis=1)
    
    # 건수 합계 계산
    p_cnt['1분기(건)'] = p_cnt[q1].sum(axis=1)
    p_cnt['2분기(건)'] = p_cnt[q2].sum(axis=1)
    p_cnt['3분기(건)'] = p_cnt[q3].sum(axis=1)
    p_cnt['4분기(건)'] = p_cnt[q4].sum(axis=1)
    p_cnt['전체 합계(건)'] = p_cnt[all_months].sum(axis=1)
    p_cnt.rename(columns={m: f"{m}(건)" for m in all_months}, inplace=True)
    
    # 통합 마스터 테이블 결합
    final_board = pd.merge(p_amt, p_cnt, on='업체명', how='outer').fillna(0)
    
    # 정렬 및 표시를 위한 컬럼 레이아웃 재구성
    disp_cols = ['업체명']
    for q_m, q_a, q_c in [(q1, '1분기 합계', '1분기(건)'), (q2, '2분기 합계', '2분기(건)'), (q3, '3분기 합계', '3분기(건)'), (q4, '4분기 합계', '4분기(건)')]:
        for m in q_m:
            disp_cols.append(m)
            if show_count_col: disp_cols.append(f"{m}(건)")
        disp_cols.append(q_a)
        if show_count_col: disp_cols.append(q_c)
    disp_cols.append('전체 합계')
    if show_count_col: disp_cols.append('전체 합계(건)')
    
    final_board = final_board[disp_cols]
    
    # 다이내믹 월별/분기별 선택 정렬 기능
    sort_options = [c for c in disp_cols if c != '업체명']
    st.write("")
    col_sort1, col_sort2 = st.columns([3, 1])
    with col_sort2:
        sort_target = st.selectbox("⬇️ 실적 테이블 정렬 기준", options=sort_options, index=sort_options.index('전체 합계'))
        
    # 데이터 정렬 및 No. 랭킹 부여
    final_board = final_board.sort_values(sort_target, ascending=False).reset_index(drop=True)
    final_board.insert(0, '랭킹 No.', range(1, len(final_board) + 1))
    
    # --- 8. 판다스 고품격 테이블 스타일링 (그라데이션 & 파스텔 배경) ---
    fmt_map = {c: "{:,.0f}" for c in final_board.columns if c not in ['랭킹 No.', '업체명']}
    styled_board = final_board.style.format(fmt_map)
    
    # 업체명 열 강조
    styled_board = styled_board.set_properties(subset=['업체명'], **{'background-color': 'rgba(128, 128, 128, 0.08)', 'font-weight': 'bold'})
    
    # 월별, 분기별, 전체 합계별 그리드 입체 색상 부여
    month_cols = [c for c in final_board.columns if '월' in c and '(' not in c]
    q_amt_cols = [c for c in final_board.columns if '분기 합계' in c]
    cnt_cols = [c for c in final_board.columns if '(건)' in c]
    
    styled_board = styled_board.set_properties(subset=month_cols, **{'background-color': 'rgba(54, 162, 235, 0.03)'})
    styled_board = styled_board.set_properties(subset=q_amt_cols, **{'background-color': 'rgba(255, 159, 64, 0.08)', 'font-weight': 'bold'})
    styled_board = styled_board.set_properties(subset=['전체 합계'], **{'background-color': 'rgba(255, 99, 132, 0.08)', 'font-weight': 'bold', 'color': '#1e3a8a'})
    
    if show_count_col:
        styled_board = styled_board.set_properties(subset=cnt_cols, **{'background-color': 'rgba(76, 175, 80, 0.03)'})
        
    # 선택된 정렬 대상 열에 실시간 하이라이트 그라데이션 적용
    styled_board = styled_board.background_gradient(subset=[sort_target], cmap='Blues')
    
    # 웹 화면 고정 렌더링
    st.dataframe(styled_board, use_container_width=True, hide_index=True, height=650)
    
    # --- 9. 마스터 고품격 엑셀 다운로드 파일 빌더 ---
    xlsx_io = BytesIO()
    with pd.ExcelWriter(xlsx_io, engine='xlsxwriter') as writer:
        final_board.to_excel(writer, index=False, sheet_name='전수_조달랭킹_마스터')
        # 엑셀 시트 서식 자동 맞춤 최적화
        worksheet = writer.sheets['전수_조달랭킹_마스터']
        for idx, col in enumerate(final_board.columns):
            max_len = max(final_board[col].astype(str).map(len).max(), len(col)) + 3
            worksheet.set_column(idx, idx, min(max_len, 30))
            
    st.download_button(
        label="💾 정제 완료된 이 테이블 엑셀 파일로 받기",
        data=xlsx_io.getvalue(),
        file_name=f"조달청_54개사_종합랭킹_마스터_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.markdown("<br><center style='color:gray;'>Data Sync Status: Stable (Local Engine V102). Generated for Business Intelligence.</center>", unsafe_allow_html=True)
