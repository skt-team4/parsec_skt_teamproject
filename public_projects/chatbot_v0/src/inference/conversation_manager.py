"""
대화 관리자
사용자 의도 파악 및 길찾기 제안 관리
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConversationState:
    """대화 상태 관리"""
    last_recommendations: List[Dict] = None
    selected_shop: Dict = None
    user_location: str = None
    waiting_for_navigation: bool = False
    conversation_history: List = None
    last_context_metadata: Dict = None  # NLG가 생성한 맥락 메타데이터
    recent_recommended_categories: List[str] = None  # 최근 추천한 카테고리 목록
    
    def __post_init__(self):
        if self.last_recommendations is None:
            self.last_recommendations = []
        if self.conversation_history is None:
            self.conversation_history = []
        if self.last_context_metadata is None:
            self.last_context_metadata = {}
        if self.recent_recommended_categories is None:
            self.recent_recommended_categories = []


class ConversationManager:
    """대화 흐름 관리자"""
    
    # 가게 선택 의도 패턴
    SELECTION_PATTERNS = [
        r'(\d+)번',  # "1번"
        r'첫\s*번째',  # "첫번째"
        r'두\s*번째',  # "두번째"
        r'세\s*번째',  # "세번째"
        r'(.*?)\s*갈게',  # "삼청골명가 갈게"
        r'(.*?)\s*가고\s*싶',  # "거기 가고 싶어"
        r'(.*?)\s*갈래',  # "거기 갈래"
        r'거기',  # "거기"
        r'그거',  # "그거"
        r'여기',  # "여기로 갈게"
    ]
    
    # 길찾기 수락 패턴 (청소년 슬랭 추가)
    NAVIGATION_ACCEPT_PATTERNS = [
        r'응|ㅇㅇ|웅|어|ㅇ|오케이|ok|okay|네|넵|예|좋아|그래|알려줘|해줘|부탁',
        r'엉|억|어어|ㅇㅋ|ㄱㄱ|ㄱ|갈게|가자|고고',  # 청소년 슬랭 추가
        r'길\s*찾기|길\s*안내|어떻게\s*가|가는\s*방법|가는\s*길|안내.*줘'
    ]
    
    # 길찾기 거절 패턴
    NAVIGATION_REJECT_PATTERNS = [
        r'아니|안|ㄴㄴ|노|괜찮|됐|필요\s*없'
    ]
    
    def __init__(self):
        self.states: Dict[str, ConversationState] = {}
    
    def get_state(self, user_id: str) -> ConversationState:
        """사용자별 대화 상태 가져오기"""
        if user_id not in self.states:
            self.states[user_id] = ConversationState()
        return self.states[user_id]
    
    def update_recommendations(self, user_id: str, recommendations: List[Dict]):
        """추천 결과 업데이트"""
        state = self.get_state(user_id)
        state.last_recommendations = recommendations
        state.selected_shop = None
        state.waiting_for_navigation = False
        
        # 추천된 카테고리 추적 (최근 3개 세션만 유지)
        for rec in recommendations[:3]:  # 상위 3개만 추적
            category = rec.get('category', '')
            if category and category not in state.recent_recommended_categories:
                state.recent_recommended_categories.append(category)
        
        # 최근 5개 카테고리만 유지
        if len(state.recent_recommended_categories) > 5:
            state.recent_recommended_categories = state.recent_recommended_categories[-5:]
        
        logger.info(f"최근 추천 카테고리 업데이트: {state.recent_recommended_categories}")
    
    def check_shop_selection(self, user_id: str, user_input: str) -> Tuple[bool, Optional[Dict]]:
        """
        사용자가 특정 가게를 선택했는지 확인
        
        Returns:
            (선택 여부, 선택된 가게 정보)
        """
        state = self.get_state(user_id)
        
        if not state.last_recommendations:
            return False, None
        
        user_input_lower = user_input.lower()
        
        # 번호로 선택 (1번, 2번, 3번)
        number_match = re.search(r'(\d+)\s*번', user_input)
        if number_match:
            number = int(number_match.group(1))
            if 1 <= number <= len(state.last_recommendations):
                selected = state.last_recommendations[number - 1]
                state.selected_shop = selected
                return True, selected
        
        # 순서로 선택 (첫번째, 두번째)
        ordinal_map = {
            '첫': 1, '두': 2, '세': 3,
            '1': 1, '2': 2, '3': 3
        }
        
        for keyword, index in ordinal_map.items():
            if keyword in user_input_lower and '번째' in user_input_lower:
                if index <= len(state.last_recommendations):
                    selected = state.last_recommendations[index - 1]
                    state.selected_shop = selected
                    return True, selected
        
        # 가게 이름으로 선택
        for rec in state.last_recommendations:
            shop_name = rec.get('shop_name', '')
            if shop_name and shop_name in user_input:
                state.selected_shop = rec
                return True, rec
        
        # "거기 갈게", "여기 가고 싶어" 등의 패턴
        for pattern in self.SELECTION_PATTERNS:
            if re.search(pattern, user_input_lower):
                # 마지막 추천 중 첫 번째를 기본으로 선택
                if state.last_recommendations:
                    selected = state.last_recommendations[0]
                    state.selected_shop = selected
                    return True, selected
        
        return False, None
    
    def should_offer_navigation(self, user_id: str, user_input: str) -> bool:
        """길찾기를 제안해야 하는지 판단"""
        is_selected, shop = self.check_shop_selection(user_id, user_input)
        
        if is_selected and shop:
            state = self.get_state(user_id)
            state.waiting_for_navigation = True
            return True
        
        return False
    
    def check_navigation_response(self, user_id: str, user_input: str) -> Optional[str]:
        """
        길찾기 제안에 대한 사용자 응답 확인
        
        Returns:
            'accept' | 'reject' | None
        """
        state = self.get_state(user_id)
        
        if not state.waiting_for_navigation:
            return None
        
        user_input_lower = user_input.lower().strip()
        
        # 수락 패턴 확인
        for pattern in self.NAVIGATION_ACCEPT_PATTERNS:
            if re.search(pattern, user_input_lower):
                state.waiting_for_navigation = False
                return 'accept'
        
        # 거절 패턴 확인
        for pattern in self.NAVIGATION_REJECT_PATTERNS:
            if re.search(pattern, user_input_lower):
                state.waiting_for_navigation = False
                state.selected_shop = None
                return 'reject'
        
        return None
    
    def set_user_location(self, user_id: str, location: str):
        """사용자 위치 설정"""
        state = self.get_state(user_id)
        state.user_location = location
    
    def get_selected_shop(self, user_id: str) -> Optional[Dict]:
        """선택된 가게 정보 가져오기"""
        state = self.get_state(user_id)
        return state.selected_shop
    
    def generate_navigation_offer_message(self, shop_name: str) -> str:
        """길찾기 제안 메시지 생성"""
        messages = [
            f"오~ {shop_name} 가는구나! 길 안내해줄까? 🗺️",
            f"{shop_name}! 좋은 선택이야~ 어떻게 가는지 알려줄까?",
            f"헤헤 {shop_name} 맛있겠다! T맵으로 길찾기 할래?",
            f"{shop_name} 가려고? 나한테 길 안내 맡겨줄래? 😊"
        ]
        
        import random
        return random.choice(messages)
    
    def generate_navigation_ready_message(self) -> str:
        """길찾기 준비 메시지 생성"""
        messages = [
            "좋아! 지금 있는 곳이 어디야? (예: 강남역, 홍대입구)",
            "오케이! 어디서 출발할거야? 🚶",
            "알겠어! 현재 위치 알려줘~ (예: 신촌역)",
            "그래! 어디서 출발하는지 말해줘!"
        ]
        
        import random
        return random.choice(messages)
    
    def generate_rejection_response(self) -> str:
        """길찾기 거절 응답 메시지"""
        messages = [
            "알겠어! 맛있게 먹고 와~ 😋",
            "오키! 다른 거 필요하면 말해줘!",
            "그래그래~ 혹시 또 필요한 거 있으면 불러!",
            "응응! 맛있게 먹어! 🍴"
        ]
        
        import random
        return random.choice(messages)
    
    def clear_state(self, user_id: str):
        """대화 상태 초기화"""
        if user_id in self.states:
            del self.states[user_id]
    
    def add_message(self, user_id: str, role: str, content: str):
        """대화 히스토리에 메시지 추가"""
        state = self.get_state(user_id)
        if state.conversation_history is None:
            state.conversation_history = []
        state.conversation_history.append({"role": role, "content": content})
    
    def update_context(self, user_id: str, context_metadata: Dict):
        """NLG가 생성한 맥락 메타데이터 업데이트"""
        state = self.get_state(user_id)
        state.last_context_metadata = context_metadata
        logger.info(f"[ConversationManager] 맥락 업데이트: {context_metadata}")
    
    def get_last_context(self, user_id: str) -> Optional[Dict]:
        """마지막 맥락 메타데이터 반환"""
        state = self.get_state(user_id)
        return state.last_context_metadata
    
    def get_formatted_history(self, user_id: str, max_turns: int = 5) -> List[Dict[str, str]]:
        """LLM에 전달할 대화 히스토리 반환"""
        state = self.get_state(user_id)
        if not state.conversation_history:
            return []
        # 최근 N턴만 반환
        recent_history = state.conversation_history[-(max_turns * 2):] if len(state.conversation_history) > max_turns * 2 else state.conversation_history
        return recent_history
    
    def get_context_summary(self, user_id: str) -> str:
        """현재 대화 상태 요약"""
        state = self.get_state(user_id)
        summary = []
        
        # 최근 추천 있었는지
        if state.last_recommendations:
            recs = ", ".join([r.get('shop_name', '') for r in state.last_recommendations[:3]])
            summary.append(f"최근 추천: {recs}")
        
        # 사용자 위치
        if state.user_location:
            summary.append(f"위치: {state.user_location}")
        
        # 길찾기 대기 상태
        if state.waiting_for_navigation:
            summary.append("길찾기 응답 대기 중")
        
        return " | ".join(summary) if summary else ""


# 전역 대화 관리자 인스턴스
conversation_manager = ConversationManager()


def test_conversation_flow():
    """대화 흐름 테스트"""
    
    manager = ConversationManager()
    user_id = "test_user"
    
    # 추천 설정
    recommendations = [
        {'shop_id': 1, 'shop_name': '삼청골명가'},
        {'shop_id': 2, 'shop_name': '국밥특공대'},
        {'shop_id': 3, 'shop_name': '서울호떡'}
    ]
    manager.update_recommendations(user_id, recommendations)
    
    # 테스트 케이스
    test_cases = [
        ("1번 갈게", True),
        ("삼청골명가 갈래", True),
        ("거기 가고 싶어", True),
        ("다른 거 추천해줘", False),
        ("뭐가 맛있어?", False)
    ]
    
    print("대화 흐름 테스트")
    print("=" * 50)
    
    for user_input, expected in test_cases:
        is_selected, shop = manager.check_shop_selection(user_id, user_input)
        result = "✓" if is_selected == expected else "✗"
        print(f"{result} '{user_input}' → 선택: {is_selected}")
        if shop:
            print(f"   선택된 가게: {shop['shop_name']}")
    
    # 길찾기 응답 테스트
    print("\n길찾기 응답 테스트")
    print("-" * 50)
    
    manager.get_state(user_id).waiting_for_navigation = True
    
    navigation_tests = [
        ("ㅇㅇ", "accept"),
        ("응 알려줘", "accept"),
        ("아니 괜찮아", "reject"),
        ("ㄴㄴ", "reject")
    ]
    
    for user_input, expected in navigation_tests:
        manager.get_state(user_id).waiting_for_navigation = True
        response = manager.check_navigation_response(user_id, user_input)
        result = "✓" if response == expected else "✗"
        print(f"{result} '{user_input}' → {response}")


if __name__ == "__main__":
    test_conversation_flow()