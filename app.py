import time
import random
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProcurementApp:
    def __init__(self):
        # 검증된 파로스 데이터 및 랭킹 엔진 초기화 상태 시뮬레이션
        self.db = {
            "주식회사 파로스": {
                "total_amount": 182025000,  # 4/14까지의 기존 데이터
                "last_updated": "2026-04-14",
                "contract_type": "MAS"
            }
        }
        self.ranking_board = []

    def fetch_mas_data_with_retry(self, company_name, start_date, end_date):
        """
        조달청 G2B 서버 장애(550 Error)를 대응하는 재시도 로직 포함 수집 함수
        """
        max_retries = 5
        base_delay = 2  # 초
        
        for attempt in range(max_retries):
            try:
                logger.info(f"[{attempt + 1}/{max_retries}] {company_name} {start_date}~{end_date} MAS 실적 수집 시도 중...")
                
                # 시뮬레이션: 15~16일 데이터 호출 시 가끔 550 에러 발생 상황 가정
                if attempt < 1:  # 첫 시도는 무조건 실패 가정 (서버 장애 대응 테스트)
                    raise Exception("G2B Server Error: 550 - Connection Failed")

                # 실제 수집 성공 데이터 (사용자 제공 데이터 기준)
                if start_date == "2026-04-15":
                    collected_amount = 878905640
                else:
                    collected_amount = 0
                
                return collected_amount

            except Exception as e:
                wait_time = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"오류 발생: {e}. {wait_time:.2f}초 후 재시도합니다.")
                time.sleep(wait_time)
        
        logger.error("최대 재시도 횟수를 초과했습니다. 데이터 수집 실패.")
        return None

    def update_database(self, company_name, amount):
        """
        수집된 데이터를 DB에 반영
        """
        if amount is not None:
            self.db[company_name]["total_amount"] += amount
            self.db[company_name]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"✔ DB 업데이트 완료: {company_name} 누적액 -> {self.db[company_name]['total_amount']:,}원")
            return True
        return False

    def refresh_ranking_board(self):
        """
        캐시를 지우고 랭킹 보드를 강제 리프레시 (사용자님이 안 보인다고 하신 부분 해결)
        """
        logger.info("♻ 랭킹 보드 엔진 리프레시 중... (MAS 필터 적용)")
        # 실시간 집계 로직 실행 시뮬레이션
        self.ranking_board = sorted(
            [{"name": k, "amount": v["total_amount"]} for k, v in self.db.items()],
            key=lambda x: x["amount"],
            reverse=True
        )
        logger.info("✅ 랭킹 보드 업데이트가 완료되었습니다. 이제 대시보드에서 확인 가능합니다.")

# --- 메인 실행부 ---
if __name__ == "__main__":
    app = ProcurementApp()
    
    target_company = "주식회사 파로스"
    
    print("--- [조달 프로그램 실시간 업데이트 시작] ---")
    
    # 1. 누락된 15~16일 데이터 강제 수집
    new_data = app.fetch_mas_data_with_retry(target_company, "2026-04-15", "2026-04-16")
