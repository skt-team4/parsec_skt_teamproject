"""
모델 팩토리 - 다양한 LLM 모델을 통합 관리
KoAlpaca, A.X 3.1 Lite 등을 설정으로 선택 가능
"""

import logging
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass

# from .koalpaca_model import KoAlpacaModel  # 파일이 없으므로 주석 처리
from .ax_model import AXModel
from .models_config import ModelConfigManager

logger = logging.getLogger(__name__)


@dataclass
class ModelSelection:
    """모델 선택 설정"""
    model_type: str = "ax"  # "koalpaca" or "ax"
    use_cache: bool = True
    cache_dir: Optional[str] = None
    enable_lora: bool = False
    lora_path: Optional[str] = None


class ModelFactory:
    """통합 모델 팩토리 클래스"""
    
    SUPPORTED_MODELS = {
        "koalpaca": {
            "class": AXModel,  # KoAlpacaModel 대신 AXModel 사용
            "name": "KoAlpaca 5.8B",
            "description": "기존 한국어 모델 (안정적, 빠름)"
        },
        "ax": {
            "class": AXModel,
            "name": "A.X 3.1 Lite 7B", 
            "description": "SKT 한국어 특화 모델 (고품질, 나비얌 최적화)"
        }
    }
    
    @classmethod
    def create_model(
        cls, 
        model_config, 
        model_selection: ModelSelection = None
    ) -> AXModel:
        """
        설정에 따라 적절한 모델을 생성
        
        Args:
            model_config: 모델 설정
            model_selection: 모델 선택 옵션
            
        Returns:
            선택된 모델 인스턴스
        """
        if model_selection is None:
            model_selection = ModelSelection()
            
        model_type = model_selection.model_type.lower()
        
        if model_type not in cls.SUPPORTED_MODELS:
            raise ValueError(
                f"지원하지 않는 모델 타입: {model_type}. "
                f"지원 모델: {list(cls.SUPPORTED_MODELS.keys())}"
            )
        
        model_info = cls.SUPPORTED_MODELS[model_type]
        model_class = model_info["class"]
        
        logger.info(f"모델 생성: {model_info['name']} - {model_info['description']}")
        
        try:
            # 모델 인스턴스 생성
            config_manager = ModelConfigManager(model_config)
            model_instance = model_class(model_config, config_manager)
            
            # 모델 로드
            cache_dir = model_selection.cache_dir if model_selection.use_cache else None
            model_instance.load_model(cache_dir)
            
            # LoRA 설정 (필요시)
            if model_selection.enable_lora:
                model_instance.setup_lora(model_selection.lora_path)
            
            logger.info(f"{model_info['name']} 모델 생성 완료")
            return model_instance
            
        except Exception as e:
            logger.error(f"모델 생성 실패: {model_info['name']} - {e}")
            raise
    
    @classmethod
    def get_model_info(cls, model_type: str) -> Dict[str, str]:
        """모델 정보 조회"""
        model_type = model_type.lower()
        if model_type not in cls.SUPPORTED_MODELS:
            raise ValueError(f"지원하지 않는 모델 타입: {model_type}")
        
        return cls.SUPPORTED_MODELS[model_type].copy()
    
    @classmethod
    def list_supported_models(cls) -> Dict[str, Dict[str, str]]:
        """지원되는 모든 모델 목록 반환"""
        return cls.SUPPORTED_MODELS.copy()
    
    @classmethod
    def create_naviyam_model(
        cls,
        model_config,
        model_type: str = "ax",  # 기본값을 A.X 3.1 Lite로 변경
        cache_dir: Optional[str] = None,
        enable_lora: bool = False
    ) -> AXModel:
        """
        나비얌 챗봇에 최적화된 모델 생성 (편의 함수)
        
        Args:
            model_config: 모델 설정
            model_type: 모델 타입 ("koalpaca" or "ax")
            cache_dir: 캐시 디렉토리
            enable_lora: LoRA 활성화 여부
            
        Returns:
            나비얌용 모델 인스턴스
        """
        model_selection = ModelSelection(
            model_type=model_type,
            use_cache=True,
            cache_dir=cache_dir,
            enable_lora=enable_lora
        )
        
        logger.info(f"나비얌 챗봇용 {cls.SUPPORTED_MODELS[model_type]['name']} 모델 생성")
        return cls.create_model(model_config, model_selection)


# 편의 함수들 (기존 코드 호환성)
def create_model(
    model_config,
    model_type: str = "ax",
    cache_dir: Optional[str] = None
) -> AXModel:
    """모델 생성 편의 함수"""
    return ModelFactory.create_naviyam_model(
        model_config, 
        model_type=model_type, 
        cache_dir=cache_dir
    )


def create_koalpaca_model(model_config, cache_dir: Optional[str] = None) -> AXModel:
    """KoAlpaca 모델 생성"""
    return ModelFactory.create_naviyam_model(
        model_config,
        model_type="koalpaca",
        cache_dir=cache_dir
    )


def create_ax_model(model_config, cache_dir: Optional[str] = None) -> AXModel:
    """A.X 3.1 Lite 모델 생성"""
    return ModelFactory.create_naviyam_model(
        model_config,
        model_type="ax", 
        cache_dir=cache_dir
    )


# 설정 기반 모델 생성
def create_model_from_config(config_dict: Dict[str, Any]) -> AXModel:
    """
    설정 딕셔너리로부터 모델 생성
    
    config_dict 예시:
    {
        "model_type": "ax",  # or "koalpaca"
        "cache_dir": "./cache",
        "enable_lora": False,
        "lora_path": None
    }
    """
    from utils.config import get_default_config
    
    model_type = config_dict.get("model_type", "ax")
    cache_dir = config_dict.get("cache_dir", None)
    enable_lora = config_dict.get("enable_lora", False)
    lora_path = config_dict.get("lora_path", None)
    
    # 기본 모델 설정 가져오기
    model_config = get_default_config().model
    
    model_selection = ModelSelection(
        model_type=model_type,
        use_cache=cache_dir is not None,
        cache_dir=cache_dir,
        enable_lora=enable_lora,
        lora_path=lora_path
    )
    
    return ModelFactory.create_model(model_config, model_selection)


if __name__ == "__main__":
    # 테스트 코드
    print("=== 모델 팩토리 테스트 ===")
    
    # 지원 모델 목록
    models = ModelFactory.list_supported_models()
    print("지원 모델:")
    for model_type, info in models.items():
        print(f"  {model_type}: {info['name']} - {info['description']}")
    
    # 모델 정보 조회
    ax_info = ModelFactory.get_model_info("ax")
    print(f"\nA.X 모델 정보: {ax_info}")