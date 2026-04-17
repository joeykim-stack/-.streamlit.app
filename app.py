import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# --- 1. 기본 설정 ---
st.set_page_config(page_title="조달청 실적 분석 대시보드", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: 800; margin-bottom: 0.5rem; }
    .update-time { color: #6c757d; font-size: 0.9rem; margin-bottom: 2rem; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 분석 대상 업체 ---
TARGET_COMPANIES = [
    "주식회사 티제이원", "주식회사 파로스", "주식회사 포딕스시스템", "주식회사 세오", 
    "주식회사 펜타게이트", "주식회사 홍석", "주식회사 솔디아", "주식회사 디라직", 
    "주식회사 새움", "주식회사 디지탈라인", "주식회사 지인테크", "(주)비엔에스테크", 
    "주식회사 시큐인포", "주식회사 명광", "주식회사 올인원 코리아(ALL-IN-ONE KOREA CO., LTD.)", 
    "주식회사 포커스에이아이", "주식회사 한국아이티에스", "(주)앤다스", "주식회사 다누시스", 
    "이노뎁(주)", "주식회사 핀텔", "주식회사 오티에스", "주식회사 에스카", "에코아이넷(주)", 
    "미르텍 주식회사", "주식회사 아이즈온솔루션", "주식회사 그린아이티코리아", "주식회사 제노시스", 
    "(주)지성이엔지", "주식회사 알엠텍", "(주)원우이엔지", "(주)포소드", "주식회사 두원전자통신", 
    "대신네트웍스주식회사", "주식회사 마이크로시스템", "주식회사 크리에이티브넷", "주식회사센텍", 
    "(주)경림이앤지", "주식회사 웹게이트", "한국씨텍(주)", "뉴코리아전자통신 주식회사", 
    "주식회사 제이한테크", "주식회사 아라드네트웍스", "주식회사 진명아이앤씨", "렉스젠 주식회사", 
    "주식회사 디케이앤트", "사이테크놀로지스 주식회사", "주식회사 송우인포텍", "주식회사 아이엔아이", 
    "비티에스 주식회사", "주식회사 인텔리빅스", "주식회사 비알인포텍"
]

# --- 3. [무적 엔진] 로컬 데이터 로직 ---
@st.cache_data(ttl=3600)
def load_historical_data():
    files = ['data.csv', 'data02.csv', 'data02.cvs', 'data03.csv', 'data04.csv']
    dfs = []
    
    for idx, file in enumerate(files):
        try:
            df = None
            try_configs = [
                {'encoding': 'utf-16', 'sep': '\t'},
                {'encoding': 'cp949', 'sep': ','},
                {'encoding': 'utf-8', 'sep': ','}
            ]
            
            for config in try_configs:
                try:
                    temp_df = pd.read_csv(file, encoding=config['encoding'], sep=config['sep'], on_bad_lines='skip', low_memory=False)
                    if len(temp_df.columns) > 2:
                        df = temp_df
                        break
                except: pass
            
            if df is None: continue

            df.rename(columns=lambda x: str(x).strip(), inplace=True)
            
            if '계약업체명' in df.columns and '업체명' not in df.columns: df.rename(columns={'계약업체명': '업체명'}, inplace=True)
            if '품명' in df.columns and '물품분류명' not in df.columns: df.rename(columns={'품명': '물품분류명'}, inplace=True)
            
            req_col = '납품요구번호' if '납품요구번호' in df.columns else ('주문번호' if '주문번호' in df.columns else None)
            if not req_col: continue 

            # 납품증감금액 100% 반영 로직
            if '납품증감금액' in df.columns:
                df['금액'] = pd.to_numeric(df['납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '합계납품증감금액' in df.columns:
                df['금액'] = pd.to_numeric(df['합계납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '납품요구금액' in df.columns: 
                df['금액'] = pd.to_numeric(df['납품요구금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '납품금액' in df.columns: 
                df['금액'] = pd.to_numeric(df['납품금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '금액' in df.columns:
                df['금액'] = pd.to_numeric(df['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            else: continue
                
            if '업체명' not in df.columns or '물품분류명' not in df.columns: continue

            temp_df = df[['업체명', '물품분류명', '금액', req_col]].copy()
            temp_df.columns = ['업체명', '물품분류명', '금액', '납품요구번호']
            temp_df['월'] = f"{idx+1}월"
            temp_df['업체명'] = temp_df['업체명'].astype(str).str.strip()
            
            dfs.append(temp_df[temp_df['업체명'].isin(TARGET_COMPANIES)])
            
        except Exception: continue
            
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# --- 4. [백그라운드] 실시간 API 업데이트 로직 ---
def update_realtime_data():
    if 'api_df' not in st.session_state: st.session_state.api_df = pd.DataFrame()
    if 'last_update' not in st.session_state: st.session_state.last_update = "업데이트 전"
    if 'retry_time' not in st.session_state: st.session_state.retry_time = None

    now = datetime.now()
    
    if st.session_state.retry_time and now < st.session_state.retry_time:
        return st.session_state.api_df, f"⏳ 재시도 대기 중 (다음: {st.session_state.retry_time.strftime('%H:%M:%S')})"

    try:
        API_KEY = "c1b379f7734c7d624ddefea07510eae71b6e12c5fb89970319d76c5ae8db5248"
        URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
        params = {'serviceKey': API_KEY, 'numOfRows': '100', 'inqryDiv': '1', 
                  'inqryBgnDate': '20260415', 'inqryEndDate': now.strftime('%Y%m%d')}
        res = requests.get(URL, params=params, timeout=5)
        
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            items = root.findall('.//item')
            new_data = []
            for item in items:
                corp = item.findtext('corpNm', '').strip()
                if corp in TARGET_COMPANIES:
                    new_data.append({
                        '업체명': corp, 
                        '물품분류명': item.findtext('prdctClsfcNm', ''),
                        '금액': float(item.findtext('dlvrReqAmt', 0)), 
                        '납품요구번호': item.findtext('dlvrReqNo', f'API_{now.timestamp()}'),
                        '월': '4월(실시간)'
                    })
            
            if new_data:
                st.session_state.api_df = pd.DataFrame(new_data)
                st.session_state.last_update = now.strftime('%H:%M:%S')
                return st.session_state.api_df, "🟢 실시간 업데이트 완료"
            return pd.DataFrame(), "🔵 최신 실적 없음 (동기화 대기)"
        else:
            st.session_state.retry_time = now + timedelta(minutes=30)
            return pd.DataFrame(), f"⚠️ 서버 점검 중 (500) - 30분 뒤 재시도"
    except:
        st.session_state.retry_time = now + timedelta(minutes=30)
        return pd.DataFrame(), "⚠️ 통신 일시 장애 - 30분 뒤 재시도"

# --- 5. 데이터 통합 ---
df_hist = load_historical_data()
df_api, api_msg = update_realtime_data()

if not df_api.empty: df_total = pd.concat([df_hist, df_api], ignore_index=True)
else: df_total = df_hist.copy()

st.markdown(f"<div class='main-title'>🏆 조달청 제3자단가계약 통합 대시보드 v8.0</div>", unsafe_allow_html=True)
st.markdown(f"<div class='update-time'>🕒 마지막 업데이트: {st.session_state.last_update} | 상태: {api_msg}</div>", unsafe_allow_html=True)

# --- 6. 사이드바 필터 ---
with st.sidebar:
    st.header("🔍 분석 필터")
    
    if df_total.empty:
        st.error("⚠️ 데이터를 찾을 수 없습니다.")
        all_items = []
    else:
        all_items = sorted(df_total['물품분류명'].dropna().astype(str).unique())
    
    if 'filter_items' not in st.session_state: st.session_state.filter_items = all_items
    else: st.session_state.filter_items = [item for item in st.session_state.filter_items if item in all_items]

    col1, col2 = st.columns(2)
    if col1.button("✅ 전체"): st.session_state.filter_items = all_items
    if col2.button("❌ 해제"): st.session_state.filter_items = []

    selected = st.multiselect("품목 상세 선택", options=all_items, default=st.session_state.filter_items if all_items else [])

# --- 7. 메인 차트 및 대시보드 (v6.6 UI 완벽 복구) ---
if df_total.empty:
    st.warning("🚨 데이터베이스에서 실적을 불러오는 중이거나 파일이 없습니다.")
elif not selected:
    st.info("👈 왼쪽 필터에서 분석할 품목을 1개 이상 선택해주세요.")
else:
    df_f = df_total[df_total['물품분류명'].isin(selected)]
    
    # 📊 1. 핵심 지표 (건수 고유값 처리)
    total_cnt = df_f['납품요구번호'].nunique()
    total_amt = df_f['금액'].sum()
    avg_amt = total_amt / total_cnt if total_cnt > 0 else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 누적 매출액 (납품증감 합계)", f"{total_amt:,.0f} 원")
    c2.metric("📝 총 계약 건수 (납품요구번호)", f"{total_cnt:,} 건")
    c3.metric("📊 건당 평균 계약액", f"{avg_amt:,.0f} 원")
    st.markdown("---")

    # 📈 2. 월별 실적 추이 (콤보 차트 복구)
    st.subheader("📈 월별 실적 추이 (매출 및 건수)")
    monthly_df = df_f.groupby('월').agg(금액=('금액', 'sum'), 건수=('납품요구번호', 'nunique')).reset_index().sort_values('월')
    
    fig_combo = go.Figure()
    fig_combo.add_trace(go.Bar(x=monthly_df['월'], y=monthly_df['금액'], name='매출액(원)', marker_color='#3b82f6', yaxis='y1'))
    fig_combo.add_trace(go.Scatter(x=monthly_df['월'], y=monthly_df['건수'], name='계약건수(건)', mode='lines+markers+text', text=monthly_df['건수'], textposition='top center', marker_color='#ef4444', yaxis='y2'))
    fig_combo.update_layout(
        yaxis=dict(title='매출액(원)', showgrid=False),
        yaxis2=dict(title='계약건수(건)', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=0, r=0, t=30, b=0)
    )
    st.plotly_chart(fig_combo, use_container_width=True)
    st.markdown("---")

    # 🏆 3. Top 10 바 차트 & 시장 점유율 도넛 차트 복구
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🏆 업체별 매출 순위 (Top 10)")
        top10 = df_f.groupby('업체명')['금액'].sum().nlargest(10).reset_index()
        fig_bar = px.bar(top10, x='업체명', y='금액', text_auto='.2s', color='금액', color_continuous_scale='Blues')
        fig_bar.update_layout(xaxis_title="", yaxis_title="매출액")
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with col_b:
        st.subheader("🍩 품목별 시장 점유율")
        fig_pie = px.pie(df_f, names='물품분류명', values='금액', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)
    st.markdown("---")

    # 📋 4. 업체/품목별 월별 피벗 테이블 복구 (총합계 및 총계약건수 포함)
    st.subheader("📋 상세 실적 피벗 테이블 (월별/업체별)")
    
    pivot_df = pd.pivot_table(df_f, values='금액', index=['업체명', '물품분류명'], columns='월', aggfunc='sum', fill_value=0).reset_index()
    month_cols = [col for col in pivot_df.columns if col not in ['업체명', '물품분류명']]
    pivot_df['매출총합계'] = pivot_df[month_cols].sum(axis=1)
    
    cnt_df = df_f.groupby(['업체명', '물품분류명'])['납품요구번호'].nunique().reset_index().rename(columns={'납품요구번호':'총계약건수'})
    final_table = pd.merge(pivot_df, cnt_df, on=['업체명', '물품분류명']).sort_values('매출총합계', ascending=False)
    
    # 숫자 포맷팅해서 예쁘게 보여주기
    styled_table = final_table.style.format({col: "{:,.0f}" for col in month_cols + ['매출총합계']})
    st.dataframe(styled_table, use_container_width=True)

    # 💾 5. 엑셀 다운로드 버튼 복구
    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='실적분석')
            # 엑셀 컬럼 너비 자동 조절
            worksheet = writer.sheets['실적분석']
            for i, col in enumerate(df.columns):
                column_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, column_len)
        return output.getvalue()

    st.download_button(
        label="💾 엑셀(.xlsx) 보고서 다운로드",
        data=to_excel(final_table),
        file_name=f'조달실적_통합분석_{datetime.now().strftime("%Y%m%d")}.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim. Data from Public Data Portal.</center>", unsafe_allow_html=True)
