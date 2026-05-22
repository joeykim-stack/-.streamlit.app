# 4. 데이터 수집 및 DB 업로드 (디버깅 모드 추가)
def run_crawler():
    API_KEY = st.secrets["API_KEY"]
    bgn_date = (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")
    url = f"http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList?serviceKey={API_KEY}&numOfRows=10&pageNo=1&inqryDiv=1&inqryBgnDate={bgn_date}&inqryEndDate={end_date}"
    
    try:
        res = requests.get(url, verify=False)
        root = ET.fromstring(res.content)
        items = root.findall('.//item')
        
        if not items: return 0
        
        # 🚨 [디버깅] 첫 번째 아이템의 구조를 그대로 다 출력해봐!
        st.write("### 🚨 API 원본 데이터 샘플 (첫 번째 아이템의 모든 필드)")
        for child in items[0]:
            st.write(f"{child.tag}: {child.text}")
            
        # 이후 적재 로직은 동일
        # ...
