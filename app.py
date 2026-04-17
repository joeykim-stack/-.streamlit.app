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
    "주식회사 펜타게이트", "주식회사 홍석", "주식회사 솔디아", "주식회사 정현씨앤씨", "주식회사 디라직", 
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
    file_month_map = {
        'data.csv': '1월', 'data02.csv': '2월', 'data02.cvs': '2월', 
        'data03.csv': '3월', 'data04.csv': '4월'
    }
    dfs = []
    for file, target_month in file_month_map.items():
        try:
            df = None
            for config in [{'encoding':'utf-16','sep':'\t'}, {'encoding':'cp949','sep':','}, {'encoding':'utf-8','sep':','}]:
                try:
                    temp_df = pd.read_csv(file, encoding=config['encoding'], sep=config['sep'], on_bad_lines='skip', low_memory=False)
                    if len(temp_df.columns) > 2:
                        df = temp_df; break
                except: pass
            
            if df is None: continue
            df.rename(columns=lambda x: str(x).strip(), inplace=True)
            if '계약업체명' in df.columns and '업체명' not in df.columns: df.rename(columns={'계약업체명': '업체명'}, inplace=True)
            if '품명' in df.columns and '물품분류명' not in df.columns: df.rename(columns={'품명': '물품분류명'}, inplace=True)
            req_col = '납품요구번호' if '납품요구번호' in df.columns else ('주문번호' if '주문번호' in df.columns else None)
            if not req_col: continue 

            if '납품증감금액' in df.columns: df['금액'] = pd.to_numeric(df['납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '합계납품증감금액' in df.columns: df['금액'] = pd.to_numeric(df['합계납품증감금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '납품요구금액' in df.columns: df['금액'] = pd.to_numeric(df['납품요구금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '납품금액' in df.columns: df['금액'] = pd.to_numeric(df['납품금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            elif '금액' in df.columns: df['금액'] = pd.to_numeric(df['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            else: continue
                
            if '업체명' not in df.columns or '물품분류명' not in df.columns: continue
            temp_df = df[['업체명', '물품분류명', '금액', req_col]].copy()
            temp_df.columns = ['업체명', '물품분류명', '금액', '납품요구번호']
            temp_df['월'] = target_month
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
        params = {'serviceKey': API_KEY, 'numOfRows': '100', 'inqryDiv': '1', 'inqryBgnDate': '20260415', 'inqryEndDate': now.strftime('%Y%m%d')}
        res = requests.get(URL, params=params, timeout=5)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            items = root.findall('.//item')
            new_data = []
            for item in items:
                corp = item.findtext('corpNm', '').strip()
                if corp in TARGET_COMPANIES:
                    new_data.append({'업체명': corp, '물품분류명': item.findtext('prdctClsfcNm', ''), '금액': float(item.findtext('dlvrReqAmt', 0)), '납품요구번호': item.findtext('dlvrReqNo', f'API_{now.timestamp()}'), '월': '4월'})
            if new_data:
                st.session_state.api_df = pd.DataFrame(new_data)
                st.session_state.last_update = now.strftime('%H:%M:%S')
                return st.session_state.api_df, "🟢 실시간 4월 실적 병합 완료"
            return pd.DataFrame(), "🔵 금일 추가 실적 없음"
        else:
            st.session_state.retry_time = now + timedelta(minutes=30)
            return pd.DataFrame(), f"⚠️ 서버 점검 중 (500) - 30분 뒤 재시도"
    except:
        st.session_state.retry_time = now + timedelta(minutes=30)
        return pd.DataFrame(), "⚠️ 통신 일시 장애 - 30분 뒤 재시도"

# --- 5. 데이터 통합 ---
df_hist = load_historical_data()
df_api, api_msg = update_realtime_data()
df_total = pd.concat([df_hist, df_api], ignore_index=True) if not df_api.empty else df_hist.copy()

st.markdown(f"<div class='main-title'>🏆 조달청 제3자단가계약 통합 대시보드 v8.6</div>", unsafe_allow_html=True)
st.markdown(f"<div class='update-time'>🕒 마지막 업데이트: {st.session_state.last_update} | 상태: {api_msg}</div>", unsafe_allow_html=True)

# --- 6. 사이드바 필터 ---
with st.sidebar:
    st.markdown("### 🔍 품목 필터")
    all_items = sorted(df_total['물품분류명'].dropna().astype(str).unique()) if not df_total.empty else []
    
    select_all = st.checkbox("☑️ 전체 품목 선택", value=True)
    if select_all:
        selected = st.multiselect("품목 상세", options=all_items, default=all_items, label_visibility="collapsed")
    else:
        selected = st.multiselect("품목 상세", options=all_items, default=[], label_visibility="collapsed")

# --- 7. 메인 차트 및 대시보드 ---
if df_total.empty:
    st.warning("🚨 데이터베이스에서 실적을 불러오는 중이거나 파일이 없습니다.")
elif not selected:
    st.info("👈 왼쪽 필터에서 분석할 품목을 1개 이상 선택해주세요.")
else:
    df_f = df_total[df_total['물품분류명'].isin(selected)]
    
    # 📊 1. 핵심 지표
    total_cnt = df_f['납품요구번호'].nunique()
    total_amt = df_f['금액'].sum()
    avg_amt = total_amt / total_cnt if total_cnt > 0 else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 누적 매출액", f"{total_amt:,.0f} 원")
    c2.metric("📝 총 계약 건수", f"{total_cnt:,} 건")
    c3.metric("📊 건당 평균 계약액", f"{avg_amt:,.0f} 원")
    st.markdown("---")

    # 📈 월별 실적 콤보 차트
    monthly_df = df_f.groupby('월').agg(금액=('금액', 'sum'), 건수=('납품요구번호', 'nunique')).reset_index().sort_values('월')
    fig_combo = go.Figure()
    fig_combo.add_trace(go.Bar(x=monthly_df['월'], y=monthly_df['금액'], name='매출액(원)', marker_color='#3b82f6', yaxis='y1'))
    fig_combo.add_trace(go.Scatter(x=monthly_df['월'], y=monthly_df['건수'], name='계약건수(건)', mode='lines+markers+text', text=monthly_df['건수'], textposition='top center', marker_color='#ef4444', yaxis='y2'))
    fig_combo.update_layout(yaxis=dict(title='매출액(원)', showgrid=False), yaxis2=dict(title='계약건수(건)', overlaying='y', side='right', showgrid=False), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(l=0, r=0, t=30, b=0))
    
    # 🏆 도넛 차트
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("📈 월별 실적 추이")
        st.plotly_chart(fig_combo, use_container_width=True)
        
    with col_b:
        st.subheader("🍩 시장 점유율 (매출액 기준)")
        top10 = df_f.groupby('업체명')['금액'].sum().nlargest(10).reset_index()
        fig_pie = px.pie(top10, names='업체명', values='금액', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(showlegend=False, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")

    # 📋 4. 업체별 피벗 테이블 (월별/분기별 건수 교차 표시 완벽 구현!)
    st.subheader("📋 업체별 종합 실적 랭킹 보드")
    
    # 💡 [핵심] 테이블 바로 위에 체크박스 생성
    show_count = st.checkbox("📝 표에 월별/분기별 계약건수 함께 보기", value=False)
    
    # 1. 매출액 피벗 (기준)
    pivot_amt = pd.pivot_table(df_f, values='금액', index='업체명', columns='월', aggfunc='sum', fill_value=0).reset_index()
    for m in ['1월', '2월', '3월', '4월']:
        if m not in pivot_amt.columns: pivot_amt[m] = 0
    pivot_amt['1분기 합계'] = pivot_amt['1월'] + pivot_amt['2월'] + pivot_amt['3월']
    pivot_amt['누적 합계'] = pivot_amt['1분기 합계'] + pivot_amt['4월']
    
    # 2. 계약 건수 피벗
    pivot_cnt = pd.pivot_table(df_f, values='납품요구번호', index='업체명', columns='월', aggfunc='nunique', fill_value=0).reset_index()
    for m in ['1월', '2월', '3월', '4월']:
        if m not in pivot_cnt.columns: pivot_cnt[m] = 0
    pivot_cnt['1분기(건수)'] = pivot_cnt['1월'] + pivot_cnt['2월'] + pivot_cnt['3월']
    pivot_cnt['누적(건수)'] = pivot_cnt['1분기(건수)'] + pivot_cnt['4월']
    
    # 건수 컬럼명 변경 (교차 표시를 위해)
    pivot_cnt.rename(columns={'1월': '1월(건수)', '2월': '2월(건수)', '3월': '3월(건수)', '4월': '4월(건수)'}, inplace=True)
    
    # 3. 데이터 병합
    final_table = pd.merge(pivot_amt, pivot_cnt, on='업체명', how='outer').fillna(0)
    final_table = final_table.sort_values('누적 합계', ascending=False).reset_index(drop=True)
    final_table.insert(0, '랭킹 No.', range(1, len(final_table) + 1))
    
    # 4. 체크박스 상태에 따라 표시할 칼럼 '교차' 배치
    if show_count:
        display_cols = [
            '랭킹 No.', '업체명', 
            '1월', '1월(건수)', 
            '2월', '2월(건수)', 
            '3월', '3월(건수)', 
            '1분기 합계', '1분기(건수)', 
            '4월', '4월(건수)', 
            '누적 합계', '누적(건수)'
        ]
    else:
        display_cols = ['랭킹 No.', '업체명', '1월', '2월', '3월', '1분기 합계', '4월', '누적 합계']
        
    final_table = final_table[display_cols]
    
    # 5. 숫자 포맷팅
    format_dict = {col: "{:,.0f}" for col in ['1월', '2월', '3월', '1분기 합계', '4월', '누적 합계']}
    if show_count: 
        format_dict.update({col: "{:,.0f}" for col in ['1월(건수)', '2월(건수)', '3월(건수)', '1분기(건수)', '4월(건수)', '누적(건수)']})
    
    styled_table = final_table.style.format(format_dict)
    
    # 6. 엑셀 조건부 서식 스타일 (건수는 연두색 계열로 칠해서 구별)
    styled_table = styled_table.set_properties(subset=['업체명'], **{'background-color': 'rgba(128, 128, 128, 0.1)', 'font-weight': 'bold'})
    styled_table = styled_table.set_properties(subset=['1월', '2월', '3월', '4월'], **{'background-color': 'rgba(54, 162, 235, 0.05)'})
    styled_table = styled_table.set_properties(subset=['1분기 합계'], **{'background-color': 'rgba(255, 159, 64, 0.1)', 'font-weight': 'bold'})
    
    if show_count:
        # 건수 데이터는 옅은 녹색, 분기/누적 건수는 살짝 진한 녹색
        styled_table = styled_table.set_properties(subset=['1월(건수)', '2월(건수)', '3월(건수)', '4월(건수)'], **{'background-color': 'rgba(76, 175, 80, 0.05)'})
        styled_table = styled_table.set_properties(subset=['1분기(건수)', '누적(건수)'], **{'background-color': 'rgba(76, 175, 80, 0.15)', 'font-weight': 'bold'})
    
    styled_table = styled_table.background_gradient(subset=['누적 합계'], cmap='Blues')
    
    st.dataframe(styled_table, use_container_width=True, hide_index=True)

    # 💾 5. 엑셀 다운로드 (체크박스 켠 상태로 다운받으면 건수도 엑셀에 포함됨!)
    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='실적랭킹')
            worksheet = writer.sheets['실적랭킹']
            for i, col in enumerate(df.columns):
                worksheet.set_column(i, i, max(df[col].astype(str).map(len).max(), len(col)) + 2)
        return output.getvalue()

    st.download_button(
        label="💾 엑셀(.xlsx) 보고서 다운로드",
        data=to_excel(final_table),
        file_name=f'조달실적_업체별랭킹_{datetime.now().strftime("%Y%m%d")}.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim. Data from Public Data Portal.</center>", unsafe_allow_html=True)
