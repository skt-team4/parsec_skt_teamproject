#!/usr/bin/env python3
"""
통합 챗봇 v2 - 의도 후처리기 통합 버전
10개 단순화 의도 → 28개 세부 의도 매핑
"""

import logging
from typing import Optional, Dict, List
from pathlib import Path

from src.inference.selective_pipeline import SelectivePipeline
from src.inference.simple_response_generator import SimpleLLMResponseGenerator
from src.models.nlu_factory import NLUFactory
from src.nlp.intent_postprocessor import IntentPostProcessor
from src.nlp.rule_based_preprocessor import RuleBasedPreprocessor
from src.data.data_structure import UserInput, ExtractedInfo, IntentType
from src.utils.coupon_manager import CouponManager
from src.recommendation.coupon_recommender import CouponRecommender

logger = logging.getLogger(__name__)


class UnifiedChatbotV2:
    """의도 후처리기가 통합된 통합 챗봇"""
    
    def __init__(self, config):
        """
        초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config
        
        # 지식베이스 로드
        from data.data_loader import DataLoader
        loader = DataLoader()
        self.knowledge = loader.load_knowledge()
        
        # NLU 초기화 (10개 의도 버전)
        nlu_type = getattr(config, 'nlu_type', 'ax_encoder')
        if nlu_type == 'ax_encoder':
            # 새로 학습한 10개 의도 모델 사용
            model_path = "models/ax_encoder_simplified_nlu"
            if Path(model_path).exists():
                logger.info(f"단순화된 NLU 모델 로드: {model_path}")
            else:
                # 폴백: 기존 모델
                model_path = "models/ax_encoder_real_data_nlu"
                logger.info(f"기존 NLU 모델 로드: {model_path}")
        
        self.nlu = NLUFactory.create_nlu_model(
            nlu_type=nlu_type,
            model_path=model_path,
            use_trained=True
        )
        
        # 전처리기 및 후처리기 초기화
        self.rule_preprocessor = RuleBasedPreprocessor()
        self.intent_processor = IntentPostProcessor()
        logger.info("규칙 기반 전처리기 및 IntentPostProcessor 초기화 완료")
        
        # LLM 생성기
        from models.ax_model import AXModel
        ax_model = AXModel(use_4bit=getattr(config, 'use_4bit', True))
        self.llm_generator = SimpleLLMResponseGenerator(
            self.knowledge, 
            ax_model,
            use_wide_deep=getattr(config, 'use_wide_deep', True)
        )
        
        # SelectivePipeline 초기화
        self.pipeline = SelectivePipeline(
            knowledge=self.knowledge,
            llm_generator=self.llm_generator,
            config_path="config/pipeline_config.ini",
            enable_data_collection=getattr(config, 'enable_data_collection', True)
        )
        
        # 쿠폰 기능 (옵션)
        if getattr(config, 'enable_coupon', True):
            self.coupon_manager = CouponManager(self.knowledge)
            self.coupon_recommender = CouponRecommender(self.knowledge)
        
        # 데이터 수집기 (옵션)
        if getattr(config, 'enable_data_collection', True):
            from inference.data_collector import LearningDataCollector
            self.data_collector = LearningDataCollector(
                save_path=f"{config.data.output_path}/learning_data",
                buffer_size=100,
                auto_save_interval=300
            )
        else:
            self.data_collector = None
        
        logger.info("UnifiedChatbotV2 초기화 완료")
    
    def chat(self, user_message: str, user_id: str = "guest") -> str:
        """
        챗봇 대화 처리
        
        Args:
            user_message: 사용자 입력
            user_id: 사용자 ID
            
        Returns:
            챗봇 응답 텍스트
        """
        try:
            # UserInput 생성
            from datetime import datetime
            user_input = UserInput(
                text=user_message,
                user_id=user_id,
                timestamp=datetime.now()
            )
            
            # NLU 처리 (10개 단순화 의도)
            extracted_info = self.nlu.process(user_message)
            logger.debug(f"NLU 결과 (단순화): {extracted_info.intent}, 신뢰도: {extracted_info.confidence:.2f}")
            
            # 규칙 기반 전처리 적용
            rule_intent, rule_confidence = self.rule_preprocessor.preprocess(user_message)
            if rule_intent and rule_confidence >= 0.85:
                # 규칙이 높은 신뢰도로 매칭되면 규칙 우선
                extracted_info.intent = rule_intent
                extracted_info.confidence = rule_confidence
                logger.debug(f"규칙 적용: {rule_intent} (신뢰도: {rule_confidence:.2f})")
            elif rule_intent and rule_confidence >= 0.75:
                # 중간 신뢰도면 모델과 비교
                if str(extracted_info.intent).split('.')[-1].lower() == rule_intent:
                    extracted_info.confidence = min(extracted_info.confidence * 1.2, 1.0)
                elif extracted_info.confidence < rule_confidence:
                    extracted_info.intent = rule_intent
                    extracted_info.confidence = rule_confidence
                    logger.debug(f"규칙 적용: {rule_intent} (신뢰도: {rule_confidence:.2f})")
            
            # 의도 후처리 (10개 → 28개 세부 의도)
            extracted_info = self._apply_intent_postprocessing(extracted_info, user_message)
            logger.debug(f"후처리 결과 (세부): {extracted_info.intent}, 신뢰도: {extracted_info.confidence:.2f}")
            
            # 사용자 위치 (간단히 처리)
            user_location = {
                'latitude': 37.5665,
                'longitude': 126.9780,
                'address': '서울특별시'
            }
            
            # SelectivePipeline 처리
            response = self.pipeline.process(
                user_input=user_input,
                extracted_info=extracted_info,
                conversation_context=[],
                user_profile=None,
                user_location=user_location,
                user_id=user_id
            )
            
            # 데이터 수집
            if self.data_collector:
                self.data_collector.collect(
                    user_input=user_input,
                    extracted_info=extracted_info,
                    response=response
                )
            
            # 응답 텍스트 반환
            return response.message
            
        except Exception as e:
            logger.error(f"챗봇 처리 중 오류: {e}", exc_info=True)
            return "죄송해요, 처리 중 문제가 발생했어요. 다시 시도해주세요. 😅"
    
    def _apply_intent_postprocessing(self, extracted_info: ExtractedInfo, user_message: str) -> ExtractedInfo:
        """
        의도 후처리기를 사용하여 10개 → 28개 세부 의도로 변환
        
        Args:
            extracted_info: NLU 처리 결과 (10개 의도)
            user_message: 원본 사용자 입력
            
        Returns:
            후처리된 ExtractedInfo (28개 세부 의도)
        """
        
        # 현재 의도 문자열 가져오기
        current_intent_str = extracted_info.intent.value if hasattr(extracted_info.intent, 'value') else str(extracted_info.intent)
        
        # 엔티티 정보 준비
        # ExtractedEntity 객체에서 속성 직접 접근
        entities = {
            "location": bool(getattr(extracted_info.entities, "location", None)),
            "food": bool(getattr(extracted_info.entities, "food_type", None)),
            "price": bool(getattr(extracted_info.entities, "price_range", None))
        }
        
        # 후처리 실행
        detailed_intent, adjusted_confidence = self.intent_processor.process(
            simplified_intent=current_intent_str,
            text=user_message,
            entities=entities,
            confidence=extracted_info.confidence
        )
        
        # IntentType enum으로 변환
        try:
            # IntentType enum 매핑 (실제 enum 값에 맞게 수정)
            intent_enum_map = {
                # 추천/검색 관련
                "food_request": IntentType.FOOD_REQUEST,
                "restaurant_search": IntentType.SHOP_INQUIRY,  # RESTAURANT_SEARCH 없음
                "menu_recommendation": IntentType.MENU_INQUIRY,  # MENU_RECOMMENDATION 없음
                "category_search": IntentType.SHOP_INQUIRY,
                "nearby_search": IntentType.LOCATION_INQUIRY,
                "popular_request": IntentType.FOOD_REQUEST,
                
                # 정보 문의 관련
                "price_inquiry": IntentType.PRICE_INQUIRY,
                "nutrition_inquiry": IntentType.NUTRITIONAL_INFO,  # NUTRITION_INQUIRY 없음
                "review_inquiry": IntentType.RATING_REQUEST,  # REVIEW_INQUIRY 없음
                "ingredient_inquiry": IntentType.ALLERGY_INFO,  # ALLERGY_INQUIRY -> ALLERGY_INFO
                "allergy_inquiry": IntentType.ALLERGY_INFO,
                "discount_inquiry": IntentType.COUPON_INQUIRY,  # DISCOUNT_INQUIRY 없음
                
                # 운영 정보 관련
                "time_inquiry": IntentType.TIME_INQUIRY,
                "location_inquiry": IntentType.LOCATION_INQUIRY,
                "contact_inquiry": IntentType.SHOP_INQUIRY,  # CONTACT_INQUIRY 없음
                "holiday_inquiry": IntentType.TIME_INQUIRY,
                
                # 서비스 관련
                "delivery_inquiry": IntentType.DELIVERY_INQUIRY,
                "packaging_inquiry": IntentType.DELIVERY_INQUIRY,  # PACKAGING_INQUIRY 없음
                "reservation_inquiry": IntentType.RESERVATION_REQUEST,  # RESERVATION_INQUIRY -> RESERVATION_REQUEST
                "payment_inquiry": IntentType.PAYMENT_METHOD,  # PAYMENT_INQUIRY -> PAYMENT_METHOD
                "student_discount": IntentType.PAYMENT_METHOD,  # STUDENT_CARD 없음
                
                # 예산 관련
                "budget_constraint": IntentType.BUDGET_INQUIRY,  # BUDGET_CONSTRAINT -> BUDGET_INQUIRY
                "cheap_request": IntentType.BUDGET_INQUIRY,
                "value_request": IntentType.BUDGET_INQUIRY,
                
                # 특별 요구 (이런 상세 의도는 없으므로 FOOD_REQUEST로)
                "solo_dining": IntentType.FOOD_REQUEST,
                "group_dining": IntentType.FOOD_REQUEST,
                "date_place": IntentType.FOOD_REQUEST,
                "quiet_place": IntentType.FOOD_REQUEST,
                
                # 대화 관리
                "greeting": IntentType.GREETING,
                "thanks": IntentType.THANKS,
                "goodbye": IntentType.THANKS,  # GOODBYE 없음
                "feedback": IntentType.COMPLAINT,  # FEEDBACK -> COMPLAINT
                
                # 기타
                "nonsense": IntentType.NONSENSE,
                "spam": IntentType.NONSENSE,
                "other": IntentType.GENERAL_CHAT,  # OTHER_REQUEST 없음
                "unknown": IntentType.GENERAL_CHAT
            }
            
            # enum 변환
            if detailed_intent in intent_enum_map:
                extracted_info.intent = intent_enum_map[detailed_intent]
            else:
                # 매핑되지 않은 의도는 GENERAL_CHAT으로
                extracted_info.intent = IntentType.GENERAL_CHAT
                logger.warning(f"매핑되지 않은 의도: {detailed_intent}")
            
            # 신뢰도 업데이트
            extracted_info.confidence = adjusted_confidence
            
            # 메타데이터에 후처리 정보 추가
            if not hasattr(extracted_info, 'metadata') or extracted_info.metadata is None:
                extracted_info.metadata = {}
            
            extracted_info.metadata.update({
                "simplified_intent": current_intent_str,
                "detailed_intent": detailed_intent,
                "postprocessed": True,
                "confidence_adjustment": adjusted_confidence - extracted_info.confidence
            })
            
        except Exception as e:
            logger.error(f"의도 후처리 중 오류: {e}")
            # 오류 시 기본값 설정 (GENERAL_CHAT 사용)
            extracted_info.intent = IntentType.GENERAL_CHAT
            extracted_info.confidence = 0.5
        
        return extracted_info
    
    def get_intent_stats(self) -> Dict[str, int]:
        """의도별 통계 반환 (디버깅용)"""
        if not self.data_collector:
            return {}
        
        # 데이터 수집기에서 통계 가져오기
        stats = {}
        for data in self.data_collector.buffer:
            intent = data.get('extracted_info', {}).get('intent', 'unknown')
            stats[intent] = stats.get(intent, 0) + 1
        
        return stats
    
    def save_data(self):
        """데이터 저장"""
        if self.data_collector:
            self.data_collector.save()
            logger.info("학습 데이터 저장 완료")


def create_unified_chatbot_v2(config, **kwargs):
    """팩토리 함수"""
    return UnifiedChatbotV2(config)


# 테스트
if __name__ == "__main__":
    # 간단한 설정 객체
    class SimpleConfig:
        nlu_type = 'ax_encoder'
        use_4bit = True
        use_wide_deep = False
        enable_coupon = False
        enable_data_collection = False
        
        class data:
            output_path = "output"
    
    # 챗봇 생성
    config = SimpleConfig()
    chatbot = UnifiedChatbotV2(config)
    
    # 테스트 대화
    test_cases = [
        "부평에서 치킨 먹고 싶어",
        "가격 얼마야?",
        "급식카드 되나요?",
        "만원 이하 메뉴 추천해줘",
        "지금 열어있는 곳 알려줘"
    ]
    
    print("=== UnifiedChatbotV2 테스트 ===\n")
    for message in test_cases:
        print(f"사용자: {message}")
        response = chatbot.chat(message)
        print(f"챗봇: {response[:100]}...\n")