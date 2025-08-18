"""
모델 설정 및 하드웨어 최적화
RTX 3060 Ti (8GB VRAM) 환경 최적화
"""
import torch
import psutil
import GPUtil
from transformers import BitsAndBytesConfig
from peft import LoraConfig, TaskType
from typing import Dict, Optional, Tuple
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HardwareInfo:
    """하드웨어 정보"""
    gpu_name: str
    gpu_memory_total: float  # GB
    gpu_memory_free: float  # GB
    cpu_count: int
    ram_total: float  # GB
    ram_free: float  # GB


class ModelConfigManager:
    """모델 설정 관리자"""

    def __init__(self, model_config):
        """
        Args:
            model_config: ModelConfig 객체
        """
        self.config = model_config
        self.device = self._detect_device()
        self.hardware_info = self._get_hardware_info()

        # VRAM 사용량 최적화
        self._optimize_for_hardware()

    def _detect_device(self) -> torch.device:
        """최적 디바이스 감지"""
        if torch.cuda.is_available():
            device = torch.device("cuda")
            logger.info(f"CUDA 사용: {torch.cuda.get_device_name()}")
        else:
            device = torch.device("cpu")
            logger.warning("CUDA 없음. CPU 사용")
        return device

    def _get_hardware_info(self) -> HardwareInfo:
        """하드웨어 정보 수집"""
        info = HardwareInfo(
            gpu_name="Unknown",
            gpu_memory_total=0.0,
            gpu_memory_free=0.0,
            cpu_count=psutil.cpu_count(),
            ram_total=psutil.virtual_memory().total / (1024 ** 3),
            ram_free=psutil.virtual_memory().available / (1024 ** 3)
        )

        # GPU 정보
        if torch.cuda.is_available():
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    info.gpu_name = gpu.name
                    info.gpu_memory_total = gpu.memoryTotal / 1024  # MB to GB
                    info.gpu_memory_free = gpu.memoryFree / 1024
            except Exception as e:
                logger.warning(f"GPU 정보 수집 실패: {e}")
                # PyTorch 방식으로 fallback
                info.gpu_memory_total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                info.gpu_memory_free = info.gpu_memory_total  # 근사치

        logger.info(f"하드웨어: {info.gpu_name}, "
                    f"VRAM {info.gpu_memory_free:.1f}/{info.gpu_memory_total:.1f}GB, "
                    f"RAM {info.ram_free:.1f}/{info.ram_total:.1f}GB")

        return info

    def _optimize_for_hardware(self):
        """하드웨어에 맞게 설정 최적화"""
        if not torch.cuda.is_available():
            logger.warning("GPU 없음. CPU 모드로 전환")
            self.config.use_8bit = False
            self.config.use_4bit = False
            return

        # VRAM 체크 - 4bit 우선순위 높임
        available_vram = self.hardware_info.gpu_memory_free
        
        # 사용자가 4bit를 원하면 VRAM이 부족해도 4bit 강제 적용
        if self.config.use_4bit:
            logger.info(f"4bit 양자화 사용자 설정 - 강제 적용 (VRAM: {available_vram:.1f}GB)")
            self.config.use_8bit = False  # 8bit 비활성화
            if available_vram < 4:
                self.config.max_length = min(self.config.max_length, 256)
                logger.warning("VRAM 매우 부족 - max_length 256으로 제한")
            return

        # 4bit 설정이 없는 경우에만 자동 최적화
        if available_vram < 4:
            logger.warning(f"VRAM 부족 ({available_vram:.1f}GB). 4bit 모드 강제 적용")
            self.config.use_4bit = True
            self.config.use_8bit = False
            self.config.max_length = min(self.config.max_length, 256)

        elif available_vram < 8:
            logger.info(f"VRAM 제한적 ({available_vram:.1f}GB). 8bit 모드 권장")
            self.config.use_8bit = True
            self.config.max_length = min(self.config.max_length, 384)

        # 배치 크기 조정 (추론용)
        if available_vram < 6:
            recommended_batch = 1
        elif available_vram < 8:
            recommended_batch = 2
        else:
            recommended_batch = 4

        logger.info(f"권장 배치 크기: {recommended_batch}")

    def get_quantization_config(self) -> Optional[BitsAndBytesConfig]:
        """양자화 설정 생성"""
        if not torch.cuda.is_available():
            return None

        if self.config.use_4bit:
            logger.info("4bit 양자화 설정")
            return BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16
            )
        elif self.config.use_8bit:
            logger.info("8bit 양자화 설정")
            return BitsAndBytesConfig(
                load_in_8bit=True,
                bnb_8bit_use_double_quant=True,
                bnb_8bit_quant_type="nf8",
                bnb_8bit_compute_dtype=torch.bfloat16
            )
        else:
            logger.info("양자화 없음 (Full precision)")
            return None

    def get_lora_config(self) -> LoraConfig:
        """LoRA 설정 생성"""
        return LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            inference_mode=False,
            r=self.config.lora_rank,
            lora_alpha=self.config.lora_alpha,
            lora_dropout=self.config.lora_dropout,
            target_modules=[
                "q_proj", "v_proj", "k_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj"  # LLaMA 계열용
            ],
            bias="none",
            fan_in_fan_out=False
        )

    def get_model_kwargs(self) -> Dict:
        """모델 로드용 kwargs 생성"""
        kwargs = {
            "torch_dtype": torch.bfloat16,
            "device_map": "auto",
            "trust_remote_code": True,
            "low_cpu_mem_usage": True
        }

        # 양자화 설정 추가
        quantization_config = self.get_quantization_config()
        if quantization_config:
            kwargs["quantization_config"] = quantization_config

        return kwargs

    def get_generation_kwargs(self) -> Dict:
        """텍스트 생성용 kwargs"""
        return {
            "max_length": self.config.max_length,
            "max_new_tokens": min(200, self.config.max_length // 2),
            "temperature": self.config.temperature,
            "do_sample": self.config.do_sample,
            "top_p": 0.9,
            "top_k": 50,
            "repetition_penalty": 1.1,
            "pad_token_id": None,  # 토크나이저에서 설정
            "eos_token_id": None,  # 토크나이저에서 설정
            "use_cache": True
        }

    def monitor_memory_usage(self) -> Dict[str, float]:
        """메모리 사용량 모니터링"""
        memory_info = {}

        # GPU 메모리
        if torch.cuda.is_available():
            memory_info["gpu_allocated"] = torch.cuda.memory_allocated() / (1024 ** 3)
            memory_info["gpu_reserved"] = torch.cuda.memory_reserved() / (1024 ** 3)
            memory_info["gpu_max_allocated"] = torch.cuda.max_memory_allocated() / (1024 ** 3)

            # 사용률 계산
            if self.hardware_info.gpu_memory_total > 0:
                memory_info["gpu_usage_percent"] = (
                        memory_info["gpu_allocated"] / self.hardware_info.gpu_memory_total * 100
                )

        # RAM 메모리
        ram = psutil.virtual_memory()
        memory_info["ram_used"] = ram.used / (1024 ** 3)
        memory_info["ram_percent"] = ram.percent

        return memory_info

    def clear_memory_cache(self):
        """메모리 캐시 정리"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            logger.info("GPU 캐시 정리 완료")

    def check_memory_limits(self) -> Tuple[bool, str]:
        """메모리 한계 체크"""
        memory_info = self.monitor_memory_usage()

        # GPU 메모리 체크
        if torch.cuda.is_available():
            gpu_usage = memory_info.get("gpu_usage_percent", 0)
            if gpu_usage > 90:
                return False, f"GPU 메모리 과사용 ({gpu_usage:.1f}%)"
            elif gpu_usage > 80:
                return True, f"GPU 메모리 높음 ({gpu_usage:.1f}%)"

        # RAM 메모리 체크
        ram_usage = memory_info.get("ram_percent", 0)
        if ram_usage > 90:
            return False, f"RAM 메모리 과사용 ({ram_usage:.1f}%)"
        elif ram_usage > 80:
            return True, f"RAM 메모리 높음 ({ram_usage:.1f}%)"

        return True, "메모리 사용량 정상"

    def get_optimal_batch_size(self, sequence_length: int = 512) -> int:
        """최적 배치 크기 계산"""
        if not torch.cuda.is_available():
            return 1

        available_memory = self.hardware_info.gpu_memory_free

        # 경험적 공식 (VRAM GB당 처리 가능한 시퀀스 수)
        if self.config.use_4bit:
            sequences_per_gb = 8
        elif self.config.use_8bit:
            sequences_per_gb = 4
        else:
            sequences_per_gb = 2

        # 시퀀스 길이 보정
        length_factor = 512 / sequence_length

        optimal_batch = max(1, int(available_memory * sequences_per_gb * length_factor))

        # 안전 마진 적용
        optimal_batch = int(optimal_batch * 0.8)

        logger.info(f"계산된 최적 배치 크기: {optimal_batch}")
        return optimal_batch

    def validate_config(self) -> Tuple[bool, list[str]]:
        """설정 유효성 검증"""
        warnings = []

        # 하드웨어 호환성 체크
        if not torch.cuda.is_available() and (self.config.use_8bit or self.config.use_4bit):
            warnings.append("GPU 없음. 양자화 설정이 무시됩니다")

        # VRAM 체크
        if torch.cuda.is_available():
            if self.hardware_info.gpu_memory_total < 4:
                warnings.append("VRAM 부족. 최소 4GB 권장")

            if not (self.config.use_8bit or self.config.use_4bit) and self.hardware_info.gpu_memory_total < 12:
                warnings.append("Full precision 모드에는 12GB+ VRAM 권장")

        # 설정 일관성 체크
        if self.config.use_8bit and self.config.use_4bit:
            warnings.append("8bit와 4bit 동시 설정. 4bit 우선 적용")
            self.config.use_8bit = False

        # LoRA 설정 체크
        if self.config.lora_rank > 64:
            warnings.append("LoRA rank 너무 높음. 메모리 부족 가능")

        is_valid = len(warnings) < 3  # 경고 3개 이상이면 유효하지 않음으로 판단

        return is_valid, warnings

    def print_config_summary(self):
        """설정 요약 출력"""
        print(f"""
=== 모델 설정 요약 ===
모델: {self.config.model_name}
디바이스: {self.device}
양자화: {'4bit' if self.config.use_4bit else '8bit' if self.config.use_8bit else 'None'}
최대 길이: {self.config.max_length}
LoRA Rank: {self.config.lora_rank}
온도: {self.config.temperature}

=== 하드웨어 정보 ===
GPU: {self.hardware_info.gpu_name}
VRAM: {self.hardware_info.gpu_memory_free:.1f}/{self.hardware_info.gpu_memory_total:.1f}GB
RAM: {self.hardware_info.ram_free:.1f}/{self.hardware_info.ram_total:.1f}GB
====================
""")


# 편의 함수들
def create_model_config_manager(model_config) -> ModelConfigManager:
    """모델 설정 관리자 생성"""
    return ModelConfigManager(model_config)


def check_hardware_compatibility(model_config) -> bool:
    """하드웨어 호환성 간단 체크"""
    manager = ModelConfigManager(model_config)
    is_valid, warnings = manager.validate_config()

    if warnings:
        for warning in warnings:
            logger.warning(warning)

    return is_valid