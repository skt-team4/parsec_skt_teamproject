"""
나비얌 챗봇 설정 관리
argparse + 기본값 조합으로 유연한 파라미터 관리
중앙화된 경로 관리 추가
"""

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# 환경변수 로딩 (보안 설정)
env = os.getenv("APP_ENV", "development")
dotenv_path = f".env.{env}" if env != "development" else ".env"

print(f"[CONFIG] Loading environment from {dotenv_path}")
load_dotenv(dotenv_path=dotenv_path, verbose=True)


@dataclass
class PathConfig:
    """중앙화된 경로 관리"""
    # 기본 디렉토리
    PROJECT_ROOT: Path = PROJECT_ROOT
    DATA_DIR: Path = PROJECT_ROOT / "data"
    OUTPUT_DIR: Path = PROJECT_ROOT / "outputs"
    CACHE_DIR: Path = PROJECT_ROOT / "cache"
    LOG_DIR: Path = PROJECT_ROOT / "outputs" / "logs"
    
    # 데이터 파일
    RAG_DATA_FILE: Path = PROJECT_ROOT / "rag" / "test_data.json"
    RESTAURANTS_DATA: Path = DATA_DIR / "restaurants_optimized.json"
    
    # 모델 관련
    MODEL_CACHE_DIR: Path = CACHE_DIR / "models"
    LORA_ADAPTERS_DIR: Path = OUTPUT_DIR / "lora_adapters"
    
    # FAISS 관련 - Windows 한글 경로 문제 회피
    TEMP_FAISS_DIR: Path = Path("C:/temp_naviyam")
    PREBUILT_FAISS_INDEX: Path = TEMP_FAISS_DIR / "prebuilt_faiss.faiss"
    PREBUILT_FAISS_METADATA: Path = TEMP_FAISS_DIR / "prebuilt_faiss_metadata.json"
    FAISS_BUILD_INFO: Path = OUTPUT_DIR / "prebuilt_faiss_build_info.json"
    
    # 학습 데이터
    LEARNING_DATA_DIR: Path = OUTPUT_DIR / "learning_data"
    TRAINING_DATA_DIR: Path = OUTPUT_DIR / "training_data"
    
    # 사용자 데이터
    USER_PROFILES_DIR: Path = OUTPUT_DIR / "user_profiles"
    CONVERSATION_LOGS_DIR: Path = OUTPUT_DIR / "conversation_logs"
    
    # 추천 모델
    RECOMMENDATION_MODELS_DIR: Path = OUTPUT_DIR / "recommendation_models"
    BEST_MODEL_PATH: Path = RECOMMENDATION_MODELS_DIR / "best_model.pth"
    
    # 임시 파일
    TEMP_DIR: Path = OUTPUT_DIR / "temp"
    
    def __post_init__(self):
        """필요한 디렉토리 생성"""
        import logging
        logger = logging.getLogger(__name__)
        
        directories = [
            self.OUTPUT_DIR,
            self.CACHE_DIR,
            self.LOG_DIR,
            self.MODEL_CACHE_DIR,
            self.LORA_ADAPTERS_DIR,
            self.LEARNING_DATA_DIR,
            self.TRAINING_DATA_DIR,
            self.USER_PROFILES_DIR,
            self.CONVERSATION_LOGS_DIR,
            self.RECOMMENDATION_MODELS_DIR,
            self.TEMP_DIR
        ]
        
        for directory in directories:
            try:
                directory.mkdir(exist_ok=True, parents=True)
            except PermissionError as e:
                logger.error(f"디렉토리 생성 실패 (권한 없음): {directory} - {e}")
                # 대체 경로 시도 (사용자 홈 디렉토리)
                alt_directory = Path.home() / ".naviyam" / directory.name
                try:
                    alt_directory.mkdir(exist_ok=True, parents=True)
                    logger.warning(f"대체 경로 사용: {alt_directory}")
                    setattr(self, directory.name, alt_directory)
                except Exception as e2:
                    logger.error(f"대체 경로도 실패: {e2}")
            except Exception as e:
                logger.error(f"디렉토리 생성 실패: {directory} - {e}")
    
    def get_path(self, key: str) -> Path:
        """키로 경로 가져오기"""
        return getattr(self, key.upper(), None)
    
    def get_str(self, key: str) -> str:
        """경로를 문자열로 반환"""
        path = self.get_path(key)
        return str(path) if path else ""
    
    def validate_paths(self) -> List[str]:
        """필수 파일/디렉토리 존재 여부 확인"""
        missing = []
        
        # 필수 파일 체크
        if not self.RAG_DATA_FILE.exists():
            missing.append(f"RAG 데이터 파일: {self.RAG_DATA_FILE}")
        
        # 프로덕션 환경에서 필수 파일
        if os.getenv("APP_ENV") == "production":
            if not self.PREBUILT_FAISS_INDEX.exists():
                missing.append(f"FAISS 인덱스: {self.PREBUILT_FAISS_INDEX}")
            if not self.PREBUILT_FAISS_METADATA.exists():
                missing.append(f"FAISS 메타데이터: {self.PREBUILT_FAISS_METADATA}")
        
        return missing
    
    def get_relative_path(self, key: str, base: str = "PROJECT_ROOT") -> Path:
        """기준 경로 대비 상대 경로 반환"""
        target = self.get_path(key)
        base_path = self.get_path(base)
        try:
            return target.relative_to(base_path)
        except ValueError:
            # 상대 경로 변환 불가능한 경우 절대 경로 반환
            return target


@dataclass
class ModelConfig:
    """모델 관련 설정"""
    model_type: str = "ax"  # "koalpaca" or "ax" (A.X 3.1 Lite)
    model_name: str = "skt/A.X-3.1-Light"  # A.X 3.1 Lite 기본값
    use_8bit: bool = False
    use_4bit: bool = True  # A.X 3.1 Lite는 4-bit 양자화 사용
    max_vram_gb: int = 6  # RTX 3060 Ti 기준
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.1
    max_length: int = 512
    temperature: float = 0.7
    do_sample: bool = True
    enable_lora: bool = False  # LoRA 활성화 여부
    lora_path: Optional[str] = None  # LoRA 어댑터 경로


@dataclass
class DataConfig:
    """데이터 관련 설정"""
    data_path: str = "./preprocessed_data"
    output_path: str = "./outputs"
    cache_dir: str = "./cache"
    max_conversations: int = 1000
    save_processed: bool = True
    # 데이터베이스 연결 정보 (환경변수에서 로드)
    database_url: str = os.getenv("DATABASE_URL", "")


@dataclass
class TrainingConfig:
    """학습 관련 설정"""
    epochs: int = 3
    batch_size: int = 4
    learning_rate: float = 1e-4
    warmup_steps: int = 100
    save_steps: int = 500
    eval_steps: int = 100
    gradient_accumulation_steps: int = 4


@dataclass
class RAGConfig:
    """RAG 시스템 관련 설정"""
    vector_store_type: str = "prebuilt_faiss"  # "mock", "faiss", "prebuilt_faiss", "chromadb"
    embedding_model: str = "all-MiniLM-L6-v2"  # SentenceTransformer 모델명
    embedding_dim: int = 384
    top_k: int = 5
    enable_rag: bool = True
    
    # PathConfig를 사용하여 동적으로 경로 설정
    def get_index_path(self, path_config: PathConfig) -> str:
        """Vector store 타입에 따른 인덱스 경로 반환"""
        if self.vector_store_type == "prebuilt_faiss":
            return str(path_config.PREBUILT_FAISS_INDEX)
        else:
            return str(path_config.OUTPUT_DIR / "faiss_index.faiss")
    
    def get_metadata_path(self, path_config: PathConfig) -> str:
        """메타데이터 경로 반환"""
        return str(path_config.PREBUILT_FAISS_METADATA)


@dataclass
class NLUConfig:
    """NLU 모델 설정"""
    model_name: str = "skt/A.X-3.1-Light"
    adapter_path: Optional[str] = None
    max_new_tokens: int = 100
    temperature: float = 0.7
    top_p: float = 0.9
    use_4bit: bool = True
    use_trained: bool = False


@dataclass
class InferenceConfig:
    """추론 관련 설정"""
    max_response_length: int = 200
    confidence_threshold: float = 0.5
    enable_personalization: bool = True
    save_conversations: bool = False
    response_timeout: int = 30  # 초


@dataclass
class AppConfig:
    """전체 앱 설정"""
    mode: str = "chat"  # chat, training, inference, evaluation
    log_level: str = "INFO"
    debug: bool = False
    device: str = "auto"  # auto, cpu, cuda

    # 하위 설정들 - field() with default_factory 사용
    model: ModelConfig = field(default_factory=ModelConfig)
    data: DataConfig = field(default_factory=DataConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    inference: InferenceConfig = field(default_factory=InferenceConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    paths: PathConfig = field(default_factory=PathConfig)  # 중앙화된 경로 설정


def create_parser() -> argparse.ArgumentParser:
    """명령행 인자 파서 생성"""
    parser = argparse.ArgumentParser(
        description="나비얌 챗봇 - 아동 대상 착한가게 추천 AI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # ==============================================
    # 메인 실행 모드
    # ==============================================
    parser.add_argument(
        "--mode",
        choices=["chat", "training", "inference", "evaluation"],
        default="chat",
        help="실행 모드 선택"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="디버그 모드 활성화"
    )

    parser.add_argument(
        "--log_level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="로그 레벨 설정"
    )

    # ==============================================
    # 데이터 관련
    # ==============================================
    data_group = parser.add_argument_group("데이터 설정")

    data_group.add_argument(
        "--data_path",
        type=str,
        default="./preprocessed_data",
        help="전처리된 데이터 경로"
    )

    data_group.add_argument(
        "--output_path",
        type=str,
        default="./outputs",
        help="출력 파일 저장 경로"
    )

    data_group.add_argument(
        "--cache_dir",
        type=str,
        default="./cache",
        help="캐시 디렉토리 경로"
    )

    data_group.add_argument(
        "--max_conversations",
        type=int,
        default=1000,
        help="최대 대화 기록 수"
    )

    # ==============================================
    # 모델 관련
    # ==============================================
    model_group = parser.add_argument_group("모델 설정")

    model_group.add_argument(
        "--model_type",
        type=str,
        choices=["koalpaca", "ax"],
        default="ax",
        help="모델 타입 선택 (koalpaca: KoAlpaca 5.8B, ax: A.X 3.1 Lite)"
    )

    model_group.add_argument(
        "--model_name", 
        type=str,
        default="skt/A.X-3.1-Light",
        help="사용할 모델 이름"
    )

    model_group.add_argument(
        "--use_8bit",
        action="store_true",
        default=False,
        help="8bit 양자화 사용"
    )

    model_group.add_argument(
        "--use_4bit",
        action="store_true",
        default=True,
        help="4bit 양자화 사용 (A.X 3.1 Lite 기본값)"
    )

    model_group.add_argument(
        "--max_vram_gb",
        type=int,
        default=6,
        help="최대 VRAM 사용량 (GB) - RTX 3060 Ti 기준"
    )

    model_group.add_argument(
        "--lora_rank",
        type=int,
        default=16,
        help="LoRA rank 설정"
    )

    model_group.add_argument(
        "--max_length",
        type=int,
        default=512,
        help="최대 토큰 길이"
    )

    model_group.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="생성 온도 설정"
    )

    # ==============================================
    # 학습 관련
    # ==============================================
    train_group = parser.add_argument_group("학습 설정")

    train_group.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="학습 에포크 수"
    )

    train_group.add_argument(
        "--batch_size",
        type=int,
        default=4,
        help="배치 크기"
    )

    train_group.add_argument(
        "--learning_rate",
        type=float,
        default=1e-4,
        help="학습률"
    )

    train_group.add_argument(
        "--save_steps",
        type=int,
        default=500,
        help="모델 저장 주기"
    )

    # ==============================================
    # NLU 관련 설정 (새로 추가)
    # ==============================================
    nlu_group = parser.add_argument_group("NLU 설정")
    
    nlu_group.add_argument(
        "--nlu_type",
        type=str,
        choices=["ax_lite", "ax_encoder"],
        default="ax_lite",
        help="NLU 모델 타입 (ax_lite: LLM 기반, ax_encoder: 경량 인코더)"
    )
    
    nlu_group.add_argument(
        "--use_trained",
        action="store_true",
        help="학습된 A.X Encoder 모델 사용 (ax_encoder 전용)"
    )
    
    # ==============================================
    # 추론 관련
    # ==============================================
    inference_group = parser.add_argument_group("추론 설정")

    inference_group.add_argument(
        "--confidence_threshold",
        type=float,
        default=0.5,
        help="신뢰도 임계값"
    )

    inference_group.add_argument(
        "--enable_personalization",
        action="store_true",
        default=True,
        help="개인화 기능 활성화"
    )

    inference_group.add_argument(
        "--save_conversations",
        action="store_true",
        help="대화 기록 저장"
    )

    inference_group.add_argument(
        "--response_timeout",
        type=int,
        default=30,
        help="응답 타임아웃 (초)"
    )

    return parser


def parse_config() -> AppConfig:
    """명령행 인자를 파싱하여 설정 객체 생성"""
    parser = create_parser()
    args = parser.parse_args()

    # AppConfig 객체 생성
    config = AppConfig()

    # 메인 설정
    config.mode = args.mode
    config.debug = args.debug
    config.log_level = args.log_level
    
    # NLU 설정 (새로 추가)
    config.nlu_type = args.nlu_type
    config.use_trained = args.use_trained
    config.use_4bit = args.use_4bit  # 기존 설정 활용

    # 데이터 설정
    config.data.data_path = args.data_path
    config.data.output_path = args.output_path
    config.data.cache_dir = args.cache_dir
    config.data.max_conversations = args.max_conversations

    # 모델 설정
    config.model.model_type = args.model_type
    config.model.model_name = args.model_name
    config.model.use_8bit = args.use_8bit
    config.model.use_4bit = args.use_4bit
    config.model.max_vram_gb = args.max_vram_gb
    config.model.lora_rank = args.lora_rank
    config.model.max_length = args.max_length
    config.model.temperature = args.temperature

    # 학습 설정
    config.training.epochs = args.epochs
    config.training.batch_size = args.batch_size
    config.training.learning_rate = args.learning_rate
    config.training.save_steps = args.save_steps

    # 추론 설정
    config.inference.confidence_threshold = args.confidence_threshold
    config.inference.enable_personalization = args.enable_personalization
    config.inference.save_conversations = args.save_conversations
    config.inference.response_timeout = args.response_timeout

    # 경로 생성
    Path(config.data.output_path).mkdir(exist_ok=True)
    Path(config.data.cache_dir).mkdir(exist_ok=True)
    
    # 보안 검증: 필수 환경변수 확인
    if not config.data.database_url:
        print("[WARNING] DATABASE_URL 환경변수가 설정되지 않았습니다.")
        print("   .env 파일을 확인하거나 환경변수를 설정해주세요.")
        print("   예시: DATABASE_URL='postgresql://user:password@localhost/naviyam_db'")
    else:
        print(f"[SUCCESS] 데이터베이스 연결 정보 로드 완료: {config.data.database_url[:20]}...")

    return config


def get_config_summary(config: AppConfig) -> str:
    """설정 요약 문자열 생성"""
    model_type_display = "A.X 3.1 Lite" if config.model.model_type == "ax" else "KoAlpaca"
    summary = f"""
=== 나비얌 챗봇 설정 ===
모드: {config.mode}
모델 타입: {model_type_display}
모델: {config.model.model_name}
양자화: {'8bit' if config.model.use_8bit else '4bit' if config.model.use_4bit else 'None'}
데이터 경로: {config.data.data_path}
출력 경로: {config.data.output_path}
개인화: {'ON' if config.inference.enable_personalization else 'OFF'}
디버그: {'ON' if config.debug else 'OFF'}
========================
"""
    return summary


# 편의 함수들
def get_default_config() -> AppConfig:
    """기본 설정 반환"""
    return AppConfig()


def save_config(config: AppConfig, path: str):
    """설정을 파일로 저장"""
    import json
    from dataclasses import asdict

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(asdict(config), f, indent=2, ensure_ascii=False)


def load_config(path: str) -> AppConfig:
    """파일에서 설정 로드"""
    import json

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 딕셔너리를 AppConfig로 변환 (간단한 버전)
    config = AppConfig()
    # 실제로는 더 정교한 변환 로직 필요
    return config