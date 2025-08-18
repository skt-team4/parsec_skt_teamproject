"""
SKT A.X 3.1 Lite 모델 래퍼 클래스
RTX 3060 Ti/4090 최적화, 메모리 관리 포함
"""

import os
import torch
from transformers import (
    AutoTokenizer, AutoModelForCausalLM,
    GenerationConfig, StoppingCriteria, StoppingCriteriaList,
    BitsAndBytesConfig
)
from peft import get_peft_model, PeftModel
import logging
from typing import List, Dict, Optional, Tuple, Union
import time
import gc
import re
from pathlib import Path

from .models_config import ModelConfigManager
from src.data.data_structure import ChatbotResponse

logger = logging.getLogger(__name__)

class CustomStoppingCriteria(StoppingCriteria):
    """커스텀 정지 조건"""

    def __init__(self, stop_words: List[str], tokenizer):
        self.stop_words = stop_words
        self.tokenizer = tokenizer
        self.stop_token_ids = []

        # 정지 단어들을 토큰 ID로 변환
        for word in stop_words:
            token_ids = tokenizer.encode(word, add_special_tokens=False)
            self.stop_token_ids.extend(token_ids)

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        # 마지막 생성된 토큰이 정지 토큰인지 확인
        last_token = input_ids[0][-1].item()
        return last_token in self.stop_token_ids


class AXModel:
    """SKT A.X 3.1 Lite 모델 래퍼"""

    def __init__(self, model_config=None, config_manager: Optional[ModelConfigManager] = None, use_4bit: bool = True):
        """
        Args:
            model_config: ModelConfig 객체
            config_manager: ModelConfigManager (선택사항)
            use_4bit: 4비트 양자화 사용 여부
        """
        self.use_4bit = use_4bit
        
        # model_config가 없으면 기본 설정 사용
        if model_config is None:
            from utils.config import ModelConfig
            model_config = ModelConfig(
                model_name="skt/A.X-3.1-Light",
                use_4bit=use_4bit
            )
        
        self.config = model_config
        self.config_manager = config_manager or ModelConfigManager(model_config)

        # 모델 관련 변수
        self.tokenizer = None
        self.model = None
        self.peft_model = None
        self.generation_config = None

        # 성능 추적
        self.generation_stats = {
            "total_generations": 0,
            "total_time": 0.0,
            "avg_tokens_per_sec": 0.0
        }

        # A.X 3.1 Lite 특화 정지 단어
        self.ax_stop_words = [
            "사용자:", "User:", "AI:", "Assistant:",
            "###", "---", "[END]", "질문:", "답변:"
        ]

    def load_model(self, cache_dir: Optional[str] = None):
        """모델과 토크나이저 로드"""
        try:
            logger.info(f"A.X 3.1 Lite 모델 로딩 시작")
            start_time = time.time()

            # 토크나이저 로드
            self._load_tokenizer(cache_dir)

            # 모델 로드 (4-bit 양자화 적용)
            self._load_base_model(cache_dir)

            # Generation Config 설정
            self._setup_generation_config()

            # 메모리 체크
            memory_ok, memory_msg = self.config_manager.check_memory_limits()
            if not memory_ok:
                logger.warning(f"메모리 주의: {memory_msg}")

            load_time = time.time() - start_time
            logger.info(f"A.X 3.1 Lite 로딩 완료: {load_time:.2f}초")

            # GPU 메모리 사용량 출력
            if torch.cuda.is_available():
                memory_used = torch.cuda.memory_allocated() / 1024**3
                logger.info(f"GPU 메모리 사용량: {memory_used:.2f}GB")

        except Exception as e:
            logger.error(f"A.X 3.1 Lite 로딩 실패: {e}")
            raise

    def _load_tokenizer(self, cache_dir: Optional[str] = None):
        """토크나이저 로드"""
        logger.info("A.X 3.1 Lite 토크나이저 로딩...")
        
        # 캐시 디렉토리 설정
        if cache_dir is None:
            cache_dir = "./cache"
        
        # tokenizer_config.json에 명시된 대로 GPT2Tokenizer 사용
        from transformers import GPT2Tokenizer
        self.tokenizer = GPT2Tokenizer.from_pretrained(
            'skt/A.X-3.1-Light',
            cache_dir=cache_dir,
            trust_remote_code=True
        )

        # 패딩 토큰 설정
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            logger.info("패딩 토큰을 EOS 토큰으로 설정")

        logger.info(f"A.X 토크나이저 로드 완료: {len(self.tokenizer)} 토큰")

    def _load_base_model(self, cache_dir: Optional[str] = None):
        """기본 모델 로드 (4-bit 양자화 적용)"""
        logger.info("A.X 3.1 Lite 모델 로딩... (4-bit 양자화)")

        # 4-bit 양자화 설정
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type='nf4',
            bnb_4bit_compute_dtype=torch.float16,
            llm_int8_enable_fp32_cpu_offload=True
        )

        # 모델 로드 kwargs
        import platform
        
        # OS에 따라 attention 구현 선택
        if platform.system() == "Linux":
            # GCP/Linux 서버에서는 Flash Attention 2 사용
            attn_impl = "flash_attention_2"
            logger.info("Linux 감지: Flash Attention 2 사용 시도")
        else:
            # Windows 개발 환경에서는 SDPA 사용
            attn_impl = "sdpa"
            logger.info("Windows 감지: SDPA 사용")
        
        model_kwargs = {
            'trust_remote_code': True,
            'quantization_config': bnb_config,
            'device_map': 'auto',
            'low_cpu_mem_usage': True,
            'torch_dtype': torch.float16,
            'attn_implementation': attn_impl
        }
        
        if cache_dir:
            model_kwargs["cache_dir"] = cache_dir

        # RTX 3060 Ti 환경에서 메모리 제한
        if torch.cuda.is_available():
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            if gpu_memory <= 8:  # 8GB 이하 GPU
                model_kwargs['max_memory'] = {0: '5GB'}
                logger.info("GPU 메모리 제한 적용: 5GB")

        self.model = AutoModelForCausalLM.from_pretrained(
            'skt/A.X-3.1-Light',
            **model_kwargs
        )

        # 모델을 evaluation 모드로 설정
        self.model.eval()
        logger.info("A.X 3.1 Lite 모델 로드 완료")

    def _setup_generation_config(self):
        """텍스트 생성 설정"""
        # A.X 3.1 Lite 특화 생성 설정
        generation_kwargs = {
            'max_new_tokens': 150,
            'do_sample': True,
            'temperature': 0.7,
            'top_p': 0.9,
            'top_k': 50,
            'repetition_penalty': 1.1,
            'pad_token_id': self.tokenizer.pad_token_id,
            'eos_token_id': self.tokenizer.eos_token_id
        }

        self.generation_config = GenerationConfig(**generation_kwargs)
        logger.info("A.X Generation Config 설정 완료")

    def setup_lora(self, lora_path: Optional[str] = None):
        """LoRA 어댑터 설정"""
        try:
            if lora_path and Path(lora_path).exists():
                # 기존 LoRA 어댑터 로드
                logger.info(f"LoRA 어댑터 로드: {lora_path}")
                self.peft_model = PeftModel.from_pretrained(
                    self.model,
                    lora_path,
                    is_trainable=False
                )
            else:
                # 새 LoRA 어댑터 생성
                logger.info("새 LoRA 어댑터 생성")
                lora_config = self.config_manager.get_lora_config()
                self.peft_model = get_peft_model(self.model, lora_config)

            logger.info("LoRA 설정 완료")

        except Exception as e:
            logger.error(f"LoRA 설정 실패: {e}")
            # LoRA 없이도 동작하도록 fallback
            self.peft_model = None

    def generate(self, prompt: str, **kwargs):
        """
        generate_text 메서드의 래퍼 (호환성을 위해)
        NLU 모듈들이 generate()를 호출하므로 이를 generate_text()로 전달
        """
        # kwargs에서 generate_text가 받는 파라미터만 추출
        valid_params = ['max_new_tokens', 'temperature', 'stop_words']
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
        
        # generate_text 호출
        result = self.generate_text(prompt, **filtered_kwargs)
        
        # NLU가 기대하는 문자열 형태로 반환
        if isinstance(result, dict):
            return result.get('text', '')
        return result

    def generate_response(self, extracted_info=None, user_profile=None, conversation_context=None, rag_context="", recommendations=None, **kwargs):
        """
        IntegratedPipeline과 호환성을 위한 generate_response 메서드
        ExtractedInfo 기반으로 응답 생성
        """
        from src.data.data_structure import ChatbotResponse
        
        # ExtractedInfo에서 텍스트 추출
        if extracted_info:
            user_text = extracted_info.raw_text
            intent = getattr(extracted_info, 'intent', None)
            entities = getattr(extracted_info, 'entities', None)
        else:
            user_text = kwargs.get('prompt', '')
            intent = None
            entities = None
        
        # 프롬프트 구성
        prompt_parts = []
        
        # 추천 결과 정보 추가 (최우선)
        if recommendations and len(recommendations) > 0:
            rec_text = "실제 추천할 가게:\n"
            for i, rec in enumerate(recommendations[:3], 1):
                shop_name = rec.get('shop_name', '알 수 없음')
                category = rec.get('category', '기타')
                rec_text += f"{i}. {shop_name} ({category})\n"
            prompt_parts.append(rec_text)
        
        # RAG 컨텍스트 추가
        if rag_context and rag_context.strip():
            prompt_parts.append(f"참고 정보:\n{rag_context}\n")
        
        # 사용자 프로필 정보 추가
        if user_profile and isinstance(user_profile, dict):
            profile_info = []
            if user_profile.get('preferred_cuisines'):
                profile_info.append(f"선호 음식: {', '.join(user_profile['preferred_cuisines'])}")
            if user_profile.get('age_group'):
                profile_info.append(f"연령대: {user_profile['age_group']}")
            if profile_info:
                prompt_parts.append(f"사용자 정보: {', '.join(profile_info)}\n")
        
        # 시스템 컨텍스트 추가 (페르소나 정보, 설정 정보 등)
        if user_profile and user_profile.get('system_context'):
            prompt_parts.insert(0, user_profile['system_context'] + "\n")
            logger.info("시스템 컨텍스트 추가됨")
        
        # 대화 맥락 추가 (최근 2-3턴)
        if conversation_context and isinstance(conversation_context, list):
            recent_context = conversation_context[-6:]  # 최근 3턴 (user+assistant 각각)
            context_str = []
            for ctx in recent_context:
                if isinstance(ctx, dict):
                    # ConversationManager 형식 지원
                    if ctx.get('role') and ctx.get('content'):
                        if ctx['role'] == 'user':
                            context_str.append(f"사용자: {ctx['content']}")
                        elif ctx['role'] == 'assistant':
                            context_str.append(f"아이얌: {ctx['content']}")
                        elif ctx['role'] == 'system' and 'system_context' not in str(ctx['content']):
                            # system 역할이지만 system_context가 아닌 경우만 추가
                            continue
                    # 기존 형식도 지원
                    elif ctx.get('user'):
                        context_str.append(f"사용자: {ctx['user']}")
                    elif ctx.get('bot'):
                        context_str.append(f"아이얌: {ctx['bot']}")
            if context_str:
                context_text = f"대화 맥락:\n{chr(10).join(context_str)}\n"
                prompt_parts.append(context_text)
                logger.info(f"대화 맥락 추가됨: {len(context_str)}개 메시지")
            else:
                logger.warning("대화 맥락이 비어있음")
        
        # 메인 지시사항 (의도에 따라 다르게)
        from src.data.data_structure import IntentType
        
        # extracted_info에서 의도 가져오기
        intent = extracted_info.intent if extracted_info else IntentType.UNKNOWN
        
        # 의도별 프롬프트 생성
        if intent in [IntentType.CHITCHAT, IntentType.GREETING, IntentType.GENERAL_CHAT]:
            # 일반 대화/인사말
            prompt_parts.append(f"""당신은 아이얌(AIYAM) 친구 챗봇입니다. 10대 청소년과 자연스럽게 대화하세요.

현재 사용자 메시지: "{user_text}"

중요: 위의 '대화 맥락'을 반드시 참고하여 이전 대화의 흐름에 맞게 응답하세요!
- 같은 질문을 반복하지 마세요
- 사용자가 "재미없음"이라고 했으면 위로나 다른 활동 제안
- 대화가 이어지도록 자연스럽게 응답

응답 가이드:
- 친근하고 자연스러운 대화
- 2-3문장으로 짧게
- 캐주얼한 반말 사용 (~야, ~지 등)
- ㅋㅋ 이모티콘 사용 금지

응답 후 반드시 다음과 같은 JSON 형식의 메타데이터를 추가하세요:
```json
{{"context_type": "general_chat", "sentiment": "긍정적/부정적/중립적"}}
```

아이얌:""")
        elif intent == IntentType.THANKS:
            # 감사 인사
            prompt_parts.append(f"""당신은 아이얌(AIYAM) 친구 챗봇입니다. 감사 인사에 자연스럽게 응답하세요.

사용자: "{user_text}"

아이얌:""")
        elif intent == IntentType.GOODBYE:
            # 작별 인사
            prompt_parts.append(f"""당신은 아이얌(AIYAM) 친구 챗봇입니다. 작별 인사를 자연스럽게 하세요.

사용자: "{user_text}"

아이얌:""")
        else:
            # 음식 추천 관련
            if recommendations:
                # 실제 추천 결과가 있을 때
                categories = list(set([r.get('category', '') for r in recommendations[:3] if r.get('category')]))
                category_text = ', '.join(categories) if categories else '다양한 음식'
                
                prompt_parts.append(f"""당신은 아이얌(AIYAM) 맛집 추천 챗봇입니다. 10대 청소년과 대화하듯 짧고 캐주얼하게 답변하세요.

사용자: "{user_text}"

실제 추천된 카테고리: {category_text}

응답 가이드:
- 위에 언급된 카테고리를 자연스럽게 언급
- 2-3문장으로 짧게
- 캐주얼한 반말 사용 (~야, ~지 등)
- "아래 추천 리스트 확인해봐" 같은 안내 포함
- JSON 메타데이터나 코드 절대 포함하지 말 것

아이얌:""")
            else:
                # 추천 결과가 없을 때 (폴백)
                prompt_parts.append(f"""당신은 아이얌(AIYAM) 맛집 추천 챗봇입니다. 10대 청소년과 대화하듯 짧고 캐주얼하게 답변하세요.

사용자: "{user_text}"

응답 가이드:
- 2-3문장으로 짧게
- 캐주얼한 반말 사용 (~야, ~지 등)
- 일반적인 음식 추천 응답

아이얌:""")
        
        final_prompt = "\n".join(prompt_parts)
        
        try:
            # A.X 3.1 Lite로 텍스트 생성
            result = self.generate_text(
                prompt=final_prompt,
                max_new_tokens=kwargs.get('max_new_tokens', 150),
                temperature=kwargs.get('temperature', 0.7)
            )
            
            response_text = result.get('text', '') if isinstance(result, dict) else str(result)
            
            # 디버깅 로그 추가
            logger.debug(f"[NLG] 원본 응답 (처리 전): {response_text[:200]}")
            
            # 맥락 정보 추출 (JSON 기반으로 개선)
            context_metadata = {}
            try:
                import re
                import json
                
                # JSON 코드 블록 패턴 매칭 (```json ... ```)
                json_match = re.search(r'```json\s*\n?(.*?)\n?```', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
                    try:
                        context_metadata = json.loads(json_str)
                        # 응답에서 JSON 블록 제거 (더 확실하게)
                        response_text = re.sub(r'```json.*?```', '', response_text, flags=re.DOTALL).strip()
                        # JSON 관련 텍스트도 제거
                        response_text = re.sub(r'응답 후 반드시.*메타데이터를 추가하세요[:\.]?', '', response_text, flags=re.DOTALL).strip()
                        logger.info(f"[DEBUG] JSON 메타데이터 추출 성공: {context_metadata}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON 메타데이터 파싱 실패: {e}, 원본: {json_str}")
                        context_metadata = {}
                
                # 폴백: 기존 대괄호 방식도 지원
                elif '[CONTEXT_TYPE:' in response_text:
                    # CONTEXT_TYPE 추출
                    context_type_match = re.search(r'\[CONTEXT_TYPE:\s*([^\]]+)\]', response_text)
                    if context_type_match:
                        context_metadata['context_type'] = context_type_match.group(1).strip()
                        response_text = re.sub(r'\[CONTEXT_TYPE:[^\]]+\]', '', response_text).strip()
                    
                    # CONTEXT_DETAIL 추출
                    context_detail_match = re.search(r'\[CONTEXT_DETAIL:\s*([^\]]+)\]', response_text)
                    if context_detail_match:
                        detail = context_detail_match.group(1).strip()
                        if ',' in detail:
                            context_metadata['categories'] = [c.strip() for c in detail.split(',')]
                        else:
                            context_metadata['detail'] = detail
                        response_text = re.sub(r'\[CONTEXT_DETAIL:[^\]]+\]', '', response_text).strip()
                    logger.info(f"[DEBUG] 폴백 메타데이터 추출: {context_metadata}")
                
            except Exception as e:
                logger.warning(f"맥락 메타데이터 추출 중 오류: {e}")
                context_metadata = {}
            
            # ChatbotResponse 객체로 반환
            return ChatbotResponse(
                text=response_text,
                recommendations=[],  # 추천은 IntegratedPipeline에서 별도 처리
                metadata={
                    'generation_model': 'A.X-3.1-Light',
                    'prompt_length': len(final_prompt),
                    'response_length': len(response_text),
                    'generation_time': result.get('generation_time', 0) if isinstance(result, dict) else 0,
                    'context_metadata': context_metadata  # 맥락 메타데이터 추가
                }
            )
            
        except Exception as e:
            logger.error(f"A.X 3.1 Lite 응답 생성 실패: {e}")
            # 폴백 응답
            return ChatbotResponse(
                text="죄송합니다. 일시적인 오류가 발생했습니다. 다시 시도해 주세요.",
                recommendations=[],
                metadata={'error': str(e), 'fallback': True}
            )
    
    def generate_text(
        self,
        prompt: str,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop_words: Optional[List[str]] = None
    ) -> Dict[str, Union[str, float, int]]:
        """텍스트 생성"""
        if self.model is None:
            raise RuntimeError("모델이 로드되지 않음. load_model()을 먼저 호출하세요")

        start_time = time.time()

        try:
            # 입력 토큰화
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.config.max_length - (max_new_tokens or 150),
                return_token_type_ids=False
            )

            if 'token_type_ids' in inputs:
                del inputs['token_type_ids']

            # GPU로 이동 (모델이 있는 디바이스로)
            if torch.cuda.is_available():
                device = next(self.model.parameters()).device
                inputs = {k: v.to(device) for k, v in inputs.items()}

            # 생성 설정 조정
            generation_config = self.generation_config
            if max_new_tokens:
                generation_config.max_new_tokens = max_new_tokens
            if temperature:
                generation_config.temperature = temperature

            # 정지 조건 설정
            stopping_criteria = None
            if stop_words:
                combined_stop_words = self.ax_stop_words + stop_words
                stopping_criteria = StoppingCriteriaList([
                    CustomStoppingCriteria(combined_stop_words, self.tokenizer)
                ])

            # 모델 선택 (LoRA 있으면 LoRA 사용)
            model_to_use = self.peft_model if self.peft_model else self.model

            # 텍스트 생성
            with torch.no_grad():
                generate_kwargs = {
                    'input_ids': inputs['input_ids'],
                    'generation_config': generation_config,
                    'return_dict_in_generate': True,
                    'output_scores': True
                }

                # attention_mask가 있으면 추가
                if 'attention_mask' in inputs:
                    generate_kwargs['attention_mask'] = inputs['attention_mask']

                # stopping_criteria가 있으면 추가
                if stopping_criteria:
                    generate_kwargs['stopping_criteria'] = stopping_criteria

                outputs = model_to_use.generate(**generate_kwargs)

            # 결과 디코딩
            generated_tokens = outputs.sequences[0][inputs['input_ids'].shape[1]:]
            generated_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)

            # 통계 업데이트
            generation_time = time.time() - start_time
            num_tokens = len(generated_tokens)

            self._update_stats(generation_time, num_tokens)

            # A.X 특화 후처리
            cleaned_text = self._postprocess_ax_text(generated_text)

            result = {
                "text": cleaned_text,
                "raw_text": generated_text,
                "tokens_generated": num_tokens,
                "generation_time": generation_time,
                "tokens_per_second": num_tokens / generation_time if generation_time > 0 else 0,
                "prompt_tokens": inputs['input_ids'].shape[1]
            }

            logger.debug(f"A.X 생성 완료: {num_tokens}토큰, {generation_time:.2f}초")

            return result

        except Exception as e:
            logger.error(f"A.X 텍스트 생성 실패: {e}")
            return {
                "text": "",
                "error": str(e),
                "generation_time": time.time() - start_time
            }

    def _postprocess_ax_text(self, text: str) -> str:
        """A.X 3.1 Lite 특화 텍스트 후처리"""
        # 불필요한 공백 제거
        cleaned = text.strip()

        # A.X 특화 정지 단어 제거
        for stop_word in self.ax_stop_words:
            if stop_word in cleaned:
                cleaned = cleaned.split(stop_word)[0].strip()

        # JSON 메타데이터 완전 제거 (더 강력한 패턴)
        # 1. 다양한 JSON 패턴들 제거
        json_patterns = [
            r'["\']?type["\']?\s*:\s*["\']?[^"\'}\]]*["\']?',
            r'["\']?coordinates["\']?\s*:\s*["\']?[^"\'}\]]*["\']?',
            r'["\']?detail["\']?\s*:\s*["\']?[^"\'}\]]*["\']?',
            r'["\']?context_type["\']?\s*:\s*["\']?[^"\'}\]]*["\']?',
            r'["\']?context_["\']?\s*:\s*["\']?[^"\'}\]]*["\']?',
            r'["\']?categories["\']?\s*:\s*\[[^\]]*\]',
            r'["\']?dish["\']?\s*:\s*["\']?[^"\'}\]]*["\']?',
            r'["\']?area["\']?\s*:\s*["\']?[^"\'}\]]*["\']?',
            r'["\']?location_based_recommendation["\']?',
            r'["\']?location_based["\']?',  # location_based 단독 제거
            r'["\']?sentiment["\']?\s*:\s*["\']?[^"\'}\]]*["\']?',  # sentiment 제거
            r'["\']?metadata["\']?\s*:\s*["\']?[^"\'}\]]*["\']?',  # metadata 제거
        ]
        
        for pattern in json_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # 2. JSON 구조 제거
        cleaned = re.sub(r'```json.*?```', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'\{[^}]*\}', '', cleaned)  # 모든 중괄호 블록 제거
        
        # 3. 잔재 제거
        cleaned = re.sub(r'^\s*[}\]"\',:.]+\s*', '', cleaned)  # 시작 부분 잔재
        cleaned = re.sub(r'\s*[}\]"\':,]+\s*(\*+)?', ' ', cleaned)  # 중간 잔재
        cleaned = re.sub(r'[{}]', '', cleaned)  # 남은 중괄호
        cleaned = re.sub(r':\s*\.', '.', cleaned)  # ": ." 패턴
        cleaned = re.sub(r'^\s*\.\s*', '', cleaned)  # 시작 부분의 마침표
        
        # 4. "추천:" 으로 시작하는 불완전한 문장 제거
        if cleaned.startswith('추천:'):
            cleaned = cleaned[3:].strip()
        
        # 5. 나비얌 특화 후처리
        cleaned = re.sub(r'#', '', cleaned)  
        cleaned = re.sub(r'\[CONTEXT_[A-Z]+:[^\]]*\]', '', cleaned)
        cleaned = re.sub(r'<[^>]*>', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)  # 중복 공백
        cleaned = cleaned.strip()

        # 6. 최종 정리
        if cleaned:
            # ** 로 시작하면 제거
            cleaned = re.sub(r'^\*+\s*', '', cleaned)
            # 빈 문자열이 아니고 문장 부호가 없으면 추가
            if cleaned and len(cleaned) > 2 and not cleaned[-1] in '.!?':
                cleaned += '.'
            # 너무 짧은 응답은 기본 메시지로
            if len(cleaned) < 5:
                cleaned = "아래 추천 리스트를 확인해봐!"

        return cleaned

    def _update_stats(self, generation_time: float, num_tokens: int):
        """성능 통계 업데이트"""
        self.generation_stats["total_generations"] += 1
        self.generation_stats["total_time"] += generation_time

        if self.generation_stats["total_time"] > 0:
            total_tokens = self.generation_stats["total_generations"] * num_tokens
            self.generation_stats["avg_tokens_per_sec"] = (
                total_tokens / self.generation_stats["total_time"]
            )

    def get_embeddings(self, text: str) -> torch.Tensor:
        """텍스트 임베딩 추출"""
        if self.model is None:
            raise RuntimeError("모델이 로드되지 않음")

        inputs = self.tokenizer(text, return_tensors="pt", truncation=True)
        if torch.cuda.is_available():
            device = next(self.model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs, output_hidden_states=True)
            # 마지막 레이어의 평균 풀링
            embeddings = outputs.hidden_states[-1].mean(dim=1)

        return embeddings

    def save_lora_adapter(self, save_path: str):
        """LoRA 어댑터 저장"""
        if self.peft_model is None:
            logger.warning("저장할 LoRA 어댑터 없음")
            return

        save_dir = Path(save_path)
        save_dir.mkdir(parents=True, exist_ok=True)

        self.peft_model.save_pretrained(save_dir)
        logger.info(f"LoRA 어댑터 저장: {save_dir}")

    def cleanup_memory(self):
        """메모리 정리"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        gc.collect()
        logger.info("메모리 정리 완료")

    def get_model_info(self) -> Dict:
        """모델 정보 반환"""
        info = {
            "model_name": "skt/A.X-3.1-Light",
            "model_type": "A.X 3.1 Lite",
            "device": str(next(self.model.parameters()).device) if self.model else "None",
            "quantization": "4-bit (nf4)",
            "lora_enabled": self.peft_model is not None,
            "generation_stats": self.generation_stats.copy()
        }

        if self.model:
            # 양자화된 모델은 정확한 파라미터 수 계산이 어려움
            info["model_size"] = "7B (quantized to ~4GB)"
            info["optimization"] = "4-bit quantization + CPU offloading"

        return info

    def benchmark_generation(self, test_prompts: List[str], num_runs: int = 3) -> Dict:
        """A.X 3.1 Lite 생성 성능 벤치마크"""
        if not test_prompts:
            test_prompts = [
                "10살 아이가 좋아할 치킨집 추천해주세요.",
                "2만원으로 가족이 먹을 수 있는 음식점 알려주세요.",
                "매운 걸 못 먹는 아이를 위한 메뉴 추천해주세요."
            ]

        results = []

        for prompt in test_prompts:
            prompt_results = []

            for _ in range(num_runs):
                result = self.generate_text(prompt, max_new_tokens=80)
                if "error" not in result:
                    prompt_results.append({
                        "tokens_per_second": result["tokens_per_second"],
                        "generation_time": result["generation_time"],
                        "tokens_generated": result["tokens_generated"]
                    })

            if prompt_results:
                avg_tps = sum(r["tokens_per_second"] for r in prompt_results) / len(prompt_results)
                avg_time = sum(r["generation_time"] for r in prompt_results) / len(prompt_results)

                results.append({
                    "prompt": prompt[:50] + "...",
                    "avg_tokens_per_second": avg_tps,
                    "avg_generation_time": avg_time,
                    "runs": len(prompt_results)
                })

        return {
            "benchmark_results": results,
            "overall_avg_tps": sum(r["avg_tokens_per_second"] for r in results) / len(results) if results else 0,
            "model_info": self.get_model_info()
        }

    def __del__(self):
        """소멸자에서 메모리 정리"""
        try:
            self.cleanup_memory()
        except:
            pass


# 편의 함수들
def create_ax_model(model_config, cache_dir: Optional[str] = None) -> AXModel:
    """A.X 3.1 Lite 모델 생성 및 로드"""
    model = AXModel(model_config)
    model.load_model(cache_dir)
    return model


def quick_ax_generate(model_config, prompt: str, cache_dir: Optional[str] = None) -> str:
    """빠른 텍스트 생성 (테스트용)"""
    model = create_ax_model(model_config, cache_dir)
    result = model.generate_text(prompt)
    model.cleanup_memory()
    return result.get("text", "")