"""
응답 생성기
상황별 맞춤 응답 생성 및 추천 시스템 연동
"""

import random
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, time
import logging

from src.data.data_structure import (
    ExtractedInfo, ChatbotResponse, UserProfile, NaviyamKnowledge,
    NaviyamShop, NaviyamMenu, NaviyamCoupon, IntentType, UserState, LearningData,
    Recommendation
)
from src.nlp.nlg import NaviyamNLG, ResponseTone
from src.nlp.llm_normalizer import LLMNormalizer
from src.models.koalpaca_model import KoAlpacaModel
from src.utils.tmap_utils import NaviyamTmapIntegration
from src.utils.location_utils import normalize_location, filter_shops_by_distance

logger = logging.getLogger(__name__)

class RecommendationEngine:
    """간단한 추천 엔진 (Matrix Factorization 전까지의 임시)"""

    def __init__(self, knowledge: NaviyamKnowledge):
        self.knowledge = knowledge

    def recommend_by_food_type(self, food_type: str, budget: int = None, limit: int = 3) -> List[Dict]:
        """음식 종류별 추천"""
        recommendations = []

        # 카테고리 매핑 (더 유연하게 확장)
        category_mapping = {
            '치킨': '치킨',
            '한식': '한식', '한국음식': '한식', '국밥': '한식', '김치찌개': '한식', '된장찌개': '한식',
            '중식': '중식', '중국음식': '중식', '짜장면': '중식', '짬뽕': '중식', '탕수육': '중식',
            '일식': '일식', '일본음식': '일식', '초밥': '일식', '라멘': '일식', '돈카츠': '일식',
            '피자': '양식', '햄버거': '양식', '파스타': '양식', '스테이크': '양식', '양식': '양식',
            '분식': '분식', '떡볶이': '분식', '순대': '분식', '튀김': '분식',
            '족발': '족발보쌈', '보쌈': '족발보쌈',
            '고기': '한식', '삼겹살': '한식', '갈비': '한식'
        }

        # 정확한 매칭이 없으면 부분 문자열 매칭 시도
        target_category = category_mapping.get(food_type, None)
        if not target_category:
            # 부분 문자열 매칭
            for key, value in category_mapping.items():
                if key in food_type or food_type in key:
                    target_category = value
                    break
            else:
                # 그래도 못 찾으면 원본 그대로 사용
                target_category = food_type

        # 해당 카테고리 가게 찾기
        matching_shops = [
            shop for shop in self.knowledge.shops.values()
            if target_category.lower() in shop.category.lower()
        ]

        # 착한가게 우선 정렬
        matching_shops.sort(key=lambda x: (
            -1 if x.is_good_influence_shop else 0,  # 착한가게 우선
            -1 if x.ordinary_discount else 0        # 할인 가게 우선
        ))

        for shop in matching_shops[:limit]:
            # 해당 가게의 메뉴 찾기
            shop_menus = [
                menu for menu in self.knowledge.menus.values()
                if menu.shop_id == shop.id
            ]

            # 예산에 맞는 메뉴 필터링
            if budget:
                shop_menus = [menu for menu in shop_menus if menu.price <= budget]

            if shop_menus:
                # 가장 인기있거나 저렴한 메뉴 선택
                best_menu = min(shop_menus, key=lambda x: x.price)

                recommendations.append({
                    'shop_id': shop.id,
                    'shop_name': shop.name,
                    'menu_id': best_menu.id,
                    'menu_name': best_menu.name,
                    'price': best_menu.price,
                    'category': shop.category,
                    'is_good_influence_shop': shop.is_good_influence_shop,
                    'ordinary_discount': shop.ordinary_discount,
                    'address': shop.address,
                    'current_status': getattr(shop, 'current_status', 'UNKNOWN'),
                    'owner_message': shop.owner_message
                })

        return recommendations
    
    def _filter_by_specific_request(self, shops: List, request: str) -> List:
        """세부 요청에 따른 가게 필터링"""
        request_lower = request.lower()
        filtered = []
        
        for shop in shops:
            # 가게 이름에 특정 키워드가 있는지 확인
            shop_name_lower = shop.name.lower()
            
            # 치킨 세부 요청 처리
            if '양념' in request_lower:
                if '양념' in shop_name_lower or '간장' in shop_name_lower or '달콤' in shop_name_lower:
                    filtered.append(shop)
            elif '후라이드' in request_lower:
                if '후라이' in shop_name_lower or '프라이드' in shop_name_lower or '오리지널' in shop_name_lower:
                    filtered.append(shop)
            elif '매운' in request_lower or '매운맛' in request_lower:
                if '매운' in shop_name_lower or '핫' in shop_name_lower or '스파이시' in shop_name_lower:
                    filtered.append(shop)
            elif '순한' in request_lower:
                if '순한' in shop_name_lower or '마일드' in shop_name_lower:
                    filtered.append(shop)
            else:
                # 기타 키워드가 가게 이름에 포함되어 있는지 확인
                if request_lower in shop_name_lower:
                    filtered.append(shop)
        
        # 필터링 결과가 없으면 메뉴에서도 찾아보기
        if not filtered:
            for shop in shops:
                shop_menus = [menu for menu in self.knowledge.menus.values() if menu.shop_id == shop.id]
                for menu in shop_menus:
                    menu_name_lower = menu.name.lower()
                    if request_lower in menu_name_lower:
                        filtered.append(shop)
                        break
        
        return filtered

    def recommend_by_budget(self, budget: int, food_type: str = None, limit: int = 3) -> List[Dict]:
        """예산별 추천"""
        recommendations = []

        # 예산 내 메뉴 찾기
        affordable_menus = [
            menu for menu in self.knowledge.menus.values()
            if menu.price <= budget
        ]

        # 음식 종류 필터링
        if food_type:
            category_mapping = {
                '치킨': '치킨',
                '한식': '한식',
                '중식': '중식',
                '일식': '일식'
            }
            target_category = category_mapping.get(food_type, food_type)

            filtered_menus = []
            for menu in affordable_menus:
                shop = self.knowledge.shops.get(menu.shop_id)
                if shop and target_category.lower() in shop.category.lower():
                    filtered_menus.append(menu)
            affordable_menus = filtered_menus

        # 가격 대비 가치 정렬 (가격 낮은 순, 착한가게 우선)
        menu_recommendations = []

        for menu in affordable_menus:
            shop = self.knowledge.shops.get(menu.shop_id)
            if shop:
                score = budget - menu.price  # 남은 예산이 높을수록 좋음
                if shop.is_good_influence_shop:
                    score += 1000  # 착한가게 보너스
                if shop.ordinary_discount:
                    score += 500   # 할인 가게 보너스

                menu_recommendations.append((score, menu, shop))

        # 점수 순 정렬
        menu_recommendations.sort(key=lambda x: x[0], reverse=True)

        for score, menu, shop in menu_recommendations[:limit]:
            recommendations.append({
                'shop_id': shop.id,
                'shop_name': shop.name,
                'menu_id': menu.id,
                'menu_name': menu.name,
                'price': menu.price,
                'category': shop.category,
                'is_good_influence_shop': shop.is_good_influence_shop,
                'ordinary_discount': shop.ordinary_discount,
                'budget_remaining': budget - menu.price,
                'value_score': score
            })

        return recommendations

    def recommend_coupons(self, budget: int = None, shop_id: int = None, limit: int = 3) -> List[Dict]:
        """쿠폰 추천"""
        available_coupons = []

        for coupon in self.knowledge.coupons.values():
            # 예산 조건 확인
            if budget and coupon.min_amount and budget < coupon.min_amount:
                continue

            # 가게 제한 확인
            if shop_id and coupon.applicable_shops and shop_id not in coupon.applicable_shops:
                continue

            available_coupons.append({
                'coupon_id': coupon.id,
                'name': coupon.name,
                'description': coupon.description,
                'amount': coupon.amount,
                'min_amount': coupon.min_amount,
                'usage_type': coupon.usage_type,
                'target': coupon.target
            })

        # 할인 금액 순 정렬
        available_coupons.sort(key=lambda x: x['amount'], reverse=True)

        return available_coupons[:limit]

    def _format_recommendation_with_shop(self, recommendation: Dict) -> str:
        """가게+메뉴 조합으로 추천 포맷"""
        shop_name = recommendation.get('shop_name', '알 수 없는 가게')
        menu_name = recommendation.get('menu_name', '추천 메뉴')
        price = recommendation.get('price', 0)
        
        # 가게 + 메뉴 명확한 형식
        if price > 0:
            return f"🏪 {shop_name}의 '{menu_name}' ({price:,}원)"
        else:
            return f"🏪 {shop_name}의 '{menu_name}'"


class NaviyamResponseGenerator:
    """나비얌 응답 생성기"""

    def __init__(self, knowledge: NaviyamKnowledge, nlg: NaviyamNLG, model: KoAlpacaModel = None, foodcard_manager=None):
        """
        Args:
            knowledge: 나비얌 지식베이스
            nlg: 자연어 생성기
            model: 언어 모델 (선택사항)
            foodcard_manager: 급식카드 관리자 (선택사항)
        """
        self.knowledge = knowledge
        self.nlg = nlg
        self.model = model
        self.foodcard_manager = foodcard_manager
        self.recommendation_engine = RecommendationEngine(knowledge)

        self.llm_normalizer = LLMNormalizer(model) if model else None
        
        # T맵 연동 초기화
        self.tmap_integration = NaviyamTmapIntegration()

        # 응답 생성 통계
        self.generation_stats = {
            "total_responses": 0,
            "template_responses": 0,
            "model_responses": 0,
            "llm_child_responses": 0,  # 오타 수정: llem -> llm
            "llm_failed_responses": 0,  # LLM 실패 횟수 추가
            "llm_retry_successes": 0,   # 재시도 성공 횟수 추가
            "fallback_responses": 0
        }
    
    def ensure_polite_tone(self, text: str) -> str:
        """모든 응답을 존댓말로 통일"""
        # 반말 표현을 존댓말로 변환
        replacements = {
            "이해해!": "이해해요.",
            "어때?": "어떠세요?", 
            "알려줘": "알려주세요",
            "먹어봐": "드셔보세요",
            "그런 기분 이해해!": "그런 기분 이해해요.",
            "어때요? ": "어떠세요? ",
            "별루라니": "별로시군요",
            "싫은데": "싫으신가 봐요",
            "좋아하시는군요!": "좋아하시는군요.",
            "좋은 선택이에요!": "좋은 선택이세요!",
            "같은 곳 어떠세요?": "같은 곳은 어떠세요?",
            # LLM이 자주 생성하는 반말 패턴
            "하자!": "하세요!",
            "가보자!": "가보세요!",
            "먹자!": "드세요!",
            "어때요~": "어떠세요?",
            "말해줘~": "말씀해 주세요.",
            "해봐~": "해보세요."
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
            
        # 문장 끝에 경어체 확인
        if text.endswith("!") and not text.endswith("세요!") and not text.endswith("어요!"):
            # 과도한 감탄사를 부드러운 마무리로
            text = text[:-1] + "."
            
        return text

    def generate_response(
        self,
        extracted_info: ExtractedInfo,
        user_profile: UserProfile = None,
        conversation_context: List[Dict] = None,
        rag_context: str = ""
    ) -> ChatbotResponse:
        """메인 응답 생성 메서드 (LLM 우선 전략)"""

        try:
            self.generation_stats["total_responses"] += 1

            # 1. 모든 의도에 대해 추천 데이터 생성 시도 (일반 대화 포함)
            recommendations = self._get_recommendations(extracted_info, user_profile, rag_context)
            
            # 2. LLM 우선 응답 생성 시도 (재시도 로직 포함)
            if self.model and self.llm_normalizer and self.llm_normalizer.should_use_llm_response(extracted_info, conversation_context):
                max_retries = 2  # 최대 2번 재시도
                
                for attempt in range(max_retries + 1):  # 0, 1, 2 (총 3번 시도)
                    try:
                        if attempt == 0:
                            logger.info(f"🚀 LLM 응답 생성 시도: intent={extracted_info.intent.value}, text='{extracted_info.raw_text}'")
                        else:
                            logger.info(f"🔄 LLM 응답 재시도 {attempt}/{max_retries}")
                        
                        # 재시도시 약간 다른 파라미터 사용
                        temperature = 0.5 if attempt == 0 else 0.7 + (attempt * 0.1)
                        
                        llm_response = self._generate_model_response(
                            extracted_info, recommendations, conversation_context, user_profile, temperature=temperature
                        )
                        
                        # LLM 응답이 유효하면 사용 (더 관대한 조건)
                        if llm_response and len(llm_response.text.strip()) > 5:  # 20자 → 5자로 완화
                            logger.info(f"✅ LLM 응답 생성 성공 (시도 {attempt + 1}회): {len(llm_response.text)}자")
                            self.generation_stats["llm_child_responses"] += 1
                            # 재시도 성공 표시
                            if attempt > 0:
                                llm_response.metadata["retry_success"] = True
                                llm_response.metadata["retry_count"] = attempt
                                self.generation_stats["llm_retry_successes"] += 1
                            return llm_response
                        else:
                            logger.warning(f"❌ LLM 응답이 너무 짧음 (시도 {attempt + 1}회): '{llm_response.text if llm_response else 'None'}'")
                            
                    except Exception as e:
                        logger.warning(f"❌ LLM 응답 생성 실패 (시도 {attempt + 1}회): {e}")
                        # 마지막 시도가 아니면 계속 진행
                        if attempt < max_retries:
                            continue
                
                logger.warning(f"❌ LLM 응답 생성 최종 실패 ({max_retries + 1}회 시도 완료)")
                self.generation_stats["llm_failed_responses"] = self.generation_stats.get("llm_failed_responses", 0) + 1
            
            # 3. LLM 실패시 또는 사용하지 않는 경우 템플릿 사용
            logger.info(f"템플릿 응답 생성: intent={extracted_info.intent.value}")
            
            # 거부가 많으면 다른 카테고리 추천
            rejection_count = self._count_rejections(conversation_context)
            if rejection_count >= 2:
                recommendations = self._get_alternative_recommendations(extracted_info, user_profile, conversation_context)

            # 응답 생성
            response = self._generate_contextual_response(
                extracted_info, recommendations, user_profile, conversation_context
            )

            # 후처리
            response = self._post_process_response(response, extracted_info, user_profile)
            return response

        except Exception as e:
            logger.error(f"응답 생성 실패: {e}")
            return self._generate_fallback_response(extracted_info)

    def _get_recommendations(self, extracted_info: ExtractedInfo, user_profile: UserProfile = None, rag_context: str = "") -> List[Dict]:
        """의도별 추천 데이터 생성 (일반 대화 포함 강화 버전)"""

        intent = extracted_info.intent
        entities = extracted_info.entities
        raw_text = extracted_info.raw_text.lower()

        recommendations = []

        # **핵심 개선: 일반 대화에서도 음식 관련 키워드 감지시 추천 생성**
        food_related_keywords = ["뭐먹", "먹고싶", "드시고싶", "추천", "맛집", "음식", "저녁", "점심", "아침", 
                                "배고프", "허기", "식사", "좋은", "맛있는", "괜찮은"]
        is_food_related = any(keyword in raw_text for keyword in food_related_keywords)

        if intent == IntentType.GENERAL_CHAT and is_food_related:
            logger.info(f"일반 대화에서 음식 관련 키워드 감지: '{extracted_info.raw_text}'")
            # 일반 대화이지만 음식 관련이면 추천 생성
            intent = IntentType.FOOD_REQUEST  # 임시로 음식 요청으로 처리

        if intent == IntentType.FOOD_REQUEST:
            # 음식 추천
            food_type = entities.food_type if entities else None
            
            # 위치 정보 요청 감지
            needs_location = any(word in extracted_info.raw_text.lower() 
                                for word in ["어디", "가게", "위치", "주소"])
            budget = entities.budget if entities else None

            # 사용자 프로필 활용
            if not food_type and user_profile and hasattr(user_profile, 'preferred_categories'):
                if user_profile.preferred_categories and len(user_profile.preferred_categories) > 0:
                    food_type = user_profile.preferred_categories[0]

            if not budget and user_profile and user_profile.average_budget:
                budget = user_profile.average_budget

            if food_type:
                recommendations = self.recommendation_engine.recommend_by_food_type(
                    food_type, budget, limit=3
                )
            else:
                # 일반 추천 - 항상 추천 제공
                # 인기 카테고리 순회
                popular_categories = ['치킨', '피자', '한식', '중식', '분식']
                import random
                selected_category = random.choice(popular_categories)
                
                # 선택된 카테고리로 추천
                recommendations = self.recommendation_engine.recommend_by_food_type(
                    selected_category, budget, limit=3
                )
                
                # 그래도 없으면 착한가게 추천
                good_shops = [shop for shop in self.knowledge.shops.values() if shop.is_good_influence_shop]
                for shop in good_shops[:3]:
                    shop_menus = [menu for menu in self.knowledge.menus.values() if menu.shop_id == shop.id]
                    if shop_menus:
                        best_menu = min(shop_menus, key=lambda x: x.price)
                        recommendations.append({
                            'shop_id': shop.id,
                            'shop_name': shop.name,
                            'menu_name': best_menu.name,
                            'price': best_menu.price,
                            'is_good_influence_shop': True
                        })

        elif intent == IntentType.BUDGET_INQUIRY:
            # 예산별 추천
            budget = entities.budget if entities else None
            food_type = entities.food_type if entities else None

            if budget:
                recommendations = self.recommendation_engine.recommend_by_budget(
                    budget, food_type, limit=3
                )

        elif intent == IntentType.COUPON_INQUIRY:
            # 쿠폰 추천
            budget = entities.budget if entities else None
            recommendations = self.recommendation_engine.recommend_coupons(
                budget, limit=3
            )

        elif intent == IntentType.TIME_INQUIRY:
            # 현재 운영중인 가게 추천
            current_time = datetime.now().time()
            open_shops = []

            for shop in self.knowledge.shops.values():
                if self._is_shop_open(shop, current_time):
                    shop_menus = [menu for menu in self.knowledge.menus.values() if menu.shop_id == shop.id]
                    if shop_menus:
                        best_menu = min(shop_menus, key=lambda x: x.price)
                        open_shops.append({
                            'shop_id': shop.id,
                            'shop_name': shop.name,
                            'menu_name': best_menu.name,
                            'price': best_menu.price,
                            'current_status': 'OPEN',
                            'close_hour': shop.close_hour
                        })

            recommendations = open_shops[:3]

        elif intent == IntentType.LOCATION_INQUIRY:
            # 근처 가게 추천 (실제로는 GPS 연동 필요)
            nearby_shops = list(self.knowledge.shops.values())[:3]
            for shop in nearby_shops:
                shop_menus = [menu for menu in self.knowledge.menus.values() if menu.shop_id == shop.id]
                if shop_menus:
                    best_menu = min(shop_menus, key=lambda x: x.price)
                    recommendations.append({
                        'shop_id': shop.id,
                        'shop_name': shop.name,
                        'menu_name': best_menu.name,
                        'price': best_menu.price,
                        'address': shop.address,
                        'distance': '도보 5분'  # 임시 데이터
                    })
        
        elif intent == IntentType.BALANCE_CHECK:
            # 급식카드 잔액 확인
            if self.foodcard_manager:
                # 임시로 user_id를 1로 설정 (실제로는 user_profile에서 가져와야 함)
                user_id = 1
                if user_profile and hasattr(user_profile, 'user_id'):
                    try:
                        user_id = int(user_profile.user_id)
                    except:
                        user_id = 1
                        
                balance = self.foodcard_manager.check_balance(user_id)
                if balance is not None:
                    recommendations.append({
                        'type': 'balance_info',
                        'balance': balance,
                        'user_id': user_id,
                        'low_balance': balance < 5000,
                        'emergency_coupon_eligible': balance < 3000
                    })
        
        elif intent == IntentType.BALANCE_CHARGE:
            # 급식카드 충전 안내
            if self.foodcard_manager:
                user_id = 1
                if user_profile and hasattr(user_profile, 'user_id'):
                    try:
                        user_id = int(user_profile.user_id)
                    except:
                        user_id = 1
                        
                # 현재 잔액 확인만 제공
                current_balance = self.foodcard_manager.check_balance(user_id)
                
                recommendations.append({
                    'type': 'balance_info',
                    'current_balance': current_balance,
                    'message': f"현재 급식카드 잔액: {current_balance:,}원" if current_balance else "급식카드가 등록되지 않았습니다."
                })

        # RAG 컨텍스트로 추천 결과 보강
        if rag_context and rag_context.strip():
            logger.info(f"RAG 컨텍스트로 추천 결과 보강 (기본 추천: {len(recommendations)}개)")
            recommendations = self._enrich_recommendations_with_rag(recommendations, rag_context)
            logger.info(f"RAG 보강 후 최종 추천: {len(recommendations)}개")

        return recommendations

    def _is_shop_open(self, shop: NaviyamShop, current_time: time) -> bool:
        """가게 운영시간 확인"""
        try:
            if not shop.open_hour or not shop.close_hour:
                return True  # 시간 정보 없으면 열린 것으로 가정

            open_time = time.fromisoformat(shop.open_hour + ":00") if ":" not in shop.open_hour else time.fromisoformat(shop.open_hour)
            close_time = time.fromisoformat(shop.close_hour + ":00") if ":" not in shop.close_hour else time.fromisoformat(shop.close_hour)

            # 브레이크타임 확인
            if shop.break_start_hour and shop.break_end_hour:
                break_start = time.fromisoformat(shop.break_start_hour + ":00") if ":" not in shop.break_start_hour else time.fromisoformat(shop.break_start_hour)
                break_end = time.fromisoformat(shop.break_end_hour + ":00") if ":" not in shop.break_end_hour else time.fromisoformat(shop.break_end_hour)

                if break_start <= current_time <= break_end:
                    return False  # 브레이크타임

            # 운영시간 확인
            if close_time < open_time:  # 자정 넘어가는 경우
                return current_time >= open_time or current_time <= close_time
            else:
                return open_time <= current_time <= close_time

        except Exception as e:
            logger.warning(f"운영시간 확인 실패 ({shop.name}): {e}")
            return True

    def _handle_general_chat(self, extracted_info: ExtractedInfo, user_profile: UserProfile = None) -> ChatbotResponse:
        """일반 대화 처리"""
        
        # 간단한 인사말 목록
        greetings = ["안녕", "하이", "헬로", "반가워", "hi", "hello"]
        
        # 사용자의 메시지가 인사말 중 하나인지 확인
        if any(greet in extracted_info.raw_text.lower() for greet in greetings):
            # 사용자 프로필이 있으면 이름을 넣어 개인화된 인사
            if user_profile and user_profile.user_id != "default_user":
                response_text = "안녕하세요! 무엇을 도와드릴까요?"
            else:
                response_text = "안녕하세요! 맛있는 음식 찾아드릴게요!"
        else:
            # 기타 일반 대화는 간단한 응답
            response_text = "네, 말씀하세요. 듣고 있어요."

        return ChatbotResponse(
            text=response_text,
            recommendations=[],
            follow_up_questions=["어떤 음식을 추천해드릴까요?", "오늘 뭐 먹을지 고민되세요?"],
            action_required=False,
            metadata={"generation_method": "general_chat_handler"}
        )

    def _generate_contextual_response(
            self,
            extracted_info: ExtractedInfo,
            recommendations: List[Dict],
            user_profile: UserProfile = None,
            conversation_context: List[Dict] = None
    ) -> ChatbotResponse:
        """맥락을 고려한 응답 생성"""

        # 1. 최우선: 일반 대화 처리
        if extracted_info.intent == IntentType.GENERAL_CHAT:
            return self._handle_general_chat(extracted_info, user_profile)

        # 2. 사용자 상태 판별 - 항상 normal mode
        user_strategy = "normal_mode"
        
        # 3. 추천이 있으면 바로 템플릿 응답
        if recommendations and len(recommendations) > 0:
            return self._generate_template_response(extracted_info, recommendations, user_profile)
        
        # 3.5 일반 모드 응답 생성
        if True:  # 항상 일반 모드
            # 일반 모드 - 조건부 LLM 사용
            use_llm_response = (
                    self.llm_normalizer and
                    self.llm_normalizer.should_use_llm_response(extracted_info, conversation_context)
            )

            if use_llm_response:
                return self._generate_model_response(extracted_info, recommendations, conversation_context)
            else:
                return self._generate_template_response(extracted_info, recommendations, user_profile)
        # else:
        #     # 기존 로직 (언어 모델 사용 여부 결정)
        #     use_model = (
        #             self.model is not None and
        #             extracted_info.confidence < 0.99 and
        #             len(extracted_info.raw_text) > 2
        #     )
        #
        #     if use_model:
        #         return self._generate_model_response(extracted_info, recommendations, conversation_context)
        #     else:
        #         return self._generate_template_response(extracted_info, recommendations, user_profile)

    def _generate_template_response(
        self,
        extracted_info: ExtractedInfo,
        recommendations: List[Dict],
        user_profile: UserProfile = None
    ) -> ChatbotResponse:
        """템플릿 기반 응답 생성 (개선 버전)"""

        self.generation_stats["template_responses"] += 1

        # 추천이 있으면 바로 보여주기
        if recommendations:
            # 추천 텍스트 생성
            rec_texts = []
            for i, rec in enumerate(recommendations[:3], 1):
                shop_name = rec.get('shop_name', '')
                menu_name = rec.get('menu_name', '')
                price = rec.get('price', 0)
                category = rec.get('category', '')
                address = rec.get('address', '')
                
                if shop_name and menu_name:
                    text = f"{i}. 🏪 {shop_name}"
                    if category:
                        text += f" ({category})"
                    text += f"\n   📍 {address}" if address else ""
                    text += f"\n   🍽️ {menu_name} - {price:,}원"
                    if rec.get('is_good_influence_shop'):
                        text += " ⭐착한가게"
                    rec_texts.append(text)
            
            if rec_texts:
                response_text = "맛있는 곳 추천해드릴게요!\n\n" + "\n\n".join(rec_texts)
                
                # 추가 안내
                if extracted_info.entities and extracted_info.entities.budget:
                    response_text += f"\n\n💰 {extracted_info.entities.budget}원 예산에 맞춰 추천드렸어요!"
                
                return ChatbotResponse(
                    text=response_text,
                    recommendations=recommendations,
                    follow_up_questions=["다른 추천도 보시겠어요?", "더 자세한 정보가 필요하신가요?"],
                    action_required=False,
                    metadata={"generation_method": "template_with_recommendations"}
                )
        
        # 추천이 없는 경우만 기존 NLG 사용
        entities_dict = {
            'food_type': extracted_info.entities.food_type if extracted_info.entities else None,
            'budget': extracted_info.entities.budget if extracted_info.entities else None,
            'raw_text': extracted_info.raw_text
        }

        response = self.nlg.generate_response(
            intent=extracted_info.intent,
            entities=entities_dict,
            recommendations=recommendations,
            user_profile=user_profile
        )

        return response
    def _generate_model_response(
            self,
            extracted_info: ExtractedInfo,
            recommendations: List[Dict],
            conversation_context: List[Dict] = None,
            user_profile: UserProfile = None,
            temperature: float = 0.5
    ) -> ChatbotResponse:
        """아동 친화적 LLM 응답 생성"""

        if not self.llm_normalizer:
            # LLM 없으면 템플릿으로 폴백
            return self._generate_template_response(extracted_info, recommendations)

        try:
            # 아동 친화적 응답 생성
            llm_response_text = self.llm_normalizer.generate_child_friendly_response(
                extracted_info, recommendations, conversation_context, user_profile, temperature=temperature
            )

            if llm_response_text and len(llm_response_text.strip()) > 10:
                self.generation_stats["llm_child_responses"] += 1
                # 존댓말 통일 처리
                llm_response_text = self.ensure_polite_tone(llm_response_text)

                return ChatbotResponse(
                    text=llm_response_text,
                    recommendations=recommendations,
                    follow_up_questions=self._generate_follow_up_questions(
                        extracted_info.intent, extracted_info.entities.__dict__ if extracted_info.entities else {}, recommendations
                    ),
                    action_required=len(recommendations) > 0,
                    metadata={
                        "generation_method": "llm_child_friendly",
                        "llm_confidence": 0.8,
                        "response_length": len(llm_response_text)
                    }
                )
            else:
                # LLM 응답이 부족하면 템플릿으로 폴백
                return self._generate_template_response(extracted_info, recommendations)

        except Exception as e:
            logger.error(f"LLM 아동 친화적 응답 생성 실패: {e}")
            # 에러시 템플릿으로 폴백
            return self._generate_template_response(extracted_info, recommendations)
    # def _generate_model_response(
    #     self,
    #     extracted_info: ExtractedInfo,
    #     recommendations: List[Dict],
    #     conversation_context: List[Dict] = None
    # ) -> ChatbotResponse:
    #     """언어 모델 기반 응답 생성"""
    #
    #     self.generation_stats["model_responses"] += 1
    #
    #     try:
    #         # 프롬프트 구성
    #         prompt = self._build_model_prompt(extracted_info, recommendations, conversation_context)
    #
    #         # 모델 생성
    #         generation_result = self.model.generate_text(
    #             prompt=prompt,
    #             max_new_tokens=150,
    #             temperature=0.7,
    #             stop_words=["사용자:", "User:", "###"]
    #         )
    #
    #         generated_text = generation_result.get("text", "")
    #
    #         # 후처리
    #         cleaned_response = self._clean_model_response(generated_text)
    #
    #         return ChatbotResponse(
    #             text=cleaned_response,
    #             recommendations=recommendations,
    #             follow_up_questions=self._extract_follow_up_from_model(generated_text),
    #             action_required=len(recommendations) > 0,
    #             metadata={
    #                 "generation_method": "model",
    #                 "model_confidence": generation_result.get("tokens_per_second", 0),
    #                 "tokens_generated": generation_result.get("tokens_generated", 0)
    #             }
    #         )
    #
    #     except Exception as e:
    #         logger.error(f"모델 기반 응답 생성 실패: {e}")
    #         # 템플릿 기반으로 폴백
    #         return self._generate_template_response(extracted_info, recommendations)

    def _build_model_prompt(
        self,
        extracted_info: ExtractedInfo,
        recommendations: List[Dict],
        conversation_context: List[Dict] = None
    ) -> str:
        """모델용 프롬프트 구성"""

        prompt_parts = [
            "당신은 아동을 위한 착한가게 추천 AI입니다.",
            "친근하고 자연스러운 톤으로 음식을 추천해주세요.",
            ""
        ]

        # 대화 맥락 추가
        if conversation_context:
            prompt_parts.append("이전 대화:")
            for ctx in conversation_context[-2:]:  # 최근 2개만
                prompt_parts.append(f"사용자: {ctx.get('user_input', '')}")
                prompt_parts.append(f"AI: {ctx.get('bot_response', '')}")
            prompt_parts.append("")

        # 현재 사용자 입력
        prompt_parts.append(f"사용자: {extracted_info.raw_text}")

        # 추천 정보 추가
        if recommendations:
            prompt_parts.append("\n추천 가능한 가게들:")
            for i, rec in enumerate(recommendations[:3]):
                shop_info = f"{i+1}. {rec.get('shop_name', '')} - {rec.get('menu_name', '')} ({rec.get('price', 0)}원)"
                if rec.get('is_good_influence_shop'):
                    shop_info += " [착한가게]"
                prompt_parts.append(shop_info)

        prompt_parts.append("\nAI:")

        return "\n".join(prompt_parts)

    def _clean_model_response(self, response: str) -> str:
        """모델 응답 정제"""
        # 불필요한 부분 제거
        response = response.strip()

        # 정지 단어 이후 제거
        stop_indicators = ["사용자:", "User:", "###", "\n\n"]
        for stop in stop_indicators:
            if stop in response:
                response = response.split(stop)[0].strip()

        # 너무 짧거나 긴 응답 처리
        if len(response) < 10:
            return "죄송해요, 다시 말씀해주시겠어요?"
        elif len(response) > 200:
            sentences = response.split('.')
            response = '. '.join(sentences[:2]) + '.'

        return response

    def _extract_follow_up_from_model(self, response: str) -> List[str]:
        """모델 응답에서 후속 질문 추출"""
        follow_ups = []

        # 질문 패턴 찾기
        question_patterns = ['?', '어떠세요', '어떻게', '어디']
        sentences = response.split('.')

        for sentence in sentences:
            if any(pattern in sentence for pattern in question_patterns):
                cleaned = sentence.strip()
                if cleaned and len(cleaned) > 5:
                    follow_ups.append(cleaned)

        return follow_ups[:2]  # 최대 2개

    def _generate_fallback_response(self, extracted_info: ExtractedInfo) -> ChatbotResponse:
        """폴백 응답 생성"""

        self.generation_stats["fallback_responses"] += 1

        fallback_messages = [
            "죄송해요! 잘 이해하지 못했어요. 다시 말씀해주시겠어요?",
            "음.. 무슨 말씀인지 잘 모르겠어요. 음식 관련해서 도와드릴까요?",
            "헷갈리네요! 간단하게 말씀해주시면 더 잘 도와드릴 수 있어요!",
            "이해하기 어려워요 ㅠㅠ 예를 들어 '치킨 추천해줘' 이런 식으로 말씀해주세요!"
        ]

        return ChatbotResponse(
            text=random.choice(fallback_messages),
            recommendations=[],
            follow_up_questions=[
                "어떤 음식이 드시고 싶으세요?",
                "예산은 얼마나 생각하고 계세요?"
            ],
            action_required=False,
            metadata={"generation_method": "fallback"}
        )

    def _post_process_response(
        self,
        response: ChatbotResponse,
        extracted_info: ExtractedInfo,
        user_profile: UserProfile = None
    ) -> ChatbotResponse:
        """응답 후처리"""

        # 1. 길이 조정
        if len(response.text) > 200:
            sentences = response.text.split('.')
            response.text = '. '.join(sentences[:2]) + '.'

        # 2. 이모티콘 추가 (확률적)
        if random.random() < 0.3:  # 30% 확률
            emoticons = []
            if not any(emote in response.text for emote in emoticons):
                response.text += f" {random.choice(emoticons)}"

        # 3. 응답 품질 검증
        if len(response.text.strip()) == 0:
            response.text = "죄송해요, 다시 말씀해주시겠어요?"

        # 4. 메타데이터 추가
        response.metadata.update({
            "post_processed": True,
            "original_intent": extracted_info.intent.value,
            "confidence": extracted_info.confidence,
            "has_recommendations": len(response.recommendations) > 0
        })

        return response

    def handle_specific_scenarios(self, extracted_info: ExtractedInfo) -> Optional[ChatbotResponse]:
        """특정 시나리오 처리"""

        intent = extracted_info.intent
        entities = extracted_info.entities

        # 긴급 상황 처리
        if intent == IntentType.TIME_INQUIRY:
            current_hour = datetime.now().hour
            if current_hour < 6 or current_hour > 23:
                return ChatbotResponse(
                    text="지금은 대부분 가게가 문 닫은 시간이에요 ㅠㅠ 편의점이나 24시간 가게를 찾아보시는 건 어떨까요?",
                    recommendations=[],
                    follow_up_questions=["24시간 편의점 찾아드릴까요?"],
                    action_required=False
                )

        # 예산 부족 상황
        if intent == IntentType.BUDGET_INQUIRY and entities and entities.budget:
            if entities.budget < 3000:
                return ChatbotResponse(
                    text=f"{entities.budget}원은 조금 부족할 것 같아요 ㅠㅠ 편의점 도시락이나 간단한 분식은 어떠세요?",
                    recommendations=[],
                    follow_up_questions=["예산을 조금 더 올려주실 수 있나요?"],
                    action_required=False
                )

        # 반복 질문 감지 (같은 의도 연속 3회)
        # TODO: 대화 히스토리 기반으로 구현

        return None

    def get_generation_statistics(self) -> Dict[str, Any]:
        """응답 생성 통계"""
        total = self.generation_stats["total_responses"]

        if total == 0:
            return self.generation_stats.copy()

        stats = self.generation_stats.copy()
        stats.update({
            "template_response_rate": stats["template_responses"] / total,
            "model_response_rate": stats["model_responses"] / total,
            "llm_child_response_rate": stats["llm_child_responses"] / total,
            "llm_failed_response_rate": stats.get("llm_failed_responses", 0) / total,  # 새로 추가
            "llm_retry_success_rate": stats.get("llm_retry_successes", 0) / max(stats.get("llm_failed_responses", 1), 1),  # 새로 추가
            "actual_llm_usage_rate": (stats["llm_child_responses"] + stats.get("llm_failed_responses", 0)) / total,  # 실제 LLM 시도율
            "fallback_response_rate": stats["fallback_responses"] / total,
            "knowledge_base_utilization": {
                "total_shops": len(self.knowledge.shops),
                "total_menus": len(self.knowledge.menus),
                "total_coupons": len(self.knowledge.coupons)
            }
        })
        # stats.update({
        #     "template_response_rate": stats["template_responses"] / total,
        #     "model_response_rate": stats["model_responses"] / total,
        #     "fallback_response_rate": stats["fallback_responses"] / total,
        #     "knowledge_base_utilization": {
        #         "total_shops": len(self.knowledge.shops),
        #         "total_menus": len(self.knowledge.menus),
        #         "total_coupons": len(self.knowledge.coupons)
        #     }
        # })

        return stats

    def reset_statistics(self):
        """통계 초기화"""
        self.generation_stats = {
            "total_responses": 0,
            "template_responses": 0,
            "model_responses": 0,
            "llm_child_responses": 0,
            "llm_failed_responses": 0,
            "llm_retry_successes": 0,
            "fallback_responses": 0
        }

    def _count_rejections(self, conversation_context: List[Dict]) -> int:
        """대화 컨텍스트에서 거부 횟수 계산"""
        if not conversation_context:
            return 0
        
        rejection_words = ["별로", "싫어", "아니", "다른", "말고", "그거 말고", "다른 거", "싫다"]
        count = 0
        
        # 최근 5개 메시지만 확인
        for msg in conversation_context[-5:]:
            user_msg = msg.get('user_message', '').lower()
            if any(word in user_msg for word in rejection_words):
                count += 1
        
        return count
    
    def _get_alternative_recommendations(self, extracted_info: ExtractedInfo, user_profile: UserProfile, conversation_context: List[Dict]) -> List[Dict]:
        """거부가 많을 때 대체 추천 생성"""
        # 이미 추천한 카테고리 수집
        recommended_categories = set()
        for msg in conversation_context:
            bot_msg = msg.get('bot_message', '')
            # 간단한 패턴 매칭으로 추천된 카테고리 추출
            categories = ['치킨', '피자', '한식', '중식', '일식', '분식', '양식', '브런치', '카페', '디저트']
            for cat in categories:
                if cat in bot_msg:
                    recommended_categories.add(cat)
        
        # 아직 추천하지 않은 카테고리에서 선택
        all_categories = ['치킨', '피자', '한식', '중식', '일식', '분식', '양식', '브런치', '카페', '디저트', '패스트푸드', '샐러드', '김밥', '떡볶이']
        remaining_categories = [cat for cat in all_categories if cat not in recommended_categories]
        
        # 무작위로 3개 선택
        selected_categories = random.sample(remaining_categories, min(3, len(remaining_categories)))
        
        # 각 카테고리에 대한 추천 생성
        recommendations = []
        for category in selected_categories:
            shops = [s for s in self.knowledge.shops.values() if category in s.category]
            if shops:
                shop = random.choice(shops)
                shop_menus = [menu for menu in self.knowledge.menus.values() if menu.shop_id == shop.id]
                if shop_menus:
                    best_menu = min(shop_menus, key=lambda x: x.price)
                    recommendations.append({
                        'shop_id': shop.id,
                        'shop_name': shop.name,
                        'menu_name': best_menu.name,
                        'price': best_menu.price,
                        'category': shop.category,
                        'reason': f"다른 카테고리로 추천드려요",
                        'is_alternative': True
                    })
        
        return recommendations


    def _determine_user_strategy(self, user_profile: UserProfile) -> str:
        """사용자 전략 결정 (덜 적극적)"""
        # 기본적으로 normal_mode 사용
        if not user_profile or user_profile.interaction_count < 1:
            return "onboarding_mode"
        else:
            return "normal_mode"  # 데이터 수집 모드 비활성화

    def _generate_onboarding_response(
            self,
            extracted_info: ExtractedInfo,
            recommendations: List[Dict]
    ) -> ChatbotResponse:
        """신규 유저 온보딩 응답"""

        entities = extracted_info.entities
        # 기본 정보 수집 질문들
        if not extracted_info.entities or not extracted_info.entities.food_type:
            return ChatbotResponse(
                text="안녕하세요! 오늘 어떤 음식을 도와드릴까요?",
                recommendations=recommendations,
                follow_up_questions=[],
                action_required=True
            )

        elif not extracted_info.entities.budget:
            return ChatbotResponse(
                text=f"{extracted_info.entities.food_type} 좋네요! 예산은 얼마 정도 생각하고 계시나요?",
                recommendations=recommendations,
                follow_up_questions=[],
                action_required=True
            )

        elif not extracted_info.entities.companions:
            return ChatbotResponse(
                text="누구와 함께 드실 예정인가요?",
                recommendations=recommendations,
                follow_up_questions=[],
                action_required=True
            )

        else:
            # 충분한 정보가 모였으면 정상 모드로 전환 (새로 추가)
            budget_text = f"{extracted_info.entities.budget}원" if extracted_info.entities.budget else "예산 내"
            return ChatbotResponse(
                text=f"{extracted_info.entities.food_type} {budget_text} 예산으로 찾아드릴게요! 추천해드려요!",
                recommendations=recommendations,
                action_required=False,
                metadata={
                    "switch_to_normal_mode": True,  # 🔥 모드 전환 신호
                    "onboarding_complete": True
                }
            )

    def _generate_data_collection_response(
            self,
            extracted_info: ExtractedInfo,
            recommendations: List[Dict],
            user_profile: UserProfile
    ) -> ChatbotResponse:
        """데이터 수집 모드 응답"""

        # 부족한 정보 파악
        missing_data = []

        if not user_profile.taste_preferences:
            missing_data.append("taste")
        if not user_profile.companion_patterns:
            missing_data.append("companions")
        if not user_profile.location_preferences:
            missing_data.append("location")

        entities = extracted_info.entities
        raw_text = extracted_info.raw_text.lower()
        
        # 맛 선호도 패턴 매칭 (더 유연하게)
        taste_patterns = {
            "mild": ["순한", "안매운", "매운거안좋아", "순한걸", "담백한", "부드러운", "싱거운"],
            "spicy": ["매운", "매운거", "매운음식", "맵게", "화끈한", "칼칼한"],
            "sweet": ["단맛", "달콤한", "단거", "설탕", "달달한"],

            "salty": ["짠맛", "짠거", "간이센", "염분"],
            "sour": ["신맛", "새콤한", "시큼한", "레몬", "식초"],
            "savory": ["감칠맛", "구수한", "깊은맛", "진한맛", "고소한", "고소", "구수", "진한"]
        }
        
        detected_taste = None
        for taste, keywords in taste_patterns.items():
            if any(keyword in raw_text for keyword in keywords):
                detected_taste = taste
                break
        
        # 위치 질문 감지 (추가)
        location_keywords = ["어디", "어디로", "어디서", "가게", "위치", "주소", "찾아가", "갈만한"]
        is_location_question = any(keyword in raw_text for keyword in location_keywords)
        
        if is_location_question and recommendations:
            # 구체적인 가게 정보 제공
            shop_info_texts = []
            for rec in recommendations[:2]:
                shop_name = rec.get('shop_name', '')
                address = rec.get('address', '')
                menu_name = rec.get('menu_name', '')
                price = rec.get('price', 0)
                
                if shop_name and address:
                    shop_info_texts.append(f"🏪 {shop_name} ({address})")
                    shop_info_texts.append(f"   추천메뉴: {menu_name} {price:,}원")
            
            if shop_info_texts:
                response_text = "\n".join(shop_info_texts)
                return ChatbotResponse(
                    text=response_text + "\n이 가게들 어떠세요? 😊",
                    recommendations=recommendations,
                    action_required=False,
                    metadata={"location_answer": True}
                )
        
        # 맛 선호도가 감지되면 응답
        # 맛 선호도가 감지되면 응답 (더 구체적으로)
        if detected_taste:
            food_type = entities.food_type if entities else "음식"
            budget_text = f"{entities.budget}원" if entities and entities.budget else ""
            
            taste_responses = {
                "mild": ("순한 음식", ""),
                "spicy": ("매운 음식", ""),
                "sweet": ("달콤한 음식", ""),
                "salty": ("짭조름한 음식", ""),
                "sour": ("새콤한 음식", ""),
                "savory": ("고소한 음식", "")
            }
            
            taste_desc, emoji = taste_responses.get(detected_taste, ("그런 맛의 음식", ""))
            
            # 구체적인 추천과 함께 응답
            if recommendations:
                shop_names = [rec.get('shop_name', '') for rec in recommendations[:2]]
                return ChatbotResponse(
                    text=f"{taste_desc} 좋아하시는군요! {', '.join(shop_names)} 같은 곳 어떠세요? {emoji}",
                    recommendations=recommendations,
                    action_required=False,
                    metadata={
                        "taste_preference_collected": detected_taste,
                        "switch_to_normal_mode": True  # 정상 모드로 전환
                    }
                )
            else:
                return ChatbotResponse(
                    text=f"{taste_desc} 좋아하시는군요! {food_type} {budget_text} 맛집 찾아드릴게요! {emoji}",
                    recommendations=recommendations,
                    action_required=False,
                    metadata={
                        "taste_preference_collected": detected_taste,
                        "switch_to_normal_mode": True  # 정상 모드로 전환
                    }
                )

        # 아직 맛 선호도 정보가 없으면 계속 질문
        if not user_profile.taste_preferences:
            return ChatbotResponse(
                text="평소에 어떤 맛을 좋아하시나요?",
                recommendations=recommendations,
                follow_up_questions=[],
                action_required=True
            )

        # 다른 정보 수집...
        return self._generate_template_response(extracted_info, recommendations, user_profile)

    def _parse_rag_context_to_recommendations(self, rag_context: str) -> List[Dict]:
        """RAG 컨텍스트를 추천 형태로 파싱 (개선 버전)"""
        recommendations = []
        
        try:
            # 실제 가게 데이터와 매칭
            if not rag_context or rag_context.strip() == "검색 결과가 없습니다.":
                # RAG 결과가 없으면 실제 가게에서 랜덤 선택
                import random
                shops = list(self.knowledge.shops.values())[:20]  # 상위 20개
                random.shuffle(shops)
                
                for shop in shops[:3]:
                    shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
                    if shop_menus:
                        menu = random.choice(shop_menus)
                        recommendations.append({
                            'shop_id': shop.id,
                            'shop_name': shop.name,
                            'menu_name': menu.name,
                            'price': menu.price,
                            'category': shop.category,
                            'address': shop.address,
                            'is_good_influence_shop': shop.is_good_influence_shop,
                            'type': 'fallback_recommendation'
                        })
                
                logger.info(f"RAG 결과 없음 - 폴백 추천 {len(recommendations)}개 생성")
                return recommendations
            
            # RAG 컨텍스트에서 키워드 추출
            lines = rag_context.lower().split('\n')
            keywords = []
            
            for line in lines:
                # 음식 관련 키워드 추출
                food_keywords = ['치킨', '피자', '한식', '중식', '일식', '양식', '분식', '카페', '디저트', 
                               '버거', '파스타', '샐러드', '김밥', '떡볶이', '라면', '우동', '초밥']
                for keyword in food_keywords:
                    if keyword in line:
                        keywords.append(keyword)
            
            # 키워드가 없으면 일반 추천
            if not keywords:
                keywords = ['치킨', '피자', '한식']  # 기본 인기 카테고리
            
            # 키워드 기반으로 실제 가게 매칭
            for keyword in keywords[:3]:  # 최대 3개
                matched_shops = []
                
                # 카테고리로 매칭
                for shop in self.knowledge.shops.values():
                    if keyword in shop.category.lower() or keyword in shop.name.lower():
                        matched_shops.append(shop)
                
                if matched_shops:
                    shop = matched_shops[0]  # 첫 번째 매칭
                    shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
                    
                    if shop_menus:
                        # 가장 저렴한 메뉴 선택
                        menu = min(shop_menus, key=lambda x: x.price)
                        recommendations.append({
                            'shop_id': shop.id,
                            'shop_name': shop.name,
                            'menu_name': menu.name,
                            'price': menu.price,
                            'category': shop.category,
                            'address': shop.address,
                            'is_good_influence_shop': shop.is_good_influence_shop,
                            'type': 'rag_matched'
                        })
            
            # 추천이 부족하면 착한가게로 채우기
            if len(recommendations) < 3:
                good_shops = [s for s in self.knowledge.shops.values() if s.is_good_influence_shop]
                for shop in good_shops[:3-len(recommendations)]:
                    shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
                    if shop_menus:
                        menu = min(shop_menus, key=lambda x: x.price)
                        recommendations.append({
                            'shop_id': shop.id,
                            'shop_name': shop.name,
                            'menu_name': menu.name,
                            'price': menu.price,
                            'category': shop.category,
                            'address': shop.address,
                            'is_good_influence_shop': True,
                            'type': 'good_influence_shop'
                        })
            
            logger.info(f"RAG 파싱 완료: {len(recommendations)}개 실제 가게 추천")
            return recommendations[:3]
            
        except Exception as e:
            logger.error(f"RAG 컨텍스트 파싱 실패: {e}")
            # 에러 시 기본 추천 반환
            return self._get_default_recommendations()
    
    def _get_default_recommendations(self) -> List[Dict]:
        """기본 추천 (에러 폴백)"""
        recommendations = []
        
        # 착한가게 우선
        good_shops = [s for s in self.knowledge.shops.values() if s.is_good_influence_shop][:3]
        
        for shop in good_shops:
            shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
            if shop_menus:
                menu = min(shop_menus, key=lambda x: x.price)
                recommendations.append({
                    'shop_id': shop.id,
                    'shop_name': shop.name,
                    'menu_name': menu.name,
                    'price': menu.price,
                    'category': shop.category,
                    'address': shop.address,
                    'is_good_influence_shop': True,
                    'type': 'default_fallback'
                })
        
        return recommendations
    def _enrich_recommendations_with_rag(self, recommendations: List[Dict], rag_context: str) -> List[Dict]:
        """추천 엔진 결과를 RAG 정보로 보강"""
        if not recommendations:
            # 추천 엔진 결과가 없으면 RAG만으로 추천 생성 (폴백)
            logger.info("추천 엔진 결과가 없어 RAG 전용 추천으로 폴백")
            return self._parse_rag_context_to_recommendations(rag_context)
        
        try:
            # RAG에서 추가 정보 추출
            rag_info = self._extract_rag_additional_info(rag_context)
            
            # 기존 추천에 RAG 정보 보강
            enriched_recommendations = []
            
            for rec in recommendations:
                enriched_rec = rec.copy()
                
                # RAG에서 관련 정보 찾아서 보강
                shop_name = rec.get('shop_name', '')
                menu_name = rec.get('menu_name', '')
                
                # RAG 정보에서 매칭되는 가게/메뉴 찾기
                for rag_item in rag_info:
                    if (rag_item.get('shop_name', '') == shop_name or 
                        rag_item.get('menu_name', '') == menu_name):
                        
                        # RAG에서 추가 정보 병합
                        enriched_rec.update({
                            'rag_description': rag_item.get('description', ''),
                            'rag_context': True,
                            'semantic_match_score': rag_item.get('relevance_score', 0.8)
                        })
                        break
                
                enriched_recommendations.append(enriched_rec)
            
            # RAG에서 추가 추천이 있으면 뒤에 붙이기 (최대 5개)
            additional_recs = [item for item in rag_info 
                             if not any(item.get('shop_name', '') == rec.get('shop_name', '') 
                                      for rec in recommendations)]
            
            for additional_rec in additional_recs[:2]:  # 최대 2개 추가
                enriched_recommendations.append({
                    'shop_name': additional_rec.get('shop_name', ''),
                    'menu_name': additional_rec.get('menu_name', ''),
                    'price': additional_rec.get('price', 0),
                    'type': additional_rec.get('type', 'rag_additional'),
                    'rag_description': additional_rec.get('description', ''),
                    'rag_context': True,
                    'semantic_match_score': additional_rec.get('relevance_score', 0.7)
                })
            
            logger.info(f"RAG 보강 완료: 기본 {len(recommendations)}개 → 최종 {len(enriched_recommendations)}개")
            return enriched_recommendations[:5]  # 최대 5개로 제한
            
        except Exception as e:
            logger.error(f"RAG 보강 실패: {e}")
            return recommendations  # 실패 시 원본 반환

    def _extract_rag_additional_info(self, rag_context: str) -> List[Dict]:
        """RAG 컨텍스트에서 추가 정보 추출"""
        # _parse_rag_context_to_recommendations와 유사하지만 
        # 보강용 정보에 특화된 파싱
        return self._parse_rag_context_to_recommendations(rag_context)

    def _extract_shop_info_from_line(self, line: str) -> Dict:
        """라인에서 가게 정보 추출"""
        shop_info = {}
        
        # 가게 이름 추출
        if '가게 이름:' in line:
            parts = line.split('가게 이름:')
            if len(parts) > 1:
                name_part = parts[1].split('.')[0].strip()
                shop_info['name'] = name_part
        
        # 카테고리 추출
        if '카테고리:' in line:
            parts = line.split('카테고리:')
            if len(parts) > 1:
                category_part = parts[1].split('.')[0].strip()
                shop_info['category'] = category_part
        
        # 주소 추출
        if '주소:' in line:
            parts = line.split('주소:')
            if len(parts) > 1:
                address_part = parts[1].split('.')[0].strip()
                shop_info['location'] = address_part
                
        return shop_info

    def _extract_menu_info_from_line(self, line: str) -> Dict:
        """라인에서 메뉴 정보 추출"""
        menu_info = {}
        
        # 메뉴명 추출
        if '메뉴명:' in line:
            parts = line.split('메뉴명:')
            if len(parts) > 1:
                name_part = parts[1].split('.')[0].strip()
                menu_info['name'] = name_part
        
        # 가격 추출
        if '가격:' in line:
            parts = line.split('가격:')
            if len(parts) > 1:
                price_part = parts[1].split('원')[0].strip()
                try:
                    menu_info['price'] = int(price_part.replace(',', ''))
                except:
                    pass
        
        # 설명 추출
        if '설명:' in line:
            parts = line.split('설명:')
            if len(parts) > 1:
                desc_part = parts[1].split('.')[0].strip()
                menu_info['description'] = desc_part
                
        return menu_info
        
    def _generate_follow_up_questions(self, intent, entities, recommendations) -> List[str]:
        """후속 질문 생성"""
        questions = []
        
        if intent == IntentType.FOOD_REQUEST:
            if not entities.get('budget'):
                questions.append("예산은 얼마 정도 생각하고 계시나요?")
            if not entities.get('companions'):
                questions.append("혼자 드실 건가요?")
        elif intent == IntentType.BUDGET_INQUIRY:
            if not entities.get('food_type'):
                questions.append("어떤 종류의 음식이 좋으실까요?")
        
        if len(recommendations) > 1:
            questions.append("더 자세한 정보가 필요하신가요?")
            
        return questions[:2]
    
    def _format_recommendations(self, recommendations: List[Dict]) -> str:
        """추천 정보를 형식화"""
        if not recommendations:
            return ""
        
        rec_texts = []
        for i, rec in enumerate(recommendations[:3], 1):
            shop_name = rec.get('shop_name', '')
            menu_name = rec.get('menu_name', '')
            price = rec.get('price', 0)
            
            if shop_name and menu_name:
                rec_text = f"{i}. {shop_name} - {menu_name} ({price:,}원)"
                if rec.get('is_good_influence_shop'):
                    rec_text += " [착한가게]"
                rec_texts.append(rec_text)
        
        if rec_texts:
            return "🌟 추천 가게:\n" + "\n".join(rec_texts)
        return ""

        # # 가장 중요한 것부터 질문
        # if "taste" in missing_data:
        #     return ChatbotResponse(
        #         text=f"혹시 매운 음식 좋아하세요? 아니면 순한 걸 좋아하세요?",
        #         recommendations=recommendations,
        #         follow_up_questions=["매운 걸 좋아해요", "순한 걸 좋아해요", "상관없어요"],
        #         action_required=True
        #     )
        #
        # elif "companions" in missing_data:
        #     return ChatbotResponse(
        #         text="평소에 주로 누구와 드시는 편인가요?",
        #         recommendations=recommendations,
        #         follow_up_questions=["주로 혼자", "친구들과", "가족과", "다양하게"],
        #         action_required=True
        #     )
        #
        # else:
        #     # 데이터가 충분하면 일반 응답으로
        #     return self._generate_template_response(extracted_info, recommendations, user_profile)

# 편의 함수들
def create_response_generator(
    knowledge: NaviyamKnowledge,
    nlg: NaviyamNLG,
    model: KoAlpacaModel = None
) -> NaviyamResponseGenerator:
    """응답 생성기 생성 (편의 함수)"""
    return NaviyamResponseGenerator(knowledge, nlg, model)

def quick_recommendation(
    knowledge: NaviyamKnowledge,
    food_type: str,
    budget: int = None
) -> List[Dict]:
    """빠른 추천 (편의 함수)"""
    engine = RecommendationEngine(knowledge)
    return engine.recommend_by_food_type(food_type, budget)

def test_response_generation(
    generator: NaviyamResponseGenerator,
    test_inputs: List[str]
) -> List[Dict]:
    """응답 생성 테스트 (편의 함수)"""
    results = []

    for text in test_inputs:
        # 간단한 ExtractedInfo 생성 (실제로는 NLU에서)
        from data.data_structure import ExtractedInfo, ExtractedEntity, IntentType

        extracted_info = ExtractedInfo(
            intent=IntentType.FOOD_REQUEST,
            entities=ExtractedEntity(food_type="치킨"),
            confidence=0.8,
            raw_text=text
        )

        response = generator.generate_response(extracted_info)

        results.append({
            "input": text,
            "response": response.text,
            "recommendations_count": len(response.recommendations),
            "method": response.metadata.get("generation_method", "template")
        })

    return results