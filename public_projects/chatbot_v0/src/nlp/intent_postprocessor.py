#!/usr/bin/env python3
"""
의도 후처리기
10개 단순화 의도를 28개 세부 의도로 매핑
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class IntentMapping:
    """의도 매핑 정보"""
    simplified: str  # 10개 단순화 의도
    detailed: str    # 28개 세부 의도
    confidence_boost: float = 0.0  # 신뢰도 보정값


class IntentPostProcessor:
    """의도 후처리기 - 10개 → 28개 매핑"""
    
    def __init__(self):
        self.intent_map = self._build_intent_mapping()
        self.context_rules = self._build_context_rules()
        
    def _build_intent_mapping(self) -> Dict[str, List[str]]:
        """10개 의도 → 28개 의도 매핑 테이블"""
        return {
            # 1. 추천/검색 (40%) → 음식 관련 의도들
            "음식추천": [  # A.X Encoder NLU가 사용하는 레이블
                "food_request",        # 음식 추천 요청
                "restaurant_search",   # 가게 검색
                "menu_recommendation", # 메뉴 추천
                "category_search",     # 카테고리별 검색
                "nearby_search",       # 근처 검색
                "popular_request",     # 인기 메뉴/가게
                "modify_request"       # 부정 피드백 (다른 추천 요청)
            ],
            "recommendation": [  # 호환성을 위해 유지
                "food_request",        # 음식 추천 요청
                "restaurant_search",   # 가게 검색
                "menu_recommendation", # 메뉴 추천
                "category_search",     # 카테고리별 검색
                "nearby_search",       # 근처 검색
                "popular_request",     # 인기 메뉴/가게
                "modify_request"       # 부정 피드백 (다른 추천 요청)
            ],
            
            # 2. 정보 문의 (15%) → 상세 정보 요청
            "info_inquiry": [
                "price_inquiry",       # 가격 문의
                "nutrition_inquiry",   # 영양 정보
                "review_inquiry",      # 리뷰/평점
                "ingredient_inquiry",  # 재료/성분
                "allergy_inquiry",     # 알레르기 정보
                "discount_inquiry"     # 할인 정보
            ],
            
            # 3. 운영 정보 (10%) → 가게 운영 관련
            "operation": [
                "time_inquiry",        # 영업시간
                "location_inquiry",    # 위치/주소
                "contact_inquiry",     # 연락처
                "holiday_inquiry"      # 휴무일
            ],
            
            # 4. 서비스 (10%) → 서비스 옵션
            "service": [
                "delivery_inquiry",    # 배달 가능 여부
                "packaging_inquiry",   # 포장 가능 여부
                "reservation_inquiry", # 예약 가능 여부
                "payment_inquiry",     # 결제 수단
                "student_discount"     # 학생 할인/급식카드
            ],
            
            # 5. 예산 (10%) → 가격대별 추천
            "budget": [
                "budget_constraint",   # 예산 제약
                "cheap_request",       # 저렴한 메뉴
                "value_request"        # 가성비
            ],
            
            # 6. 특별 요구 (5%) → 특수 상황
            "special": [
                "solo_dining",         # 혼밥
                "group_dining",        # 단체
                "date_place",          # 데이트
                "quiet_place"          # 조용한 곳
            ],
            
            # 7. 인사 (3%)
            "greeting": [
                "greeting"             # 인사
            ],
            
            # 8. 종료 (3%)
            "closing": [
                "thanks",              # 감사
                "goodbye",             # 작별
                "feedback"             # 피드백
            ],
            
            # 9. 무의미 (2%)
            "nonsense": [
                "nonsense",            # 무의미한 입력
                "spam"                 # 스팸
            ],
            
            # 10. 기타 (2%)
            "other": [
                "other",               # 기타
                "unknown"              # 알 수 없음
            ],
            
            # A.X Encoder NLU의 10개 의도 추가 매핑
            "일반대화": [           # A.X Encoder 레이블
                "general_chat",      # 일반 대화
                "chitchat",         # 잡담
                "modify_request"    # 부정 피드백 시 변환될 의도
            ],
            "가격문의": [           # A.X Encoder 레이블
                "price_inquiry"
            ],
            "잔액확인": [           # A.X Encoder 레이블
                "balance_check"
            ],
            "쿠폰조회": [           # A.X Encoder 레이블
                "coupon_inquiry"
            ],
            "가게정보": [           # A.X Encoder 레이블
                "shop_inquiry",
                "restaurant_search"
            ],
            "위치검색": [           # A.X Encoder 레이블
                "location_inquiry",
                "nearby_search"
            ],
            "영업시간": [           # A.X Encoder 레이블
                "time_inquiry"
            ],
            "감사인사": [           # A.X Encoder 레이블
                "thanks",
                "feedback"
            ],
            "기타": [               # A.X Encoder 레이블
                "other",
                "unknown"
            ]
        }
    
    def _build_context_rules(self) -> Dict[str, Dict]:
        """컨텍스트 기반 세부 의도 결정 규칙"""
        return {
            "음식추천": {  # A.X Encoder NLU가 사용하는 레이블
                "keywords": {
                    "추천": "menu_recommendation",
                    "검색": "restaurant_search",
                    "근처": "nearby_search",
                    "인기": "popular_request",
                    "뭐": "food_request",
                    "찾": "restaurant_search",
                    "별로": "modify_request",
                    "별론데": "modify_request",  # 추가
                    "그닥": "modify_request",     # 추가
                    "아닌데": "modify_request",   # 추가
                    "안땡": "modify_request",     # 추가 (청소년 슬랭)
                    "싫어": "modify_request",
                    "싫은데": "modify_request",   # 추가
                    "말고": "modify_request",
                    "다른": "modify_request",
                    "딴": "modify_request"        # 추가
                },
                "entities": {
                    "location": "nearby_search",
                    "food": "category_search",
                    "both": "restaurant_search"
                }
            },
            "recommendation": {  # 호환성을 위해 유지
                "keywords": {
                    "추천": "menu_recommendation",
                    "검색": "restaurant_search",
                    "근처": "nearby_search",
                    "인기": "popular_request",
                    "뭐": "food_request",
                    "찾": "restaurant_search",
                    "별로": "modify_request",
                    "별론데": "modify_request",  # 추가
                    "그닥": "modify_request",     # 추가
                    "아닌데": "modify_request",   # 추가
                    "안땡": "modify_request",     # 추가 (청소년 슬랭)
                    "싫어": "modify_request",
                    "싫은데": "modify_request",   # 추가
                    "말고": "modify_request",
                    "다른": "modify_request",
                    "딴": "modify_request"        # 추가
                },
                "entities": {
                    "location": "nearby_search",
                    "food": "category_search",
                    "both": "restaurant_search"
                }
            },
            "info_inquiry": {
                "keywords": {
                    "가격": "price_inquiry",
                    "얼마": "price_inquiry",
                    "칼로리": "nutrition_inquiry",
                    "영양": "nutrition_inquiry",
                    "평점": "review_inquiry",
                    "리뷰": "review_inquiry",
                    "재료": "ingredient_inquiry",
                    "알레르기": "allergy_inquiry",
                    "할인": "discount_inquiry",
                    "세일": "discount_inquiry"
                }
            },
            "operation": {
                "keywords": {
                    "시간": "time_inquiry",
                    "언제": "time_inquiry",
                    "열": "time_inquiry",
                    "위치": "location_inquiry",
                    "어디": "location_inquiry",
                    "주소": "location_inquiry",
                    "전화": "contact_inquiry",
                    "연락": "contact_inquiry",
                    "휴무": "holiday_inquiry"
                }
            },
            "service": {
                "keywords": {
                    "배달": "delivery_inquiry",
                    "딜리버리": "delivery_inquiry",
                    "포장": "packaging_inquiry",
                    "테이크아웃": "packaging_inquiry",
                    "예약": "reservation_inquiry",
                    "카드": "payment_inquiry",
                    "현금": "payment_inquiry",
                    "급식": "student_discount",
                    "학생": "student_discount"
                }
            },
            "budget": {
                "keywords": {
                    "싸": "cheap_request",
                    "저렴": "cheap_request",
                    "가성비": "value_request",
                    "예산": "budget_constraint"
                },
                "price_entity": True  # 가격 엔티티 있으면 budget_constraint
            },
            "일반대화": {  # A.X Encoder NLU가 사용하는 레이블
                "keywords": {
                    "별로": "modify_request",
                    "별론데": "modify_request",
                    "그닥": "modify_request",
                    "아닌데": "modify_request",
                    "안땡": "modify_request",
                    "싫어": "modify_request",
                    "말고": "modify_request",
                    "다른": "modify_request",
                    "딴": "modify_request",
                    "빼고": "modify_request",
                    "제외": "modify_request"
                },
                "default": "general_chat"  # 키워드 없으면 general_chat
            }
        }
    
    def process(
        self,
        simplified_intent: str,
        text: str,
        entities: Dict[str, bool],
        confidence: float = 0.0
    ) -> Tuple[str, float]:
        """
        10개 단순화 의도를 28개 세부 의도로 변환
        
        Args:
            simplified_intent: 10개 중 하나의 단순화 의도
            text: 원본 사용자 입력
            entities: 감지된 엔티티 (location, food, price)
            confidence: 원본 신뢰도
            
        Returns:
            (세부_의도, 보정된_신뢰도)
        """
        
        logger.info(f"[DEBUG PostProcessor] 입력: intent='{simplified_intent}', text='{text}', entities={entities}")
        
        # 기본 매핑 가져오기
        possible_intents = self.intent_map.get(simplified_intent, ["unknown"])
        
        # 단순 매핑 (1:1 매핑인 경우)
        if len(possible_intents) == 1:
            return possible_intents[0], confidence
        
        # 컨텍스트 기반 세부 의도 결정
        detailed_intent = self._determine_detailed_intent(
            simplified_intent, text, entities, possible_intents
        )
        
        # 신뢰도 보정
        adjusted_confidence = self._adjust_confidence(
            simplified_intent, detailed_intent, confidence, text
        )
        
        logger.debug(f"의도 후처리: {simplified_intent} → {detailed_intent} (신뢰도: {confidence:.2f} → {adjusted_confidence:.2f})")
        
        return detailed_intent, adjusted_confidence
    
    def _determine_detailed_intent(
        self,
        simplified: str,
        text: str,
        entities: Dict[str, bool],
        possible_intents: List[str]
    ) -> str:
        """컨텍스트 기반으로 세부 의도 결정"""
        
        logger.info(f"[DEBUG _determine_detailed_intent] simplified='{simplified}', text='{text}', possible={possible_intents}")
        
        # 부정 피드백 패턴 우선 체크
        negative_patterns = ['별로', '별론데', '싫어', '안좋', '다른', '말고', '아니', '그거말고', '빼고', '제외', '그닥', '안땡']
        if any(pattern in text.lower() for pattern in negative_patterns):
            logger.info(f"[DEBUG] 부정 패턴 감지: '{text}' in simplified='{simplified}'")
            
            # general_chat이나 음식추천에서 부정 패턴 → modify_request
            if simplified in ['general_chat', '일반대화', 'chitchat', '음식추천', 'recommendation']:
                logger.info(f"[DEBUG] {simplified}에서 부정 패턴 → modify_request 변환")
                # general_chat은 possible_intents가 없을 수 있으므로 바로 반환
                return "modify_request"
            
            # 음식 관련 단어가 있으면 modify_request
            food_keywords = ['치킨', '피자', '햄버거', '중식', '한식', '일식', '양식', '분식', '카페']
            if any(food in text.lower() for food in food_keywords):
                if "modify_request" in possible_intents:
                    return "modify_request"
        
        rules = self.context_rules.get(simplified, {})
        
        # 1. 키워드 기반 매칭
        if "keywords" in rules:
            for keyword, intent in rules["keywords"].items():
                if keyword in text.lower():
                    if intent in possible_intents:
                        return intent
        
        # 2. 엔티티 기반 매칭
        if "entities" in rules:
            entity_rules = rules["entities"]
            
            # 특별 케이스: location과 food 둘 다 있는 경우
            if entities.get("location") and entities.get("food"):
                if "both" in entity_rules:
                    return entity_rules["both"]
            
            # 개별 엔티티 체크
            for entity_name, intent in entity_rules.items():
                if entity_name != "both" and entities.get(entity_name):
                    if intent in possible_intents:
                        return intent
        
        # 3. 특별 규칙 (예: budget의 price_entity)
        if simplified == "budget" and entities.get("price"):
            return "budget_constraint"
        
        # 4. 기본값: 첫 번째 가능한 의도
        return possible_intents[0]
    
    def _adjust_confidence(
        self,
        simplified: str,
        detailed: str,
        original_confidence: float,
        text: str
    ) -> float:
        """신뢰도 보정"""
        
        adjusted = original_confidence
        
        # 명확한 키워드가 있으면 신뢰도 상승
        boost_keywords = {
            "food_request": ["추천", "뭐 먹", "먹고 싶"],
            "price_inquiry": ["얼마", "가격", "비싸"],
            "delivery_inquiry": ["배달", "딜리버리"],
            "time_inquiry": ["몇시", "언제", "영업시간"]
        }
        
        if detailed in boost_keywords:
            for keyword in boost_keywords[detailed]:
                if keyword in text:
                    adjusted = min(1.0, adjusted + 0.1)
                    break
        
        # 애매한 경우 신뢰도 하락
        if simplified == "other" or detailed == "unknown":
            adjusted *= 0.8
        
        return min(1.0, max(0.0, adjusted))
    
    def get_intent_info(self, detailed_intent: str) -> Dict[str, str]:
        """세부 의도에 대한 정보 반환"""
        
        intent_descriptions = {
            "food_request": "음식 추천 요청",
            "restaurant_search": "가게 검색",
            "menu_recommendation": "메뉴 추천",
            "price_inquiry": "가격 문의",
            "delivery_inquiry": "배달 문의",
            "time_inquiry": "영업시간 문의",
            "budget_constraint": "예산 제약 추천",
            "student_discount": "학생 할인/급식카드",
            # ... 나머지 의도들
        }
        
        # 역매핑으로 단순화 의도 찾기
        simplified = None
        for simp, detailed_list in self.intent_map.items():
            if detailed_intent in detailed_list:
                simplified = simp
                break
        
        return {
            "detailed": detailed_intent,
            "simplified": simplified or "unknown",
            "description": intent_descriptions.get(detailed_intent, "알 수 없는 의도"),
            "category_size": len(self.intent_map.get(simplified, []))
        }


# 테스트
if __name__ == "__main__":
    processor = IntentPostProcessor()
    
    test_cases = [
        ("recommendation", "부평 피자 추천해줘", {"location": True, "food": True}, 0.95),
        ("info_inquiry", "가격 얼마야?", {"price": True}, 0.90),
        ("service", "급식카드 되나요?", {}, 0.88),
        ("budget", "만원 이하 메뉴", {"price": True}, 0.92),
        ("operation", "지금 열어있어?", {}, 0.85),
    ]
    
    print("=== 의도 후처리 테스트 ===\n")
    for simplified, text, entities, conf in test_cases:
        detailed, adj_conf = processor.process(simplified, text, entities, conf)
        info = processor.get_intent_info(detailed)
        
        print(f"입력: \"{text}\"")
        print(f"  단순화: {simplified} → 세부: {detailed}")
        print(f"  신뢰도: {conf:.2%} → {adj_conf:.2%}")
        print(f"  설명: {info['description']}")
        print()