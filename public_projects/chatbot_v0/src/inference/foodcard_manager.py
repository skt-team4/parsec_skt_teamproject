"""
급식카드 잔액 조회 시스템 (추천 챗봇용)
"""

import logging
from typing import Dict, Optional
from datetime import datetime

from src.data.data_structure import FoodcardUser

logger = logging.getLogger(__name__)


class FoodcardManager:
    """급식카드 잔액 조회 전용 (추천 챗봇용)"""
    
    def __init__(self):
        self.users: Dict[int, FoodcardUser] = {}
        
        # 설정값
        self.LOW_BALANCE_THRESHOLD = 5000  # 잔액 부족 임계값
        
        logger.info("급식카드 잔액 조회 시스템 초기화 완료")
    
    def register_user(self, user_id: int, card_number: str, 
                     initial_balance: int = 0, target_age_group: str = "청소년") -> FoodcardUser:
        """급식카드 사용자 등록"""
        if user_id in self.users:
            logger.warning(f"이미 등록된 사용자: {user_id}")
            return self.users[user_id]
        
        foodcard_user = FoodcardUser(
            user_id=user_id,
            card_number=card_number,
            balance=initial_balance,
            status="ACTIVE",
            target_age_group=target_age_group
        )
        
        self.users[user_id] = foodcard_user
        logger.info(f"급식카드 사용자 등록: {user_id}, 초기 잔액: {initial_balance}")
        
        return foodcard_user
    
    def get_user(self, user_id: int) -> Optional[FoodcardUser]:
        """사용자 정보 조회"""
        return self.users.get(user_id)
    
    def check_balance(self, user_id: int) -> Optional[int]:
        """잔액 확인"""
        user = self.users.get(user_id)
        if not user:
            logger.warning(f"등록되지 않은 사용자: {user_id}")
            return None
        
        return user.balance
    
    def can_afford(self, user_id: int, amount: int) -> bool:
        """예산 내 구매 가능 여부 확인 (추천용)"""
        user = self.users.get(user_id)
        if not user:
            return False
        
        if user.status != "ACTIVE":
            return False
        
        return user.balance >= amount
    
    
    
    
    def is_low_balance(self, user_id: int) -> bool:
        """저잔액 상태 확인"""
        user = self.users.get(user_id)
        if not user:
            return False
        
        return user.balance < self.LOW_BALANCE_THRESHOLD
    
    
    


# 예시 사용법
if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(level=logging.INFO)
    
    # 매니저 생성
    manager = FoodcardManager()
    
    # 사용자 등록
    user = manager.register_user(
        user_id=1,
        card_number="1234-5678-9012",
        initial_balance=20000,
        target_age_group="청소년"
    )
    
    # 잔액 확인
    balance = manager.check_balance(1)
    print(f"현재 잔액: {balance:,}원")
    
    # 예산 내 구매 가능성 확인
    can_buy = manager.can_afford(1, 8000)
    print(f"8,000원 메뉴 구매 가능: {can_buy}")
    
    # 저잔액 상태 확인
    is_low = manager.is_low_balance(1)
    print(f"저잔액 상태: {is_low}")