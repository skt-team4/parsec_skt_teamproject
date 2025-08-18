#!/usr/bin/env python3
"""
통합 챗봇 - SelectivePipeline을 NaviyamChatbot 인터페이스로 래핑
main.py 수정 최소화하면서 새로운 파이프라인 사용
"""

import logging
from typing import Optional
from pathlib import Path

from src.inference.selective_pipeline import SelectivePipeline
from src.inference.simple_response_generator import SimpleLLMResponseGenerator
from src.models.nlu_factory import NLUFactory
from src.data.data_structure import UserInput, ExtractedInfo
from src.utils.coupon_manager import CouponManager
from src.recommendation.coupon_recommender import CouponRecommender

logger = logging.getLogger(__name__)


class UnifiedChatbot:
    """NaviyamChatbot 인터페이스를 유지하면서 SelectivePipeline 사용"""
    
    def __init__(self, config):
        """
        NaviyamChatbot과 동일한 인터페이스 유지
        내부적으로 SelectivePipeline 사용
        """
        self.config = config
        
        # 지식베이스 로드
        from data.data_loader import DataLoader
        loader = DataLoader()
        self.knowledge = loader.load_knowledge()
        
        # NLU 초기화 (10개 의도 버전 사용)
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
    
    def chat(self, user_message: str, user_id: str = "guest") -> str:
        """
        NaviyamChatbot과 동일한 인터페이스
        
        Args:
            user_message: 사용자 입력
            user_id: 사용자 ID
            
        Returns:
            챗봇 응답 텍스트
        """
        try:
            # UserInput 생성
            user_input = UserInput(
                text=user_message,
                user_id=user_id,
                timestamp=None
            )
            
            # NLU 처리 (10개 의도로 단순화됨)
            extracted_info = self.nlu.process(user_message)
            
            # 의도 매핑 (10개 → SelectivePipeline이 이해하는 형태로)
            extracted_info = self._map_simplified_intent(extracted_info)
            
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
            
            # 응답 텍스트만 반환 (NaviyamChatbot 호환)
            return response.message
            
        except Exception as e:
            logger.error(f"챗봇 처리 중 오류: {e}")
            return "죄송해요, 처리 중 문제가 발생했어요. 다시 시도해주세요. 😅"
    
    def _map_simplified_intent(self, extracted_info: ExtractedInfo) -> ExtractedInfo:
        """
        10개 단순화 의도를 기존 시스템이 이해하는 형태로 매핑
        
        단순화 의도:
        - recommendation → food_request
        - info_inquiry → price_inquiry
        - operation → time_inquiry
        - service → delivery_inquiry
        - budget → budget_inquiry
        - special → special_request
        - greeting → greeting
        - closing → thanks
        - nonsense → nonsense
        - other → food_request
        """
        intent_map = {
            "recommendation": "food_request",
            "info_inquiry": "price_inquiry",
            "operation": "time_inquiry",
            "service": "delivery_inquiry",
            "budget": "budget_inquiry",
            "special": "special_request",
            "greeting": "greeting",
            "closing": "thanks",
            "nonsense": "nonsense",
            "other": "food_request"
        }
        
        # 의도 이름이 문자열인 경우 매핑
        if hasattr(extracted_info, 'intent') and isinstance(extracted_info.intent, str):
            mapped_intent = intent_map.get(extracted_info.intent, extracted_info.intent)
            extracted_info.intent = mapped_intent
        
        return extracted_info
    
    def save_data(self):
        """데이터 저장 (NaviyamChatbot 호환)"""
        if self.data_collector:
            self.data_collector.save()
            logger.info("학습 데이터 저장 완료")


def create_unified_chatbot(config, **kwargs):
    """팩토리 함수 (create_naviyam_chatbot 대체)"""
    return UnifiedChatbot(config)