#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A.X 모델 기반 NLU (Natural Language Understanding)
의도 분석과 엔티티 추출을 A.X 모델이 수행
"""

import json
import logging
import sys
import os
from typing import Dict, Optional, Tuple, List

# 상위 디렉토리 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data.data_structure import IntentType, ExtractedInfo, ExtractedEntity, ConfidenceLevel

logger = logging.getLogger(__name__)


class AXNLUProcessor:
    """A.X 모델 기반 NLU 처리기"""
    
    def __init__(self, model=None, use_encoder=False):
        """
        Args:
            model: A.X 모델 (3.1 LITE 또는 Encoder)
            use_encoder: Encoder 모델 사용 여부
        """
        self.model = model
        self.use_encoder = use_encoder
        
        # Few-shot 예시
        self.few_shot_examples = """
예시 1:
입력: "안녕하세요"
출력: {"intent": "general_chat", "entities": {}, "confidence": 0.95}

예시 2:
입력: "치킨 추천해줘"
출력: {"intent": "food_request", "entities": {"food_type": "치킨"}, "confidence": 0.9}

예시 3:
입력: "부평에서 피자 먹고 싶어"
출력: {"intent": "food_request", "entities": {"location": "부평", "food_type": "피자"}, "confidence": 0.95}

예시 4:
입력: "배고파"
출력: {"intent": "food_request", "entities": {}, "confidence": 0.8}

예시 5:
입력: "오늘 날씨 어때?"
출력: {"intent": "general_chat", "entities": {}, "confidence": 0.9}
"""
    
    def analyze_intent(self, user_input: str) -> ExtractedInfo:
        """
        A.X 모델을 사용하여 의도 분석
        
        Args:
            user_input: 사용자 입력
            
        Returns:
            ExtractedInfo 객체
        """
        
        # 모델이 없으면 폴백 처리
        if not self.model:
            return self._fallback_analysis(user_input)
        
        # 프롬프트 구성
        prompt = f"""당신은 음식 추천 챗봇의 NLU 모듈입니다. 사용자 입력을 분석하여 의도와 엔티티를 추출하세요.

가능한 의도(intent):
- general_chat: 일반 대화, 인사말, 일상 대화
- food_request: 음식/맛집 추천 요청
- location_inquiry: 위치 관련 문의
- time_inquiry: 시간/영업시간 문의
- budget_inquiry: 가격/예산 관련 문의

추출할 엔티티:
- location: 위치 (예: 부평, 강남, 홍대)
- food_type: 음식 종류 (예: 치킨, 피자, 한식, 중식)
- budget: 예산 (예: 만원, 2만원)
- time: 시간 (예: 점심, 저녁, 12시)

{self.few_shot_examples}

입력: "{user_input}"
출력 (JSON 형식으로만 응답):"""
        
        try:
            # A.X 모델 호출
            if hasattr(self.model, 'generate'):
                response = self.model.generate(
                    prompt,
                    max_new_tokens=150,
                    temperature=0.3,  # 낮은 temperature로 일관성 있는 출력
                    do_sample=True
                )
            elif hasattr(self.model, 'predict'):
                response = self.model.predict(prompt)
            else:
                logger.warning("Model does not have generate or predict method")
                return self._fallback_analysis(user_input)
            
            # JSON 파싱
            try:
                # 응답에서 JSON 부분만 추출
                if '{' in response and '}' in response:
                    json_start = response.index('{')
                    json_end = response.rindex('}') + 1
                    json_str = response[json_start:json_end]
                    result = json.loads(json_str)
                else:
                    raise ValueError("No JSON found in response")
                
                # ExtractedInfo 객체 생성
                return self._create_extracted_info(result, user_input)
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse model output: {e}")
                return self._fallback_analysis(user_input)
                
        except Exception as e:
            logger.error(f"A.X NLU processing failed: {e}")
            return self._fallback_analysis(user_input)
    
    def _create_extracted_info(self, result: Dict, user_input: str) -> ExtractedInfo:
        """
        파싱된 결과로 ExtractedInfo 객체 생성
        
        Args:
            result: 파싱된 JSON 결과
            user_input: 원본 사용자 입력
        """
        # 의도 매핑
        intent_str = result.get('intent', 'unknown')
        intent_map = {
            'general_chat': IntentType.GENERAL_CHAT,
            'food_request': IntentType.FOOD_REQUEST,
            'location_inquiry': IntentType.LOCATION_INQUIRY,
            'time_inquiry': IntentType.TIME_INQUIRY,
            'budget_inquiry': IntentType.BUDGET_INQUIRY,
            'unknown': IntentType.UNKNOWN
        }
        intent = intent_map.get(intent_str, IntentType.UNKNOWN)
        
        # 엔티티 추출
        entities = ExtractedEntity()
        entity_dict = result.get('entities', {})
        
        if 'location' in entity_dict:
            entities.location_preference = entity_dict['location']
        if 'food_type' in entity_dict:
            entities.food_type = entity_dict['food_type']
        if 'budget' in entity_dict:
            try:
                # "만원" -> 10000 변환
                budget_str = entity_dict['budget'].replace('만원', '0000').replace('원', '')
                entities.budget = int(budget_str)
            except:
                pass
        if 'time' in entity_dict:
            entities.time_preference = entity_dict['time']
        
        # 신뢰도
        confidence = float(result.get('confidence', 0.5))
        if confidence >= 0.8:
            confidence_level = ConfidenceLevel.HIGH
        elif confidence >= 0.5:
            confidence_level = ConfidenceLevel.MEDIUM
        else:
            confidence_level = ConfidenceLevel.LOW
        
        return ExtractedInfo(
            intent=intent,
            entities=entities,
            confidence=confidence,
            confidence_level=confidence_level,
            raw_text=user_input
        )
    
    def _fallback_analysis(self, user_input: str) -> ExtractedInfo:
        """
        모델이 없을 때 기본 규칙 기반 분석
        
        Args:
            user_input: 사용자 입력
        """
        # 기본 패턴 매칭
        greeting_patterns = ['안녕', '하이', 'hi', 'hello', '반가워', '좋은 아침', '좋은 저녁']
        food_patterns = ['추천', '먹을', '먹고 싶', '배고파', '뭐 먹', '맛집', '음식']
        
        # 의도 판단
        is_greeting = any(p in user_input.lower() for p in greeting_patterns)
        has_food_keyword = any(p in user_input for p in food_patterns)
        
        if is_greeting and not has_food_keyword:
            intent = IntentType.GENERAL_CHAT
            confidence = 0.7
        elif has_food_keyword:
            intent = IntentType.FOOD_REQUEST
            confidence = 0.8
        else:
            intent = IntentType.GENERAL_CHAT
            confidence = 0.5
        
        # 간단한 엔티티 추출
        entities = ExtractedEntity()
        
        # 위치 추출
        locations = ['부평', '인천', '부천', '서울', '강남', '홍대', '신촌']
        for loc in locations:
            if loc in user_input:
                entities.location_preference = loc
                break
        
        # 음식 종류 추출
        food_types = {
            '치킨': '치킨', '피자': '피자', '햄버거': '햄버거',
            '한식': '한식', '중식': '중식', '일식': '일식',
            '양식': '양식', '분식': '분식'
        }
        for food, category in food_types.items():
            if food in user_input:
                entities.food_type = category
                break
        
        confidence_level = ConfidenceLevel.MEDIUM if confidence >= 0.5 else ConfidenceLevel.LOW
        
        return ExtractedInfo(
            intent=intent,
            entities=entities,
            confidence=confidence,
            confidence_level=confidence_level,
            raw_text=user_input
        )


class AXEncoderNLU(AXNLUProcessor):
    """A.X Encoder 전용 NLU 프로세서"""
    
    def __init__(self):
        """A.X Encoder 모델 로드"""
        super().__init__(use_encoder=True)
        self._load_encoder_model()
    
    def _load_encoder_model(self):
        """A.X Encoder 모델 로드"""
        try:
            from models.model_factory import create_model
            from utils.config import ModelConfig
            
            # Encoder 전용 설정
            encoder_config = ModelConfig()
            encoder_config.model_name = "ax_encoder"
            encoder_config.model_type = "encoder"
            encoder_config.cache_dir = "./cache"
            
            self.model = create_model(
                model_config=encoder_config,
                model_type="encoder",
                cache_dir="./cache"
            )
            logger.info("A.X Encoder loaded for NLU")
            
        except Exception as e:
            logger.error(f"Failed to load A.X Encoder: {e}")
            self.model = None


def test_ax_nlu():
    """A.X NLU 테스트"""
    
    # NLU 프로세서 생성 (모델 없이 폴백 모드로)
    nlu = AXNLUProcessor()
    
    test_cases = [
        "안녕하세요",
        "치킨 추천해줘",
        "부평에서 피자 먹고 싶어",
        "배고파",
        "오늘 날씨 어때?",
        "만원 이하로 먹을 수 있는 거",
        "점심에 뭐 먹지?",
        "홍대 근처 맛집 알려줘"
    ]
    
    print("="*60)
    print("A.X NLU 테스트 (Fallback Mode)")
    print("="*60)
    
    for user_input in test_cases:
        result = nlu.analyze_intent(user_input)
        print(f"\n입력: '{user_input}'")
        print(f"  의도: {result.intent.value}")
        print(f"  신뢰도: {result.confidence:.2f}")
        if result.entities.location_preference:
            print(f"  위치: {result.entities.location_preference}")
        if result.entities.food_type:
            print(f"  음식: {result.entities.food_type}")


if __name__ == "__main__":
    test_ax_nlu()