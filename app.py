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

def get_now_kst():
    return datetime.now() + timedelta(hours=9)

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
            elif '금액' in df.columns: df['금액'] = pd.to_numeric(df['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            else: continue
            temp_df = df[['업체명', '물품분류명', '금액', req_col]].copy()
            temp_df.columns = ['업체명', '물품분류명', '금액', '납품요구번호']
            temp_df['월'] = target_month
            temp_df['업체명'] = temp_df['업체명'].astype(str).str.strip()
            dfs.append(temp_df[temp_df['업체명'].isin(TARGET_COMPANIES)])
        except Exception: continue
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# --- 4. 실시간 API 업데이트 로직 (💡 1페이지 증후군 해결: 전수조사 패치) ---
def update_realtime_data():
    if 'api_df' not in st.session_state: st.session_state.api_df = pd.DataFrame()
    if 'last_update' not in st.session_state: st.session_state.last_update = "업데이트 전"
    if 'retry_time' not in st.session_state: st.session_state.retry_time = None
    
    now = get_now_kst()
    if st.session_state.retry_time and now < st.session_state.retry_time:
        return st.session_state.api_df, f"⏳ 대기 중 (다음 시도: {st.session_state.retry_time.strftime('%H:%M:%S')})"
    
    try:
        API_KEY = "c1b379f7734c7d624ddefea07510eae71b6e12c5fb89970319d76c5ae8db5248"
        URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
        
        all_new_data = []
        page_no = 1
        
        # 💡 while문을 통해 마지막 페이지가 나올 때까지 싹쓸이!
        while True:
            params = {
                'serviceKey': API_KEY, 
                'numOfRows': '999',  # 한 번에 최대치로 긁어오기
                'pageNo': str(page_no),
                'inqryDiv': '1', 
                'inqryBgnDate': '20260415', 
                'inqryEndDate': now.strftime('%Y%m%d')
            }
            res = requests.get(URL, params=params, timeout=10)
            
            if res.status_code == 200:
                root = ET.fromstring(res.content)
                items = root.findall('.//item')
                
                if not items:
                    break # 읽을 데이터가 더 없으면 루프 탈출
                    
                for item in items:
                    corp = item.findtext('corpNm', '').strip()
                    if corp in TARGET_COMPANIES:
                        all_new_data.append({
                            '업체명': corp, 
                            '물품분류명': item.findtext('prdctClsfcNm', ''), 
                            '금액': float(item.findtext('dlvrReqAmt', 0)), 
                            '납품요구번호': item.findtext('dlvrReqNo', f'API_{now.timestamp()}'), 
                            '월': '4월'
                        })
                
                # API가 알려주는 전체 데이터 개수를 확인해서, 끝까지 도달했으면 탈출
                total_count = int(root.findtext('.//totalCount', '0'))
                if page_no * 999 >= total_count:
                    break
                    
                page_no += 1
            else:
                break # 500 등 에러 발생 시 루프 중단

        if all_new_data:
            st.session_state.api_df = pd.DataFrame(all_new_data)
            st.session_state.last_update = now.strftime('%H:%M:%S')
            return st.session_state.api_df, f"🟢 실시간 4월 싹쓸이 완료 (총 {page_no}페이지)"
        
        return pd.DataFrame(), "🔵 금일 추가 실적 없음"
        
    except Exception as e:
        st.session_state.retry_time = now + timedelta(minutes=30)
        return pd.DataFrame(), "⚠️ 통신 장애 - 30분 뒤 재시도"

# --- 5. 데이터 통합 ---
df_hist = load_historical_data()
df_api, api_msg = update_realtime_data()
df_total = pd.concat([df_hist, df_api], ignore_index=True) if not df_api.empty else df_hist.copy()

st.markdown(f"<div class='main-title'>🏆 조달청 제3자단가계약 통합 대시보드 v8.8</div>", unsafe_allow_html=True)
st.markdown(f"<div class='update-time'>🕒 마지막 업데이트(한국시간): {st.session_state.last_update} | 상태: {api_msg}</div>", unsafe_allow_html=True)

# --- 6. 사이드바 필터 ---
with st.sidebar:
    st.markdown("### 🔍 품목 필터")
    all_items = sorted(df_total['물품분류명'].dropna().astype(str).unique()) if not df_total.empty else []
    select_all = st.checkbox("☑️ 전체 품목 선택", value=True)
    if select_all:
        selected = st.multiselect("품목 상세", options=all_items, default=all_items, label_visibility="collapsed")
    else:
        selected = st.multiselect("품목 상세", options=all_items, default=[], label_visibility="collapsed")

# --- 7. 메인 화면 ---
if df_total.empty:
    st.warning("🚨 데이터를 불러올 수 없습니다.")
elif not selected:
    st.info("👈 왼쪽 필터에서 품목을 선택해주세요.")
else:
    df_f = df_total[df_total['물품분류명'].isin(selected)]
    total_cnt = df_f['납품요구번호'].nunique()
    total_amt = df_f['금액'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 누적 매출액", f"{total_amt:,.0f} 원")
    c2.metric("📝 총 계약 건수", f"{total_cnt:,} 건")
    c3.metric("📊 건당 평균 계약액", f"{(total_amt/total_cnt if total_cnt>0 else 0):,.0f} 원")
    
    # 월별 실적 콤보 차트
    monthly_df = df_f.groupby('월').agg(금액=('금액', 'sum'), 건수=('납품요구번호', 'nunique')).reset_index().sort_values('월')
    fig_combo = go.Figure()
    fig_combo.add_trace(go.Bar(x=monthly_df['월'], y=monthly_df['금액'], name='매출액(원)', marker_color='#3b82f6', yaxis='y1'))
    fig_combo.add_trace(go.Scatter(x=monthly_df['월'], y=monthly_df['건수'], name='계약건수(건)', mode='lines+markers+text', text=monthly_df['건수'], textposition='top center', marker_color='#ef4444', yaxis='y2'))
    fig_combo.update_layout(yaxis=dict(title='매출액(원)', showgrid=False), yaxis2=dict(title='계약건수(건)', overlaying='y', side='right', showgrid=False), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("📈 월별 실적 추이")
        st.plotly_chart(fig_combo, use_container_width=True)
    with col_b:
        st.subheader("🍩 시장 점유율")
        top10 = df_f.groupby('업체명')['금액'].sum().nlargest(10).reset_index()
        st.plotly_chart(px.pie(top10, names='업체명', values='금액', hole=0.4), use_container_width=True)

    st.markdown("---")

    # 📋 4. 업체별 랭킹 보드 (교차 피벗)
    st.subheader("📋 업체별 종합 실적 랭킹 보드")
    show_count = st.checkbox("📝 표에 월별/분기별 계약건수 함께 보기", value=False)
    
    pivot_amt = pd.pivot_table(df_f, values='금액', index='업체명', columns='월', aggfunc='sum', fill_value=0).reset_index()
    for m in ['1월', '2월', '3월', '4월']:
        if m not in pivot_amt.columns: pivot_amt[m] = 0
    pivot_amt['1분기 합계'] = pivot_amt['1월'] + pivot_amt['2월'] + pivot_amt['3월']
    pivot_amt['누적 합계'] = pivot_amt['1분기 합계'] + pivot_amt['4월']
    
    pivot_cnt = pd.pivot_table(df_f, values='납품요구번호', index='업체명', columns='월', aggfunc='nunique', fill_value=0).reset_index()
    for m in ['1월', '2월', '3월', '4월']:
        if m not in pivot_cnt.columns: pivot_cnt[m] = 0
    pivot_cnt['1분기(건)'] = pivot_cnt['1월'] + pivot_cnt['2월'] + pivot_cnt['3월']
    pivot_cnt['누적(건)'] = pivot_cnt['1분기(건)'] + pivot_cnt['4월']
    pivot_cnt.rename(columns={'1월':'1월(건)', '2월':'2월(건)', '3월':'3월(건)', '4월':'4월(건)'}, inplace=True)
    
    final_table = pd.merge(pivot_amt, pivot_cnt, on='업체명', how='outer').fillna(0)
    final_table = final_table.sort_values('누적 합계', ascending=False).reset_index(drop=True)
    final_table.insert(0, '랭킹 No.', range(1, len(final_table) + 1))
    
    if show_count:
        cols = ['랭킹 No.', '업체명', '1월', '1월(건)', '2월', '2월(건)', '3월', '3월(건)', '1분기 합계', '1분기(건)', '4월', '4월(건)', '누적 합계', '누적(건)']
    else:
        cols = ['랭킹 No.', '업체명', '1월', '2월', '3월', '1분기 합계', '4월', '누적 합계']
    
    final_table = final_table[cols]
    
    # 스타일링
    fmt = {c: "{:,.0f}" for c in cols if c not in ['랭킹 No.', '업체명']}
    styled = final_table.style.format(fmt)
    styled = styled.set_properties(subset=['업체명'], **{'background-color': 'rgba(128, 128, 128, 0.1)', 'font-weight': 'bold'})
    styled = styled.set_properties(subset=[c for c in cols if '월' in c and '(' not in c], **{'background-color': 'rgba(54, 162, 235, 0.05)'})
    styled = styled.set_properties(subset=['1분기 합계'], **{'background-color': 'rgba(255, 159, 64, 0.1)', 'font-weight': 'bold'})
    if show_count:
        styled = styled.set_properties(subset=[c for c in cols if '(건)' in c], **{'background-color': 'rgba(76, 175, 80, 0.05)'})
    styled = styled.background_gradient(subset=['누적 합계'], cmap='Blues')
    
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # 💾 엑셀 다운로드
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        final_table.to_excel(writer, index=False, sheet_name='실적랭킹')
    st.download_button("💾 엑셀 보고서 다운로드", output.getvalue(), f'조달실적_업체별랭킹_{get_now_kst().strftime("%Y%m%d")}.xlsx')

st.markdown("<br><center style='color:gray;'>Copyright(C) 2026 Joey Kim. Data from Public Data Portal.</center>", unsafe_allow_html=True)
