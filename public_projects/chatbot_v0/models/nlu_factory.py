"""
NLU 모델 팩토리
다양한 NLU 모델을 선택적으로 로드
"""

import logging
from typing import Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class NLUFactory:
    """NLU 모델 팩토리 클래스"""
    
    @staticmethod
    def create_nlu_model(
        nlu_type: str = "ax_lite",
        model_path: Optional[str] = None,
        use_4bit: bool = True,
        use_trained: bool = False,
        config=None
    ) -> Union['NaviyamNLU', 'AXEncoderNLU']:
        """
        NLU 모델 생성
        
        Args:
            nlu_type: NLU 타입 ('ax_lite', 'ax_encoder')
            model_path: 커스텀 모델 경로 (선택사항)
            use_4bit: 4비트 양자화 사용 여부 (ax_lite용)
            use_trained: 학습된 모델 사용 여부 (ax_encoder용)
            config: 설정 객체
            
        Returns:
            NLU 모델 인스턴스
        """
        
        logger.info(f"NLU 모델 생성: type={nlu_type}, path={model_path}, 4bit={use_4bit}, trained={use_trained}")
        
        if nlu_type == "ax_lite":
            # A.X 3.1 Lite LLM 기반 NLU
            from nlp.nlu import NaviyamNLU
            
            if config and hasattr(config, 'nlu'):
                return NaviyamNLU(config.nlu, use_4bit=use_4bit)
            else:
                # 기본 설정으로 생성
                from utils.config import NLUConfig
                nlu_config = NLUConfig(
                    model_name="skt/A.X-3.1-Light",
                    adapter_path=model_path,
                    max_new_tokens=100,
                    temperature=0.7,
                    top_p=0.9
                )
                return NaviyamNLU(nlu_config, use_4bit=use_4bit)
                
        elif nlu_type == "ax_encoder":
            # A.X Encoder 경량 NLU (NaviyamNLU 인터페이스 호환)
            from models.ax_encoder_nlu_adapter import AXEncoderNLUAdapter
            
            # 모델 경로 결정
            if model_path:
                # 사용자 지정 경로
                final_path = model_path
            elif use_trained:
                # 학습된 모델 사용 (10개 의도 우선)
                trained_paths = [
                    "./models/ax_encoder_simplified_nlu",  # 10개 의도 (최신)
                    "./models/ax_encoder_real_data_nlu",    # 28개 의도
                    "./models/ax_encoder_nlu_best",
                    "./models/ax_encoder_nlu_trained",
                    "./models/ax_encoder_nlu_finetuned"
                ]
                for path in trained_paths:
                    if Path(path).exists():
                        final_path = path
                        logger.info(f"학습된 모델 발견: {path}")
                        if "simplified" in path:
                            logger.info("✅ 10개 의도 단순화 모델 사용")
                        break
                else:
                    logger.warning("학습된 모델을 찾을 수 없어 기본 모델 사용")
                    final_path = "./models/ax_encoder_base"
            else:
                # 학습 안된 기본 모델
                final_path = "./models/ax_encoder_base"
            
            return AXEncoderNLUAdapter(
                model_path=final_path
            )
            
        else:
            raise ValueError(f"지원하지 않는 NLU 타입: {nlu_type}")
    
    @staticmethod
    def get_available_models() -> dict:
        """사용 가능한 NLU 모델 목록"""
        return {
            "ax_lite": {
                "name": "A.X 3.1 Lite",
                "description": "SKT LLM 기반 NLU (정확하지만 느림)",
                "size": "~6GB",
                "speed": "~2000ms"
            },
            "ax_encoder": {
                "name": "A.X Encoder",
                "description": "경량 인코더 NLU (빠르지만 단순)",
                "size": "~600MB",
                "speed": "~36ms"
            }
        }


def create_nlu_from_config(config, nlu_override: Optional[dict] = None):
    """
    설정 기반 NLU 생성 (기존 코드 호환용)
    
    Args:
        config: 전체 설정 객체
        nlu_override: NLU 관련 오버라이드 설정
            - nlu_type: 'ax_lite' 또는 'ax_encoder'
            - model_path: 커스텀 모델 경로
            - use_trained: 학습된 모델 사용 여부
    """
    if nlu_override:
        return NLUFactory.create_nlu_model(
            nlu_type=nlu_override.get('nlu_type', 'ax_lite'),
            model_path=nlu_override.get('model_path'),
            use_4bit=nlu_override.get('use_4bit', True),
            use_trained=nlu_override.get('use_trained', False),
            config=config
        )
    else:
        # 기존 방식 (NaviyamNLU 사용)
        from nlp.nlu import NaviyamNLU
        return NaviyamNLU(config.nlu, use_4bit=getattr(config, 'use_4bit', True))