"""
NLU 모델 선택기
- A.X 3.1 Lite (기존 LLM 기반)
- A.X Encoder (새로운 경량 모델)
- 자동 폴백 지원
"""

import logging
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

from src.nlp.nlu import NaviyamNLU  # 기존 LLM 기반 NLU
from models.ax_encoder_nlu import AXEncoderNLUWrapper  # 새로운 경량 NLU

logger = logging.getLogger(__name__)


class NLUModelSelector:
    """NLU 모델 선택 및 관리"""
    
    # 지원 모델 타입
    MODEL_TYPES = {
        "ax_lite": "A.X 3.1 Lite (LLM)",
        "ax_encoder": "A.X Encoder (경량)",
        "hybrid": "하이브리드 (자동 선택)"
    }
    
    def __init__(
        self,
        model_type: str = "ax_lite",  # 기본값은 기존 모델
        ax_encoder_path: Optional[str] = None,
        enable_fallback: bool = True
    ):
        """
        초기화
        
        Args:
            model_type: 사용할 모델 타입 ("ax_lite", "ax_encoder", "hybrid")
            ax_encoder_path: A.X Encoder 모델 경로
            enable_fallback: 실패 시 폴백 활성화
        """
        self.model_type = model_type
        self.enable_fallback = enable_fallback
        
        # 모델 초기화
        self.ax_lite_nlu = None
        self.ax_encoder_nlu = None
        
        self._initialize_models(ax_encoder_path)
        
        logger.info(f"NLU 모델 선택기 초기화: {self.MODEL_TYPES.get(model_type, model_type)}")
    
    def _initialize_models(self, ax_encoder_path: Optional[str]):
        """모델 초기화"""
        
        # A.X Lite 모델 (기존)
        if self.model_type in ["ax_lite", "hybrid"]:
            try:
                self.ax_lite_nlu = NaviyamNLU(use_preprocessor=True)
                logger.info("A.X 3.1 Lite NLU 초기화 완료")
            except Exception as e:
                logger.error(f"A.X Lite NLU 초기화 실패: {e}")
        
        # A.X Encoder 모델 (새로운)
        if self.model_type in ["ax_encoder", "hybrid"]:
            try:
                # 경로가 없으면 기본 경로 사용
                if not ax_encoder_path:
                    ax_encoder_path = "./models/ax_encoder_nlu_v1"
                
                self.ax_encoder_nlu = AXEncoderNLUWrapper(ax_encoder_path)
                logger.info("A.X Encoder NLU 초기화 완료")
            except Exception as e:
                logger.error(f"A.X Encoder NLU 초기화 실패: {e}")
                
                # 폴백 설정
                if self.model_type == "ax_encoder" and self.enable_fallback:
                    logger.warning("A.X Encoder 실패, A.X Lite로 폴백")
                    self.model_type = "ax_lite"
                    if not self.ax_lite_nlu:
                        self.ax_lite_nlu = NaviyamNLU(use_preprocessor=True)
    
    def extract_intent_and_entities(
        self,
        text: str,
        use_specific_model: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any], float]:
        """
        의도와 엔티티 추출
        
        Args:
            text: 입력 텍스트
            use_specific_model: 특정 모델 강제 사용
            
        Returns:
            (intent, entities, confidence)
        """
        # 모델 선택
        model_to_use = use_specific_model or self.model_type
        
        if model_to_use == "hybrid":
            # 하이브리드 모드: 입력 길이에 따라 자동 선택
            model_to_use = self._select_best_model(text)
            logger.debug(f"하이브리드 모드: {model_to_use} 선택")
        
        # 모델 실행
        try:
            if model_to_use == "ax_encoder" and self.ax_encoder_nlu:
                result = self.ax_encoder_nlu.extract_intent_and_entities(text)
                logger.debug("A.X Encoder NLU 사용")
                return result
                
            elif self.ax_lite_nlu:
                # ExtractedInfo 객체 반환하는 기존 메서드 호출
                extracted_info = self.ax_lite_nlu.extract_intent_and_entities(text)
                
                # 튜플 형태로 변환
                entities_dict = {}
                if extracted_info.entities:
                    entity_obj = extracted_info.entities
                    # ExtractedEntity 객체의 속성들을 딕셔너리로 변환
                    if entity_obj.menu:
                        entities_dict['MENU'] = entity_obj.menu
                    if entity_obj.location:
                        entities_dict['LOCATION'] = entity_obj.location
                    if entity_obj.price_range:
                        entities_dict['PRICE'] = [entity_obj.price_range]
                    if entity_obj.time:
                        entities_dict['TIME'] = [entity_obj.time]
                
                logger.debug("A.X Lite NLU 사용")
                return extracted_info.intent.value, entities_dict, extracted_info.confidence
                
        except Exception as e:
            logger.error(f"NLU 처리 중 오류: {e}")
            
            # 폴백 시도
            if self.enable_fallback:
                return self._fallback_extraction(text)
            else:
                raise
        
        # 기본값 반환
        return "기타", {}, 0.5
    
    def _select_best_model(self, text: str) -> str:
        """
        입력에 따라 최적 모델 선택 (하이브리드 모드)
        
        규칙:
        - 짧은 입력 (30자 이하): A.X Encoder (빠른 응답)
        - 긴 입력 (30자 초과): A.X Lite (복잡한 이해)
        - 특수 패턴: 상황에 따라 선택
        """
        # 길이 기반 선택
        if len(text) <= 30:
            # 짧은 입력은 Encoder가 효율적
            if self.ax_encoder_nlu:
                return "ax_encoder"
        
        # 복잡한 문장은 LLM이 유리
        if any(word in text for word in ["그리고", "또한", "하지만", "그런데"]):
            if self.ax_lite_nlu:
                return "ax_lite"
        
        # 기본값
        if self.ax_encoder_nlu:
            return "ax_encoder"
        elif self.ax_lite_nlu:
            return "ax_lite"
        
        return "ax_lite"
    
    def _fallback_extraction(self, text: str) -> Tuple[str, Dict[str, Any], float]:
        """폴백 처리 (규칙 기반)"""
        logger.warning("폴백 모드로 NLU 처리")
        
        intent = "기타"
        entities = {}
        confidence = 0.3
        
        # 간단한 규칙 기반 의도 분류
        if "추천" in text or "뭐 먹" in text:
            intent = "음식추천"
            confidence = 0.6
        elif "얼마" in text or "가격" in text:
            intent = "가격문의"
            confidence = 0.6
        elif "쿠폰" in text:
            intent = "쿠폰조회"
            confidence = 0.7
        
        return intent, entities, confidence
    
    def get_model_info(self) -> Dict[str, Any]:
        """현재 모델 정보 반환"""
        return {
            "selected_type": self.model_type,
            "type_description": self.MODEL_TYPES.get(self.model_type, "Unknown"),
            "ax_lite_loaded": self.ax_lite_nlu is not None,
            "ax_encoder_loaded": self.ax_encoder_nlu is not None,
            "fallback_enabled": self.enable_fallback
        }
    
    def benchmark(self, test_samples: list) -> Dict[str, Any]:
        """모델 성능 비교"""
        results = {}
        
        for model_type in ["ax_lite", "ax_encoder"]:
            if (model_type == "ax_lite" and self.ax_lite_nlu) or \
               (model_type == "ax_encoder" and self.ax_encoder_nlu):
                
                import time
                total_time = 0
                success_count = 0
                
                for sample in test_samples:
                    try:
                        start = time.time()
                        _, _, confidence = self.extract_intent_and_entities(
                            sample, 
                            use_specific_model=model_type
                        )
                        elapsed = time.time() - start
                        
                        total_time += elapsed
                        if confidence > 0.5:
                            success_count += 1
                    except:
                        pass
                
                results[model_type] = {
                    "avg_time": total_time / len(test_samples) if test_samples else 0,
                    "success_rate": success_count / len(test_samples) if test_samples else 0
                }
        
        return results


# 기존 시스템과의 호환을 위한 팩토리 함수
def create_nlu_model(config: Optional[Dict] = None) -> NLUModelSelector:
    """
    설정에 따라 NLU 모델 생성
    
    Args:
        config: 설정 딕셔너리
            - model_type: "ax_lite", "ax_encoder", "hybrid"
            - ax_encoder_path: Encoder 모델 경로
            - enable_fallback: 폴백 활성화 여부
    """
    if not config:
        config = {}
    
    return NLUModelSelector(
        model_type=config.get("model_type", "ax_lite"),  # 기본값은 기존 모델
        ax_encoder_path=config.get("ax_encoder_path"),
        enable_fallback=config.get("enable_fallback", True)
    )