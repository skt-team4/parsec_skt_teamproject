"""
A.X Encoder NLU를 NaviyamNLU 인터페이스와 호환되도록 하는 어댑터
"""

import logging
from typing import Optional
from pathlib import Path

from src.data.data_structure import ExtractedInfo, ExtractedEntity, IntentType, ConfidenceLevel
from src.models.ax_encoder_nlu import AXEncoderNLU

logger = logging.getLogger(__name__)


class AXEncoderNLUAdapter:
    """A.X Encoder NLU를 NaviyamNLU 인터페이스로 래핑"""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        초기화
        
        Args:
            model_path: A.X Encoder 모델 경로
        """
        self.encoder_nlu = AXEncoderNLU(model_path)
        logger.info(f"A.X Encoder NLU 어댑터 초기화: {model_path}")
        
        # 의도 매핑 (A.X Encoder -> IntentType)
        # ax_encoder_nlu.py의 INTENT_LABELS와 매칭
        self.intent_mapping = {
            "음식추천": IntentType.FOOD_REQUEST,
            "가격문의": IntentType.BUDGET_INQUIRY,
            "잔액확인": IntentType.BUDGET_INQUIRY,
            "쿠폰조회": IntentType.COUPON_INQUIRY,
            "가게정보": IntentType.LOCATION_INQUIRY,
            "위치검색": IntentType.LOCATION_INQUIRY,
            "영업시간": IntentType.TIME_INQUIRY,
            "일반대화": IntentType.GENERAL_CHAT,
            "감사인사": IntentType.GENERAL_CHAT,
            "기타": IntentType.UNKNOWN,
            # 영어 매핑도 유지 (호환성)
            "FOOD_REQUEST": IntentType.FOOD_REQUEST,
            "BUDGET_INQUIRY": IntentType.BUDGET_INQUIRY,
            "LOCATION_INQUIRY": IntentType.LOCATION_INQUIRY,
            "TIME_INQUIRY": IntentType.TIME_INQUIRY,
            "COUPON_INQUIRY": IntentType.COUPON_INQUIRY,
            "NUTRITIONAL_INFO": IntentType.NUTRITIONAL_INFO,
            "GENERAL_CHAT": IntentType.GENERAL_CHAT,
            "UNKNOWN": IntentType.UNKNOWN
        }
        
        # 학습 데이터 수집기 (옵션)
        self.learning_data_collector = None
    
    def extract_intent_and_entities(self, text: str, user_id: str = None) -> ExtractedInfo:
        """
        NaviyamNLU와 동일한 인터페이스로 의도와 엔티티 추출
        
        Args:
            text: 입력 텍스트
            user_id: 사용자 ID (옵션)
            
        Returns:
            ExtractedInfo 객체
        """
        # A.X Encoder로 예측
        result = self.encoder_nlu.predict(text)
        
        # 의도 변환
        intent_type = self.intent_mapping.get(result.intent, IntentType.UNKNOWN)
        
        # 엔티티 변환
        extracted_entity = None
        if result.entities:
            entity_dict = {}
            
            for entity in result.entities:
                entity_type_lower = entity.entity_type.lower()
                
                # 엔티티 타입별 매핑
                if entity_type_lower == "menu" or entity_type_lower == "food":
                    entity_dict["food_type"] = entity.value
                elif entity_type_lower == "location":
                    entity_dict["location"] = entity.value
                elif entity_type_lower == "price" or entity_type_lower == "budget":
                    try:
                        # 가격 문자열에서 숫자 추출
                        price_str = str(entity.value).replace(",", "").replace("원", "")
                        # 특수 토큰이나 이상한 값 필터링
                        if price_str and not price_str.startswith("#") and not price_str.startswith("<"):
                            entity_dict["budget"] = int(price_str)
                    except:
                        # 숫자로 변환 실패 시 무시
                        pass
                elif entity_type_lower == "time":
                    entity_dict["time"] = entity.value
                else:
                    # 기타 엔티티는 raw_entities에 저장
                    if "raw_entities" not in entity_dict:
                        entity_dict["raw_entities"] = {}
                    entity_dict["raw_entities"][entity.entity_type] = entity.value
            
            # ExtractedEntity 생성 (필드명 수정)
            extracted_entity = ExtractedEntity(
                food_type=entity_dict.get("food_type"),
                location_preference=entity_dict.get("location"),  # location -> location_preference
                budget=entity_dict.get("budget"),
                time_preference=entity_dict.get("time"),  # time -> time_preference
                menu_options=[],  # 빈 리스트로 초기화
                companions=[],  # 빈 리스트로 초기화
                special_requirements=[]  # 빈 리스트로 초기화
            )
        else:
            # 엔티티가 없어도 기본 ExtractedEntity 생성
            extracted_entity = ExtractedEntity()
        
        # 텍스트에서 추가 엔티티 추출 (규칙 기반 보완)
        text_lower = text.lower()
        
        # 음식 종류 추출 (엔티티에 없는 경우)
        if not extracted_entity.food_type:
            food_keywords = ['치킨', '피자', '햄버거', '중식', '한식', '일식', '양식', '분식', '카페', '디저트', '떡볶이', '김밥']
            for food in food_keywords:
                if food in text_lower:
                    extracted_entity.food_type = food
                    break
        
        # 예산 추출 (엔티티에 없는 경우)
        if not extracted_entity.budget:
            import re
            budget_match = re.search(r'(\d+)\s*원', text)
            if budget_match:
                extracted_entity.budget = int(budget_match.group(1))
        
        # 신뢰도 레벨 계산
        if result.confidence >= 0.8:
            confidence_level = ConfidenceLevel.HIGH
        elif result.confidence >= 0.5:
            confidence_level = ConfidenceLevel.MEDIUM
        elif result.confidence >= 0.3:
            confidence_level = ConfidenceLevel.MEDIUM_LOW
        elif result.confidence >= 0.2:
            confidence_level = ConfidenceLevel.LOW
        else:
            confidence_level = ConfidenceLevel.VERY_LOW
        
        # ExtractedInfo 생성
        extracted_info = ExtractedInfo(
            intent=intent_type,
            entities=extracted_entity if extracted_entity else ExtractedEntity(),  # 빈 엔티티라도 필요
            confidence=result.confidence,
            confidence_level=confidence_level,
            raw_text=text
        )
        
        # 학습 데이터 수집 (설정된 경우)
        if self.learning_data_collector and user_id:
            # collect_nlu_features 메서드 사용 (collect_nlu_output은 없음)
            nlu_features = {
                "text": text,
                "intent": intent_type.value,
                "entities": entity_dict if result.entities else {},
                "confidence": result.confidence
            }
            self.learning_data_collector.collect_nlu_features(user_id, nlu_features)
        
        logger.debug(f"A.X Encoder NLU 결과: 의도={intent_type.value}, 신뢰도={result.confidence:.2f}")
        
        return extracted_info
    
    def process(self, text: str, user_id: str = None) -> ExtractedInfo:
        """
        process 메서드 (extract_intent_and_entities의 별칭)
        """
        return self.extract_intent_and_entities(text, user_id)
    
    def set_learning_data_collector(self, collector):
        """학습 데이터 수집기 설정"""
        self.learning_data_collector = collector
        logger.info("A.X Encoder NLU에 학습 데이터 수집기 연결됨")
    
    def get_model_info(self) -> dict:
        """모델 정보 반환"""
        return {
            "type": "ax_encoder",
            "name": "A.X Encoder NLU",
            "description": "SKT 경량 인코더 기반 NLU",
            "model_path": self.encoder_nlu.model_path,
            "device": str(self.encoder_nlu.device),
            "size": "~600MB",
            "speed": "~36ms"
        }