"""
나비얌 챗봇 데이터 구조 정의
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import sys
from pathlib import Path

# utils 디렉토리를 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))
from src.utils.categories import FOOD_CATEGORIES, is_valid_category


class IntentType(Enum):
    """의도 분류 열거형"""
    # === 추천/검색 관련 ===
    FOOD_REQUEST = "food_request"  # 음식 추천 요청
    SHOP_INQUIRY = "shop_inquiry"  # 특정 가게 문의
    MENU_INQUIRY = "menu_inquiry"  # 메뉴 관련 질문
    COMPARISON = "comparison"  # 비교 요청 ("A vs B 뭐가 나아?")
    
    # === 가격/결제 관련 ===
    PRICE_INQUIRY = "price_inquiry"  # 가격 문의
    BUDGET_INQUIRY = "budget_inquiry"  # 예산 관련 질문
    PAYMENT_METHOD = "payment_method"  # 결제 수단 문의 ("카드 되나요?")
    COUPON_INQUIRY = "coupon_inquiry"  # 쿠폰/할인 관련
    
    # === 위치/길찾기 관련 ===
    LOCATION_INQUIRY = "location_inquiry"  # 위치 관련 질문
    NAVIGATION_REQUEST = "navigation_request"  # 길 안내 요청 ("어떻게 가?")
    
    # === 운영/서비스 관련 ===
    TIME_INQUIRY = "time_inquiry"  # 시간/운영시간 질문
    DELIVERY_INQUIRY = "delivery_inquiry"  # 배달/포장 관련
    RESERVATION_REQUEST = "reservation_request"  # 예약 요청
    
    # === 식단/건강 관련 ===
    NUTRITIONAL_INFO = "nutritional_info"  # 영양 정보 요청
    ALLERGY_INFO = "allergy_info"  # 알레르기 정보 ("땅콩 알레르기 있는데")
    DIETARY_RESTRICTION = "dietary_restriction"  # 식이 제한 ("비건/할랄")
    
    # === 리뷰/평가 관련 ===
    MENU_REVIEW = "menu_review"  # 메뉴 리뷰
    RATING_REQUEST = "rating_request"  # 평점 요청 ("평점 몇점?")
    REVIEW_REQUEST = "review_request"  # 리뷰 보기 요청
    
    # === 대화 관리 ===
    GREETING = "greeting"  # 인사말
    CHITCHAT = "chitchat"  # 일상 대화
    THANKS = "thanks"  # 감사 표현
    GOODBYE = "goodbye"  # 대화 종료
    NONSENSE = "nonsense"  # 무의미한 입력
    MODIFY_REQUEST = "modify_request"  # 요청 수정 ("아니다, 피자로 바꿔줘")
    RECOMMENDATION_HISTORY = "recommendation_history"  # 이전 추천 조회 ("아까 뭐였지?")
    
    # === 기타 ===
    SPECIAL_REQUEST = "special_request"  # 특별 요구사항 (혼밥, 데이트 등)
    MENU_OPTION = "menu_option"  # 메뉴 옵션 (맵기, 양 등)
    BALANCE_CHECK = "balance_check"  # 급식카드 잔액 확인
    BALANCE_CHARGE = "balance_charge"  # 급식카드 충전
    GENERAL_CHAT = "general_chat"  # 일반 대화 (그룹)
    UNKNOWN = "unknown"  # 알 수 없는 의도


class ConfidenceLevel(Enum):
    """신뢰도 수준"""
    HIGH = "high"  # 0.8 이상
    MEDIUM = "medium"  # 0.5-0.8
    MEDIUM_LOW = 'medium_low' # 0.3 ~ 0.5
    LOW = "low"  # 0.5 미만
    VERY_LOW = 'very_low' # 0.2 미만


@dataclass
class UserInput:
    """사용자 입력 데이터"""
    text: str  # 원본 사용자 입력
    user_id: str  # 사용자 ID
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str = ""  # 대화 세션 ID

    def __post_init__(self):
        if not self.session_id:
            self.session_id = f"{self.user_id}_{self.timestamp.strftime('%Y%m%d_%H%M%S')}"


@dataclass
class NaviyamShop:
    """나비얌 가게 정보"""
    id: int
    name: str
    category: str
    is_good_influence_shop: bool  # 착한가게 여부
    is_food_card_shop: str  # 푸드카드 사용 가능 여부 ('Y', 'N', 'P', 'U')
    address: str
    open_hour: str
    close_hour: str
    break_start_hour: Optional[str] = None
    break_end_hour: Optional[str] = None
    current_status: str = "UNKNOWN"  # OPEN, CLOSED, BREAK_TIME, UNKNOWN
    owner_message: Optional[str] = None
    ordinary_discount: bool = False  # 일반 할인 제공 여부
    
    # 추가 필드들 (문서 기반)
    road_address: Optional[str] = None  # 도로명 주소
    phone: Optional[str] = None  # 전화번호
    latitude: Optional[float] = None  # 위도
    longitude: Optional[float] = None  # 경도
    popularity_score: float = 0.0  # 인기도 점수 (0.0 ~ 1.0)
    quality_score: float = 0.0  # 품질 점수 (0.0 ~ 1.0)
    recommendation_count: int = 0  # 추천 횟수
    
    def __post_init__(self):
        # 카테고리 유효성 검증
        if not is_valid_category(self.category):
            # 복합 카테고리인 경우 첫 번째 카테고리로 설정
            if "/" in self.category:
                first_category = self.category.split("/")[0].strip()
                if is_valid_category(first_category):
                    self.category = first_category
                else:
                    self.category = "한식"  # 기본값
            else:
                self.category = "한식"  # 기본값
        
        # is_food_card_shop 유효성 검증
        if self.is_food_card_shop not in ['Y', 'N', 'P', 'U']:
            self.is_food_card_shop = 'U'  # 미확인


@dataclass
class NaviyamMenu:
    """나비얌 메뉴 정보"""
    id: int
    shop_id: int
    name: str
    price: int
    description: Optional[str] = None
    category: Optional[str] = None  # 메인메뉴, 세트메뉴, 사이드메뉴, 음료, 디저트
    is_popular: bool = False  # 인기 메뉴 여부
    options: List[Dict] = field(default_factory=list)  # 메뉴 옵션들
    
    # 추가 필드들 (실용적인 것만)
    is_available: bool = True  # 판매 가능 여부
    recommendation_frequency: int = 0  # 추천 횟수
    dietary_info: Optional[str] = None  # 간단한 식이 정보 (예: "채식,글루텐프리")


@dataclass
class NaviyamCoupon:
    """나비얌 쿠폰 정보"""
    id: str
    name: str
    description: str
    amount: int = 0  # 할인 금액 (정액 할인)
    discount_rate: float = 0.0  # 할인율 (0.0 ~ 1.0)
    min_amount: Optional[int] = None  # 최소 주문 금액
    usage_type: str = "ALL"  # ALL, SHOP, CATEGORY, FOODCARD, GOOD_SHOP, EMERGENCY
    target: List[str] = field(default_factory=lambda: ["ALL"])
    applicable_shops: List[int] = field(default_factory=list)
    valid_from: Optional[str] = None  # 유효 시작일
    valid_until: Optional[str] = None  # 유효 종료일
    
    def calculate_discount(self, price: int) -> int:
        """할인 금액 계산"""
        if self.amount > 0:
            return min(self.amount, price)
        elif self.discount_rate > 0:
            return int(price * self.discount_rate)
        return 0
    
    def is_valid(self) -> bool:
        """쿠폰 유효성 검사"""
        from datetime import datetime
        now = datetime.now()
        
        if self.valid_from:
            start = datetime.fromisoformat(self.valid_from.replace('Z', '+00:00'))
            if now < start:
                return False
                
        if self.valid_until:
            end = datetime.fromisoformat(self.valid_until.replace('Z', '+00:00'))
            if now > end:
                return False
                
        return True


@dataclass
class ExtractedEntity:
    """추출된 엔티티 정보"""
    food_type: Optional[str] = None  # 음식 종류 (치킨, 한식 등)
    budget: Optional[int] = None  # 예산 (원 단위)
    location_preference: Optional[str] = None  # 지역 선호 (근처, 강남 등)
    companions: List[str] = field(default_factory=list)  # 동반자 (친구, 가족)
    time_preference: Optional[str] = None  # 시간 선호 (지금, 저녁)
    menu_options: List[str] = field(default_factory=list)  # 메뉴 옵션 (맵게, 곱배기)
    special_requirements: List[str] = field(default_factory=list)  # 특별 요구사항


@dataclass
class ExtractedInfo:
    """챗봇이 추출한 구조화 정보"""
    intent: IntentType
    entities: ExtractedEntity
    confidence: float  # 추출 신뢰도 (0.0-1.0)
    confidence_level: ConfidenceLevel
    raw_text: str  # 원본 텍스트

    def __post_init__(self):
        # 신뢰도 수준 자동 설정
        if self.confidence >= 0.8:
            self.confidence_level = ConfidenceLevel.HIGH
        elif self.confidence >= 0.5:
            self.confidence_level = ConfidenceLevel.MEDIUM
        elif self.confidence >= 0.3:
            self.confidence_level = ConfidenceLevel.MEDIUM_LOW  # 추가
        elif self.confidence >= 0.2:
            self.confidence_level = ConfidenceLevel.LOW
        else:
            self.confidence_level = ConfidenceLevel.VERY_LOW

@dataclass
class UserProfile:
    """사용자 프로필 (개인화용)"""
    user_id: str
    preferred_categories: List[str] = field(default_factory=list)  # 선호 음식 카테고리
    average_budget: Optional[int] = None  # 평균 예산
    favorite_shops: List[int] = field(default_factory=list)  # 즐겨찾는 가게
    recent_orders: List[Dict] = field(default_factory=list)  # 최근 주문 이력
    conversation_style: str = "friendly"  # 대화 스타일
    last_updated: datetime = field(default_factory=datetime.now)

    def update_preferences(self, new_order: Dict):
        """새로운 주문 정보로 선호도 업데이트"""
        self.recent_orders.append(new_order)
        # 최근 10개만 유지
        if len(self.recent_orders) > 10:
            self.recent_orders = self.recent_orders[-10:]
        self.last_updated = datetime.now()

    taste_preferences: Dict[str, float] = field(default_factory=dict)  # {"매운맛": 0.3, "짠맛": 0.8}
    companion_patterns: List[str] = field(default_factory=list)  # ["친구", "혼자", "가족"]
    location_preferences: List[str] = field(default_factory=list)  # ["건국대", "강남"]
    good_influence_preference: float = 0.5  # 착한가게 선호도
    interaction_count: int = 0  # 총 상호작용 횟수
    data_completeness: float = 0.0  # 데이터 완성도 (0.0 ~ 1.0)


@dataclass
class Recommendation:
    """추천 결과 데이터"""
    shop_id: int
    shop_name: str
    score: float  # 추천 점수 (0.0 ~ 1.0)
    reason: str  # 추천 이유
    menu_suggestions: List[str] = field(default_factory=list)  # 추천 메뉴
    coupon_applicable: bool = False  # 쿠폰 적용 가능 여부
    coupon_id: Optional[str] = None  # 적용 가능한 쿠폰 ID
    distance: Optional[float] = None  # 거리 (km)
    estimated_price: Optional[int] = None  # 예상 가격
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatbotResponse:
    """챗봇 응답 데이터"""
    text: str  # 사용자에게 보여줄 응답 텍스트
    recommendations: List[Dict] = field(default_factory=list)  # 추천 결과
    follow_up_questions: List[str] = field(default_factory=list)  # 후속 질문
    action_required: bool = False  # 추가 액션 필요 여부
    metadata: Dict[str, Any] = field(default_factory=dict)  # 메타데이터
    emotion: str = "happy"  # 캐릭터 감정 상태 (happy, excited, thinking, confused, sad)
    quick_replies: List[Dict[str, str]] = field(default_factory=list)  # Quick Reply 버튼


@dataclass
class ChatbotOutput:
    """챗봇 최종 출력"""
    response: ChatbotResponse
    extracted_info: ExtractedInfo  # 추천 시스템용 구조화 데이터
    learning_data: Dict = field(default_factory=dict)  # 개인화 학습용 데이터
    session_data: Dict = field(default_factory=dict)  # 세션 유지 데이터


@dataclass
class TrainingData:
    """학습 데이터 구조"""
    input_text: str  # 입력 텍스트
    target_intent: IntentType  # 정답 의도
    target_entities: ExtractedEntity  # 정답 엔티티
    expected_response: str  # 기대 응답
    domain: str = "naviyam"  # 도메인


@dataclass
class FoodcardUser:
    """급식카드 사용자 정보"""
    user_id: int
    card_number: str
    balance: int = 0
    status: str = "ACTIVE"  # ACTIVE, INACTIVE
    target_age_group: str = "청소년"  # 청소년, 청년
    
    def can_afford(self, price: int) -> bool:
        """가격 지불 가능 여부"""
        return self.balance >= price and self.status == "ACTIVE"
    
    def is_low_balance(self, threshold: int = 5000) -> bool:
        """잔액 부족 여부"""
        return self.balance < threshold


@dataclass
class NaviyamKnowledge:
    """나비얌 도메인 지식베이스"""
    shops: Dict[int, NaviyamShop] = field(default_factory=dict)
    menus: Dict[int, NaviyamMenu] = field(default_factory=dict)
    coupons: Dict[str, NaviyamCoupon] = field(default_factory=dict)
    foodcard_users: Dict[str, FoodcardUser] = field(default_factory=dict)
    reviews: List[Dict] = field(default_factory=list)
    popular_combinations: List[Dict] = field(default_factory=list)  # 인기 조합

    def get_good_influence_shops(self) -> List[NaviyamShop]:
        """착한가게 목록 반환"""
        return [shop for shop in self.shops.values() if shop.is_good_influence_shop]

    def get_shops_by_category(self, category: str) -> List[NaviyamShop]:
        """카테고리별 가게 목록 반환"""
        # 정확한 카테고리 매칭
        exact_matches = [shop for shop in self.shops.values() if shop.category == category]
        
        # 복합 카테고리 처리 (예: "한식/치킨"에서 "한식" 검색 시에도 포함)
        if not exact_matches:
            partial_matches = []
            for shop in self.shops.values():
                if "/" in shop.category and category in shop.category.split("/"):
                    partial_matches.append(shop)
            return partial_matches
            
        return exact_matches
    
    def get_available_categories(self) -> List[str]:
        """현재 등록된 가게들의 카테고리 목록 반환"""
        categories = set()
        for shop in self.shops.values():
            categories.add(shop.category)
        return sorted(list(categories))

    def get_menus_in_budget(self, max_budget: int) -> List[NaviyamMenu]:
        """예산 내 메뉴 목록 반환"""
        return [menu for menu in self.menus.values() if menu.price <= max_budget]
    
    def get_applicable_coupons(self, user_id: Optional[int] = None, shop_id: Optional[int] = None, 
                             category: Optional[str] = None, price: int = 0) -> List[NaviyamCoupon]:
        """사용 가능한 쿠폰 목록 반환"""
        applicable_coupons = []
        
        # 급식카드 사용자 확인
        foodcard_user = None
        if user_id and str(user_id) in self.foodcard_users:
            foodcard_user = self.foodcard_users[str(user_id)]
        
        # 가게 정보 확인
        shop = None
        if shop_id and shop_id in self.shops:
            shop = self.shops[shop_id]
            if not category:
                category = shop.category
        
        for coupon in self.coupons.values():
            # 유효기간 검사
            if not coupon.is_valid():
                continue
                
            # 최소 금액 검사
            if coupon.min_amount and price < coupon.min_amount:
                continue
            
            # 사용 대상 검사
            if coupon.usage_type == "FOODCARD" and not foodcard_user:
                continue
            
            if coupon.usage_type == "GOOD_SHOP" and (not shop or not shop.is_good_influence_shop):
                continue
                
            if coupon.usage_type == "CATEGORY" and category not in coupon.target:
                continue
                
            if coupon.usage_type == "EMERGENCY" and foodcard_user and not foodcard_user.is_low_balance():
                continue
            
            # 대상 연령 검사
            if "TEEN_FOODCARD" in coupon.target and foodcard_user and foodcard_user.target_age_group != "청소년":
                continue
                
            applicable_coupons.append(coupon)
            
        # 할인 금액 기준 정렬
        applicable_coupons.sort(key=lambda c: c.calculate_discount(price), reverse=True)
        return applicable_coupons


@dataclass
class UserState:
    """사용자 상태 정보"""
    strategy: str  # "onboarding_mode", "data_building_mode", "normal_mode"
    data_completeness: float  # 0.0 ~ 1.0
    interaction_count: int
    last_interaction: datetime = field(default_factory=datetime.now)


@dataclass
class LearningData:
    """수집된 학습 데이터"""
    user_id: str
    timestamp: datetime = field(default_factory=datetime.now)

    # 기본 추출 데이터
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    intent_confidence: float = 0.0

    # 학습용 Feature들
    food_preferences: List[str] = field(default_factory=list)
    budget_patterns: List[int] = field(default_factory=list)
    companion_patterns: List[str] = field(default_factory=list)
    taste_preferences: Dict[str, float] = field(default_factory=dict)

    # 선택/피드백 데이터
    recommendations_provided: List[Dict] = field(default_factory=list)
    user_selection: Optional[Dict] = None
    user_feedback: Optional[str] = None
    satisfaction_score: Optional[float] = None

# 전역 상수
DEFAULT_CONFIDENCE_THRESHOLD = 0.5
MAX_RESPONSE_LENGTH = 200
MAX_CONVERSATION_HISTORY = 10