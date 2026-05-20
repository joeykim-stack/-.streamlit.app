import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET
import urllib3
import time
import os

# SSL 경고 숨기기
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [디자인 헤드룸 세팅] 브랜드 커스텀 테마 CSS ---
st.set_page_config(page_title="나라장터 실시간 전수 분석 시스템", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 2.3rem; font-weight: 800; color: #1e3a8a; margin-bottom: 0.1rem; letter-spacing: -0.05rem; }
    .sub-title { font-size: 1.05rem; color: #4b5563; margin-bottom: 1.8rem; }
    .metric-card { background-color: #f8fafc; padding: 15px; border-radius: 10px; border-left: 5px solid #1e3a8a; }
    div[data-testid="stMetricValue"] { font-size: 1.9rem !important; font-weight: 800; color: #1e3a8a; }
    .stCheckbox { margin-bottom: -10px; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>🏆 조달청 타겟 54개사 종합 실적 랭킹 보드</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>⚡ 실시간 API 수집 봇 내장형 (All-in-One V106)</div>", unsafe_allow_html=True)

# --- [내장형 수집 봇 함수] ---
def run_daily_crawler():
    API_KEY = "df5a1c97ab56593d5e99889ae1c030bfe0b5e9d924ffba9bae3712c8bb1ad75c" 
    TARGET_FILE = "target_companies.csv"
    MASTER_DB_FILE = "Master_DB.csv"

    today = datetime.now()
    bgn_date = (today - timedelta(days=2)).strftime("%Y%m%d")
    end_date = (today - timedelta(days=1)).strftime("%Y%m%d")

    # 1. 타겟 업체 로드
    TARGET_MAP = {}
    try:
        raw_target = None
        for enc in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
            try:
                raw_target = pd.read_csv(TARGET_FILE, encoding=enc, header=None, dtype=str)
                break
            except: pass
            
        if raw_target is None: return "🚨 타겟 업체 파일을 읽을 수 없습니다."
            
        header_idx = None
        for idx, row in raw_target.iterrows():
            if row.astype(str).str.contains('사업자등록번호').any():
                header_idx = idx; break
                
        columns = [str(c).strip() for c in raw_target.iloc[header_idx].tolist()]
        df_target = raw_target.iloc[header_idx+1:].copy()
        df_target.columns = columns
        
        biz_col = [c for c in df_target.columns if '사업자등록번호' in c][0]
        name_col = [c for c in df_target.columns if '계약업체' in c or '업체명' in c][0]
        
        df_target[biz_col] = df_target[biz_col].fillna('').str.replace('-', '', regex=False).str.replace(r'\.0$', '', regex=True).str.strip()
        TARGET_MAP = dict(zip(df_target[biz_col], df_target[name_col]))
    except Exception as e:
        return f"🚨 업체 맵핑 에러: {e}"

    # 2. 조달청 API 호출
    BASE_URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
    headers = {'User-Agent': 'Mozilla/5.0'}
    all_new_data = []

    page = 1
    while True:
        url = f"{BASE_URL}?serviceKey={API_KEY}&numOfRows=500&pageNo={page}&inqryDiv=1&inqryBgnDate={bgn_date}&inqryEndDate={end_date}"
        success = False
        
        for wait_time in [2, 4]:
            try:
                res = requests.get(url, headers=headers, timeout=15, verify=False)
                if res.status_code == 200:
                    success = True; break
                elif res.status_code == 429:
                    return "🚨 API 트래픽 한도(429) 초과! 내일 다시 시도하세요."
            except: pass
            time.sleep(wait_time)
            
        if not success: break
            
        try:
            root = ET.fromstring(res.content)
            if root.findtext('.//resultCode') not in ['00', '0']: break
            total = int(root.findtext('.//totalCount') or 0)
            if total == 0: return f"🔵 {bgn_date}~{end_date} 기간 조달청 신규 데이터가 없습니다."
                
            items = root.findall('.//item')
            if not items: break
            
            for item in items:
                all_new_data.append({child.tag: child.text for child in item})
            
            if page * 500 >= total: break
            page += 1
        except Exception: break

    # 3. 데이터 정제 및 DB 업데이트
    if all_new_data:
        df_api = pd.DataFrame(all_new_data)
        biz_col = 'bizrno' if 'bizrno' in df_api.columns else None
        
        if biz_col:
            df_api[biz_col] = df_api[biz_col].fillna('').str.replace('-', '', regex=False).str.strip()
            df_target_only = df_api[df_api[biz_col].isin(TARGET_MAP.keys())].copy()
            
            if not df_target_only.empty:
                df_target_only['업체명'] = df_target_only[biz_col].map(TARGET_MAP)
                df_target_only = df_target_only.rename(columns={
                    'bizrno': '사업자등록번호', 'prdctClsfcNm': '물품분류명', 
                    'dlvrReqNo': '납품요구번호', 'dlvrReqRcptDate': '일자', 'dlvrReqAmt': '전체계약금액'
                })
                
                if '전체계약금액' in df_target_only.columns:
                    df_target_only['전체계약금액'] = pd.to_numeric(df_target_only['전체계약금액'], errors='coerce').fillna(0)
                
                if '일자' in df_target_only.columns:
                    df_target_only['일자'] = df_target_only['일자'].astype(str).str.replace('-', '').str[:8]
                    df_target_only['월'] = df_target_only['일자'].str[4:6].apply(lambda x: f"{int(x)}월" if x.isdigit() else "미상")

                if os.path.exists(MASTER_DB_FILE):
                    df_master = pd.read_csv(MASTER_DB_FILE, encoding='utf-8-sig', dtype=str)
                    df_combined = pd.concat([df_master, df_target_only], ignore_index=True)
                    if '납품요구번호' in df_combined.columns and '전체계약금액' in df_combined.columns:
                        df_combined = df_combined.drop_duplicates(subset=['납품요구번호', '물품분류명', '전체계약금액'], keep='last')
                    df_combined.to_csv(MASTER_DB_FILE, index=False, encoding='utf-8-sig')
                    return f"🎉 신규 실적 {len(df_target_only)}건이 Master DB에 완벽히 추가되었습니다!"
                else:
                    df_target_only.to_csv(MASTER_DB_FILE, index=False, encoding='utf-8-sig')
                    return f"🎉 Master DB를 새로 생성하고 {len(df_target_only)}건을 저장했습니다!"
            else:
                return f"🔵 조달청 업데이트는 있으나, 타겟 54개사의 실적은 없습니다."
    return "🔵 데이터 수집 중 문제가 발생했습니다."

# --- [사이드바 컨트롤 존] ---
with st.sidebar:
    st.header("⚙️ 시스템 마스터 컨트롤")
    
    # 💡 [새로운 마법의 버튼] 봇 내장형 API 수집 스위치
    if st.button("📡 [실행] 오늘자 신규 실적 수집하기", type="primary", use_container_width=True):
        with st.spinner("조달청 서버 잠입 중... (최대 1~2분 소요될 수 있습니다)"):
            result_msg = run_daily_crawler()
            if "🎉" in result_msg:
                st.success(result_msg)
            elif "🔵" in result_msg:
                st.info(result_msg)
            else:
                st.error(result_msg)
            
            # 수집 완료 후 낡은 기억 삭제 및 새로고침
            st.cache_data.clear()
            time.sleep(2)
            st.rerun()

    if st.button("🔥 기존 캐시 완전히 비우기 (새로고침)", use_container_width=True):
        st.cache_data.clear()
        st.success("🚀 기존 서버 메모리 캐시를 완전히 청소했습니다!")
        time.sleep(1)
        st.rerun()
        
    st.markdown("---")
    st.subheader("📦 품목 카테고리 필터")

# --- [초고속 엔진] 데이터 로드 ---
@st.cache_data(ttl=3600)
def load_master_db():
    if not os.path.exists("Master_DB.csv"): return pd.DataFrame()
    df = pd.read_csv("Master_DB.csv", encoding='utf-8-sig', dtype={'사업자등록번호': str, '일자': str})
    if '전체계약금액' in df.columns:
        df['전체계약금액'] = pd.to_numeric(df['전체계약금액'], errors='coerce').fillna(0)
    return df

df_raw = load_master_db()

if df_raw.empty:
    st.error("🚨 Master_DB.csv 파일이 없습니다. 좌측의 '오늘자 신규 실적 수집하기' 버튼을 눌러보세요!")
    st.stop()

def get_quarter_label(m_str):
    if not isinstance(m_str, str): return '기타'
    try:
        m = int(m_str.replace('월', ''))
        return '1분기' if m <= 3 else ('2분기' if m <= 6 else ('3분기' if m <= 9 else '4분기'))
    except: return '기타'
df_raw['분기'] = df_raw['월'].apply(get_quarter_label)

# --- [품목 필터링 로직] ---
with st.sidebar:
    all_items = sorted(df_raw['물품분류명'].dropna().unique())
    col_filter1, col_filter2 = st.columns(2)
    if col_filter1.button("🟢 전체 체크"):
        for itm in all_items: st.session_state[f"chk_{itm}"] = True
    if col_filter2.button("🔴 전체 해제"):
        for itm in all_items: st.session_state[f"chk_{itm}"] = False
        
    selected_items = [itm for itm in all_items if st.checkbox(itm, value=st.session_state.get(f"chk_{itm}", True), key=f"chk_{itm}")]

if not selected_items:
    st.warning("⚠️ 최소 한 개 이상의 품목을 필터에서 선택해 주셔야 대시보드가 구동됩니다.")
    st.stop()

df_filtered = df_raw[df_raw['물품분류명'].isin(selected_items)].copy()

# --- [영업 핵심 요약 메트릭 존] ---
total_revenue = df_filtered['전체계약금액'].sum()
total_contracts = df_filtered['납품요구번호'].nunique()
ticket_size = (total_revenue / total_contracts) if total_contracts > 0 else 0

m_col1, m_col2, m_col3 = st.columns(3)
with m_col1:
    st.markdown(f"<div class='metric-card'>", unsafe_allow_html=True)
    st.metric("💰 누적 총 조달 매출액", f"{total_revenue:,.0f} 원")
    st.markdown("</div>", unsafe_allow_html=True)
with m_col2:
    st.markdown(f"<div class='metric-card'>", unsafe_allow_html=True)
    st.metric("📝 총 유효 낙찰 건수", f"{total_contracts:,} 건")
    st.markdown("</div>", unsafe_allow_html=True)
with m_col3:
    st.markdown(f"<div class='metric-card'>", unsafe_allow_html=True)
    st.metric("📊 건당 평균 발주 스케일", f"{ticket_size:,.0f} 원")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

# --- [입체적 비주얼라이제이션 차트] ---
ch_col1, ch_col2 = st.columns(2)

with ch_col1:
    st.subheader("📊 시계열 실적 현황 및 딜 스케일")
    time_basis = st.radio("분석 타임라인", ["월별 추이", "분기별 추이"], horizontal=True, label_visibility="collapsed")
    axis_col = '월' if time_basis == "월별 추이" else '분기'
    
    trend_group = df_filtered.groupby(axis_col).agg(금액=('전체계약금액', 'sum'), 건수=('납품요구번호', 'nunique')).reset_index()
    if axis_col == '월':
        trend_group['sort_idx'] = trend_group['월'].str.replace('월', '').astype(int)
        trend_group = trend_group.sort_values('sort_idx').drop(columns=['sort_idx'])
    else:
        trend_group = trend_group.sort_values('분기')
        
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Bar(x=trend_group[axis_col], y=trend_group['금액'], name='매출 스케일(원)', marker_color='#3b82f6', yaxis='y1'))
    fig_trend.add_trace(go.Scatter(x=trend_group[axis_col], y=trend_group['건수'], name='낙찰 빈도(건)', mode='lines+markers+text', text=trend_group['건수'], textposition='top center', marker_color='#ef4444', yaxis='y2'))
    fig_trend.update_layout(yaxis=dict(title='매출액 (원)', showgrid=False), yaxis2=dict(title='계약건수 (건)', overlaying='y', side='right', showgrid=False), legend=dict(orientation="h", y=1.15, x=0.65), margin=dict(t=15, b=10, l=10, r=10))
    st.plotly_chart(fig_trend, use_container_width=True)

with ch_col2:
    st.subheader("🍩 조달 시장 점유율 프로필 (M/S Top 10)")
    share_period = ["전체 조회기간"] + sorted(df_filtered['월'].unique(), key=lambda x: int(x.replace('월','')))
    selected_period = st.selectbox("시장 점유율 타겟 기간", share_period, label_visibility="collapsed")
    
    share_dataset = df_filtered if selected_period == "전체 조회기간" else df_filtered[df_filtered['월'] == selected_period]
    
    if share_dataset.empty:
        st.info("해당 타겟 기간에는 유효 실적이 잡히지 않았습니다.")
    else:
        share_ranking = share_dataset.groupby('업체명')['전체계약금액'].sum().nlargest(10).reset_index()
        fig_share = px.pie(share_ranking, names='업체명', values='전체계약금액', hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe)
        fig_share.update_traces(textposition='inside', textinfo='percent+label')
        fig_share.update_layout(showlegend=False, margin=dict(t=15, b=10, l=10, r=10))
        st.plotly_chart(fig_share, use_container_width=True)

st.markdown("---")

# --- [종합 랭킹 보드 제어판] ---
st.subheader("📊 다이내믹 종합 실적 피벗 매트릭스")
ctrl_col1, ctrl_col2 = st.columns(2)
with ctrl_col1:
    toggle_counts = st.checkbox("📝 월별/분기별 순수 계약 건수(건) 셀 매트릭스 결합", value=False)
with ctrl_col2:
    filter_mas_only = st.checkbox("🏢 오직 다수공급자계약(MAS) 데이터만 필터링해서 보기", value=False)

df_board_base = df_filtered[df_filtered['MAS여부'] == 'Y'] if filter_mas_only else df_filtered

if df_board_base.empty:
    st.warning("지정된 필터 조건에 부합하는 조달 실적 마스터 행이 존재하지 않습니다.")
else:
    matrix_amt = pd.pivot_table(df_board_base, values='전체계약금액', index='업체명', columns='월', aggfunc='sum', fill_value=0).reset_index()
    matrix_cnt = pd.pivot_table(df_board_base, values='납품요구번호', index='업체명', columns='월', aggfunc='nunique', fill_value=0).reset_index()
    
    calendar_months = [f"{m}월" for m in range(1, 13)]
    for m in calendar_months:
        if m not in matrix_amt.columns: matrix_amt[m] = 0
        if m not in matrix_cnt.columns: matrix_cnt[m] = 0
        
    m_q1, m_q2 = ['1월', '2월', '3월'], ['4월', '5월', '6월']
    m_q3, m_q4 = ['7월', '8월', '9월'], ['10월', '11월', '12월']
    
    matrix_amt['1분기 실적'] = matrix_amt[m_q1].sum(axis=1)
    matrix_amt['2분기 실적'] = matrix_amt[m_q2].sum(axis=1)
    matrix_amt['3분기 실적'] = matrix_amt[m_q3].sum(axis=1)
    matrix_amt['4분기 실적'] = matrix_amt[m_q4].sum(axis=1)
    matrix_amt['누적 전체합계'] = matrix_amt[calendar_months].sum(axis=1)
    
    matrix_cnt['1분기(건)'] = matrix_cnt[m_q1].sum(axis=1)
    matrix_cnt['2분기(건)'] = matrix_cnt[m_q2].sum(axis=1)
    matrix_cnt['3분기(건)'] = matrix_cnt[m_q3].sum(axis=1)
    matrix_cnt['4분기(건)'] = matrix_cnt[m_q4].sum(axis=1)
    matrix_cnt['누적 전체합계(건)'] = matrix_cnt[calendar_months].sum(axis=1)
    matrix_cnt.rename(columns={m: f"{m}(건)" for m in calendar_months}, inplace=True)
    
    bi_pivot_master = pd.merge(matrix_amt, matrix_cnt, on='업체명', how='outer').fillna(0)
    
    chain_layout = ['업체명']
    for q_months, q_a_label, q_c_label in [(m_q1, '1분기 실적', '1분기(건)'), (m_q2, '2분기 실적', '2분기(건)'), (m_q3, '3분기 실적', '3분기(건)'), (m_q4, '4분기 실적', '4분기(건)')]:
        for m in q_months:
            chain_layout.append(m)
            if toggle_counts: chain_layout.append(f"{m}(건)")
        chain_layout.append(q_a_label)
        if toggle_counts: chain_layout.append(q_c_label)
    chain_layout.append('누적 전체합계')
    if toggle_counts: chain_layout.append('누적 전체합계(건)')
    
    bi_pivot_master = bi_pivot_master[chain_layout]
    
    sorting_pool = [col for col in chain_layout if col != '업체명']
    sort_box_col1, sort_box_col2 = st.columns([3, 1])
    with sort_box_col2:
        active_sort_target = st.selectbox("⬇️ 실적 테이블 가로축 정렬 필드", options=sorting_pool, index=sorting_pool.index('누적 전체합계'))
        
    bi_pivot_master = bi_pivot_master.sort_values(active_sort_target, ascending=False).reset_index(drop=True)
    bi_pivot_master.insert(0, '순위', range(1, len(bi_pivot_master) + 1))
    
    format_specs = {c: "{:,.0f}" for c in bi_pivot_master.columns if c not in ['순위', '업체명']}
    styled_view = bi_pivot_master.style.format(format_specs)
    
    styled_view = styled_view.set_properties(subset=['업체명'], **{'background-color': 'rgba(148, 163, 184, 0.08)', 'font-weight': 'bold'})
    pure_month_fields = [c for c in bi_pivot_master.columns if '월' in c and '(' not in c]
    quarter_amt_fields = [c for c in bi_pivot_master.columns if '분기 실적' in c]
    pure_count_fields = [c for c in bi_pivot_master.columns if '(건)' in c]
    
    styled_view = styled_view.set_properties(subset=pure_month_fields, **{'background-color': 'rgba(241, 245, 249, 0.4)'})
    styled_view = styled_view.set_properties(subset=quarter_amt_fields, **{'background-color': 'rgba(234, 179, 8, 0.06)', 'font-weight': 'bold'})
    styled_view = styled_view.set_properties(subset=['누적 전체합계'], **{'background-color': 'rgba(30, 58, 138, 0.05)', 'font-weight': '900', 'color': '#1e3a8a'})
    if toggle_counts:
        styled_view = styled_view.set_properties(subset=pure_count_fields, **{'background-color': 'rgba(34, 197, 94, 0.02)'})
        
    styled_view = styled_view.background_gradient(subset=[active_sort_target], cmap='Blues')
    
    st.dataframe(styled_view, use_container_width=True, hide_index=True, height=650)
    
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as xlsx_writer:
        bi_pivot_master.to_excel(xlsx_writer, index=False, sheet_name='54개사_조달랭킹_분석')
        workbook = xlsx_writer.book
        worksheet = xlsx_writer.sheets['54개사_조달랭킹_분석']
        for idx, col_name in enumerate(bi_pivot_master.columns):
            content_max = bi_pivot_master[col_name].astype(str).map(len).max()
            label_len = len(col_name)
            worksheet.set_column(idx, idx, min(max(content_max, label_len) + 4, 32))
            
    st.download_button(
        label="💾 분석 결과 테이블 고해상도 엑셀 시트로 추출하기",
        data=excel_buffer.getvalue(),
        file_name=f"나라장터_타겟54개사_교차분석마스터_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.markdown("<br><center style='color:#9ca3af; font-size:0.85rem;'>System Architecture: Web-based Auto API Crawler & Dashboard (V106-Final).</center>", unsafe_allow_html=True)
