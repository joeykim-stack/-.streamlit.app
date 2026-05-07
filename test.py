import requests

# 우리가 테스트할 새 인증키
RAW_KEY = "15bc460106a7359afdd54c91410a8dd94c17076ba2aa7d4308cfb8e07e9ce5ae"

# 1. 브라우저에서 성공했던 구형 주소
URL_OLD = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getDlvrReqInfoList"
# 2. 매뉴얼 상의 신형 V5 주소
URL_V5 = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService05/getDlvrReqInfoList"

# 크롬 브라우저 완벽 위장
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

def run_diagnostic(url_base, name):
    print(f"\n==================================================")
    print(f"🔬 [{name}] 진단 시작...")
    print(f"==================================================")
    
    # requests의 개입을 막기 위해 파라미터를 문자열로 완벽히 수동 조립
    req_url = f"{url_base}?serviceKey={RAW_KEY}&numOfRows=10&pageNo=1&inqryDiv=1&inqryBgnDate=20260401&inqryEndDate=20260420"
    
    print(f"1️⃣ 파이썬이 준비한 URL:\n{req_url}\n")
    
    try:
        # 파라미터(params) 없이 통짜 주소 그대로 던짐!
        res = requests.get(req_url, headers=headers, timeout=10)
        
        print(f"2️⃣ 서버로 실제 날아간 URL (requests가 변조했는지 확인):\n{res.request.url}\n")
        print(f"3️⃣ HTTP 상태 코드: {res.status_code}\n")
        
        # XML 응답 결과 앞부분만 출력해서 진짜 07인지, 00(성공)인지 확인
        print(f"4️⃣ 서버 응답(Response):\n{res.text[:400]}")
        
    except Exception as e:
        print(f"🚨 통신 실패: {e}")

# 두 가지 경우를 모두 테스트
run_diagnostic(URL_OLD, "TEST 1: 구형 서버 (크롬 성공 주소)")
run_diagnostic(URL_V5, "TEST 2: 최신 V5 서버")
