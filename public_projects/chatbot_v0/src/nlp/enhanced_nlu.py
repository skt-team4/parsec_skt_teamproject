"""
기존 NLU를 LLM으로 향상시킨 하이브리드 NLU
패턴 매칭 + LLM 기반 자연어 이해 결합
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
import openai
import os
from enum import Enum

from .nlu import NaviyamNLU, ExtractedInfo, ExtractedEntity, IntentType, ConfidenceLevel
from .llm_entity_extractor import LLMEntityExtractor
from src.data.data_structure import UserInput

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """LLM 제공자"""
    OPENAI = "openai"
    LOCAL_MODEL = "local"
    MOCK = "mock"


@dataclass
class EnhancedExtractionResult:
    """향상된 추출 결과"""
    intent: IntentType
    entities: ExtractedEntity
    confidence: float
    confidence_level: ConfidenceLevel
    raw_text: str
    llm_used: bool
    llm_confidence: Optional[float]
    pattern_confidence: Optional[float]
    extraction_method: str  # "pattern_only", "llm_only", "hybrid"
    reasoning: Optional[str]


class OpenAIEntityExtractor:
    """OpenAI API 기반 엔티티 추출기"""
    
    def __init__(self, api_key: str = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        
        if self.api_key:
            openai.api_key = self.api_key
        else:
            logger.warning("OpenAI API 키가 설정되지 않았습니다.")
    
    def extract_entities(self, user_input: str) -> Dict[str, Any]:
        """OpenAI로 엔티티 추출"""
        if not self.api_key:
            raise ValueError("OpenAI API 키가 필요합니다.")
        
        prompt = self._build_extraction_prompt(user_input)
        
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "당신은 한국어 음식 관련 텍스트에서 정보를 추출하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            content = response.choices[0].message.content
            return self._parse_openai_response(content)
            
        except Exception as e:
            logger.error(f"OpenAI API 호출 실패: {e}")
            raise
    
    def _build_extraction_prompt(self, user_input: str) -> str:
        """OpenAI용 추출 프롬프트"""
        return f"""
다음 사용자 입력에서 음식 추천과 관련된 정보를 JSON 형태로 추출해주세요:

사용자 입력: "{user_input}"

추출할 정보와 예시:
1. location (위치): 
   - "부평에서" → "부평"
   - "성수동 맛집" → "성수동" 
   - "강남역 주변" → "강남역"
   - "우리 동네" → "현재위치"
   
2. food_type (음식 종류):
   - "치킨 먹고 싶어" → "치킨"
   - "김치찌개나 된장찌개" → "한식-찌개"
   - "양념치킨" → "치킨-양념"
   - "이탈리안 파스타" → "양식-파스타"
   
3. budget (예산, 원 단위):
   - "1만원" → 10000
   - "1만5천원" → 15000
   - "저렴한" → 7000 (추정)
   - "학생 용돈으로" → 6000 (추정)
   
4. companions (동반자):
   - "친구랑" → ["친구"]
   - "혼자" → ["혼자"] 
   - "가족끼리" → ["가족"]
   
5. dining_context (식사 상황):
   - "점심" → "점심"
   - "야식" → "야식"
   - "회식" → "회식"
   - "데이트" → "데이트"
   
6. special_requirements (특별 요구사항):
   - "배달 가능한" → ["배달"]
   - "빠른" → ["빠른서비스"]
   - "매운거" → ["매운맛"]
   - "혼밥하기 좋은" → ["혼밥친화적"]

응답은 반드시 다음 JSON 형태로만 제공하고, 다른 설명은 추가하지 마세요:
{{
  "location": "추출된 위치 또는 null",
  "food_type": "추출된 음식 타입 또는 null",
  "budget": 숫자 또는 null,
  "companions": ["배열"] 또는 null,
  "dining_context": "식사 상황 또는 null",
  "special_requirements": ["배열"] 또는 null,
  "confidence": 0.0~1.0 사이 값,
  "reasoning": "추출 근거 한 줄 설명"
}}
"""
    
    def _parse_openai_response(self, content: str) -> Dict[str, Any]:
        """OpenAI 응답 파싱"""
        try:
            # JSON 블록 추출
            if '```json' in content:
                json_start = content.find('```json') + 7
                json_end = content.find('```', json_start)
                json_str = content[json_start:json_end].strip()
            elif content.strip().startswith('{'):
                json_str = content.strip()
            else:
                # JSON을 찾아서 추출
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("JSON 형태를 찾을 수 없음")
            
            result = json.loads(json_str)
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"OpenAI 응답 JSON 파싱 실패: {e}, 응답: {content}")
            return {"confidence": 0.2, "reasoning": "파싱 실패"}
        except Exception as e:
            logger.error(f"OpenAI 응답 처리 실패: {e}")
            return {"confidence": 0.1, "reasoning": f"오류: {e}"}


class EnhancedNLU(NaviyamNLU):
    """LLM으로 향상된 NLU"""
    
    def __init__(self, nlu_config=None, llm_provider: LLMProvider = LLMProvider.OPENAI, 
                 openai_api_key: str = None, local_model=None):
        # 기본 NLU 초기화
        super().__init__(nlu_config, use_preprocessor=True, model=local_model)
        
        self.llm_provider = llm_provider
        
        # LLM 설정
        if llm_provider == LLMProvider.OPENAI:
            try:
                self.llm_extractor = OpenAIEntityExtractor(openai_api_key)
                self.llm_available = True
            except Exception as e:
                logger.warning(f"OpenAI 설정 실패: {e}")
                self.llm_available = False
                self.llm_extractor = None
        elif llm_provider == LLMProvider.LOCAL_MODEL and local_model:
            self.llm_extractor = LLMEntityExtractor(local_model)
            self.llm_available = True
        else:
            self.llm_available = False
            self.llm_extractor = None
        
        # 성능 통계
        self.extraction_stats = {
            'total_requests': 0,
            'llm_success': 0,
            'pattern_fallback': 0,
            'hybrid_success': 0
        }
    
    def extract_info_enhanced(self, user_input: Any) -> EnhancedExtractionResult:
        """향상된 정보 추출 (메인 인터페이스)"""
        self.extraction_stats['total_requests'] += 1
        
        # 텍스트 추출
        if hasattr(user_input, 'text'):
            text = user_input.text
            user_id = getattr(user_input, 'user_id', None)
        else:
            text = str(user_input)
            user_id = None
        
        # 1단계: 기존 패턴 기반 NLU
        pattern_result = super().extract_intent_and_entities(text, user_id)
        
        # 2단계: LLM 보강 시도
        llm_result = None
        llm_confidence = None
        extraction_method = "pattern_only"
        reasoning = "패턴 매칭만 사용"
        
        if self.llm_available and self.llm_extractor:
            try:
                if isinstance(self.llm_extractor, OpenAIEntityExtractor):
                    llm_data = self.llm_extractor.extract_entities(text)
                else:
                    llm_extraction = self.llm_extractor.extract_entities_comprehensive(text)
                    llm_data = llm_extraction.entities
                    llm_data['confidence'] = llm_extraction.confidence
                    llm_data['reasoning'] = llm_extraction.reasoning
                
                llm_confidence = llm_data.get('confidence', 0.5)
                reasoning = llm_data.get('reasoning', "LLM 분석 완료")
                
                # 3단계: 하이브리드 결합
                enhanced_entities = self._merge_pattern_llm_entities(
                    pattern_result.entities, llm_data
                )
                
                # 신뢰도 계산
                combined_confidence = self._calculate_hybrid_confidence(
                    pattern_result.confidence, llm_confidence, enhanced_entities
                )
                
                extraction_method = "hybrid"
                self.extraction_stats['hybrid_success'] += 1
                
            except Exception as e:
                logger.warning(f"LLM 보강 실패, 패턴 결과 사용: {e}")
                enhanced_entities = pattern_result.entities
                combined_confidence = pattern_result.confidence
                extraction_method = "pattern_only"
                self.extraction_stats['pattern_fallback'] += 1
        else:
            enhanced_entities = pattern_result.entities
            combined_confidence = pattern_result.confidence
            self.extraction_stats['pattern_fallback'] += 1
        
        # 신뢰도 레벨 재계산
        confidence_level = self._calculate_confidence_level(combined_confidence)
        
        return EnhancedExtractionResult(
            intent=pattern_result.intent,
            entities=enhanced_entities,
            confidence=combined_confidence,
            confidence_level=confidence_level,
            raw_text=text,
            llm_used=llm_result is not None,
            llm_confidence=llm_confidence,
            pattern_confidence=pattern_result.confidence,
            extraction_method=extraction_method,
            reasoning=reasoning
        )
    
    def _merge_pattern_llm_entities(self, pattern_entities: ExtractedEntity, 
                                  llm_data: Dict[str, Any]) -> ExtractedEntity:
        """패턴과 LLM 엔티티 병합"""
        merged = ExtractedEntity()
        
        # 위치 정보 병합 (LLM 우선, 더 상세한 경우)
        llm_location = llm_data.get('location')
        if llm_location and llm_location != 'null':
            merged.location_preference = llm_location
        else:
            merged.location_preference = pattern_entities.location_preference
        
        # 음식 타입 병합 (LLM이 더 구체적인 경우 우선)
        llm_food = llm_data.get('food_type')
        if llm_food and llm_food != 'null':
            # LLM이 더 상세한 정보를 제공하는 경우
            if '-' in llm_food or (pattern_entities.food_type and 
                                  len(llm_food) > len(pattern_entities.food_type)):
                merged.food_type = llm_food
            else:
                merged.food_type = pattern_entities.food_type or llm_food
        else:
            merged.food_type = pattern_entities.food_type
        
        # 예산 정보 병합 (LLM이 더 정확할 수 있음)
        llm_budget = llm_data.get('budget')
        if llm_budget and isinstance(llm_budget, (int, float)):
            merged.budget = int(llm_budget)
        else:
            merged.budget = pattern_entities.budget
        
        # 동반자 정보 병합
        llm_companions = llm_data.get('companions', [])
        if llm_companions and isinstance(llm_companions, list):
            # 두 결과 합치기
            pattern_companions = pattern_entities.companions or []
            merged.companions = list(set(pattern_companions + llm_companions))
        else:
            merged.companions = pattern_entities.companions
        
        # 시간 정보 (LLM에서 dining_context로 확장)
        dining_context = llm_data.get('dining_context')
        if dining_context:
            merged.time_preference = dining_context
        else:
            merged.time_preference = pattern_entities.time_preference
        
        # 메뉴 옵션 (기존 패턴 유지)
        merged.menu_options = pattern_entities.menu_options
        
        # 특별 요구사항 병합
        llm_requirements = llm_data.get('special_requirements', [])
        if llm_requirements and isinstance(llm_requirements, list):
            pattern_requirements = pattern_entities.special_requirements or []
            merged.special_requirements = list(set(pattern_requirements + llm_requirements))
        else:
            merged.special_requirements = pattern_entities.special_requirements
        
        return merged
    
    def _calculate_hybrid_confidence(self, pattern_conf: float, llm_conf: float,
                                   entities: ExtractedEntity) -> float:
        """하이브리드 신뢰도 계산"""
        if llm_conf is None:
            return pattern_conf
        
        # 기본 가중 평균 (LLM 60%, 패턴 40%)
        base_confidence = llm_conf * 0.6 + pattern_conf * 0.4
        
        # 엔티티 추출 성공도로 보너스
        entity_bonus = 0
        if entities.food_type:
            entity_bonus += 0.1
        if entities.budget:
            entity_bonus += 0.1
        if entities.location_preference:
            entity_bonus += 0.1
        if entities.companions:
            entity_bonus += 0.05
        
        final_confidence = min(base_confidence + entity_bonus, 1.0)
        return final_confidence
    
    def extract_with_context(self, user_input: str, conversation_history: List[str] = None,
                           user_id: str = None) -> EnhancedExtractionResult:
        """대화 맥락을 고려한 추출"""
        # 기본 추출
        result = self.extract_info_enhanced(user_input)
        
        # 대화 히스토리가 있으면 맥락 보정
        if conversation_history and len(conversation_history) > 0:
            result = self._enhance_with_context(result, conversation_history, user_input)
        
        return result
    
    def _enhance_with_context(self, result: EnhancedExtractionResult, 
                            history: List[str], current_input: str) -> EnhancedExtractionResult:
        """대화 맥락으로 결과 보정"""
        # 이전 대화에서 언급된 위치나 음식 타입 참조
        if not result.entities.location_preference:
            for prev_msg in reversed(history[-3:]):  # 최근 3개만
                prev_location = self.extract_location_from_history(prev_msg)
                if prev_location:
                    result.entities.location_preference = prev_location
                    result.reasoning += f" (이전 대화에서 위치 참조: {prev_location})"
                    break
        
        if not result.entities.food_type:
            for prev_msg in reversed(history[-3:]):
                prev_food = self.extract_food_from_history(prev_msg)
                if prev_food:
                    result.entities.food_type = prev_food
                    result.reasoning += f" (이전 대화에서 음식 타입 참조: {prev_food})"
                    break
        
        return result
    
    def extract_location_from_history(self, text: str) -> Optional[str]:
        """대화 히스토리에서 위치 추출"""
        if self.llm_available and isinstance(self.llm_extractor, OpenAIEntityExtractor):
            try:
                result = self.llm_extractor.extract_entities(text)
                return result.get('location')
            except:
                pass
        
        # 폴백으로 간단한 패턴 매칭
        import re
        location_pattern = r'(강남|홍대|신촌|명동|부평|성수|판교|이태원)'
        match = re.search(location_pattern, text)
        return match.group(1) if match else None
    
    def extract_food_from_history(self, text: str) -> Optional[str]:
        """대화 히스토리에서 음식 타입 추출"""
        if self.llm_available and isinstance(self.llm_extractor, OpenAIEntityExtractor):
            try:
                result = self.llm_extractor.extract_entities(text)
                return result.get('food_type')
            except:
                pass
        
        # 폴백으로 간단한 패턴 매칭
        food_keywords = ['치킨', '피자', '햄버거', '파스타', '한식', '중식', '일식']
        for food in food_keywords:
            if food in text:
                return food
        return None
    
    def get_extraction_statistics(self) -> Dict[str, Any]:
        """추출 통계 반환"""
        total = self.extraction_stats['total_requests']
        if total == 0:
            return {"no_requests": True}
        
        return {
            "total_requests": total,
            "llm_success_rate": self.extraction_stats['hybrid_success'] / total,
            "pattern_fallback_rate": self.extraction_stats['pattern_fallback'] / total,
            "llm_available": self.llm_available,
            "provider": self.llm_provider.value
        }
    
    def test_extraction_quality(self, test_cases: List[Tuple[str, Dict]]) -> Dict[str, Any]:
        """추출 품질 테스트"""
        results = []
        
        for text, expected in test_cases:
            result = self.extract_info_enhanced(text)
            
            # 정확도 계산
            accuracy = self._calculate_accuracy(result.entities, expected)
            
            results.append({
                "input": text,
                "expected": expected,
                "extracted": {
                    "location": result.entities.location_preference,
                    "food_type": result.entities.food_type,
                    "budget": result.entities.budget
                },
                "accuracy": accuracy,
                "confidence": result.confidence,
                "method": result.extraction_method
            })
        
        avg_accuracy = sum(r['accuracy'] for r in results) / len(results)
        avg_confidence = sum(r['confidence'] for r in results) / len(results)
        
        return {
            "results": results,
            "average_accuracy": avg_accuracy,
            "average_confidence": avg_confidence,
            "test_count": len(test_cases)
        }
    
    def _calculate_accuracy(self, extracted: ExtractedEntity, expected: Dict) -> float:
        """정확도 계산"""
        score = 0
        total = 0
        
        # 위치 정확도
        if 'location' in expected:
            total += 1
            if extracted.location_preference == expected['location']:
                score += 1
        
        # 음식 타입 정확도  
        if 'food_type' in expected:
            total += 1
            if extracted.food_type == expected['food_type']:
                score += 1
        
        # 예산 정확도 (10% 오차 허용)
        if 'budget' in expected:
            total += 1
            if extracted.budget and abs(extracted.budget - expected['budget']) <= expected['budget'] * 0.1:
                score += 1
        
        return score / max(total, 1)


def create_enhanced_nlu(openai_api_key: str = None, use_local_model=None) -> EnhancedNLU:
    """향상된 NLU 생성 함수"""
    if openai_api_key:
        return EnhancedNLU(llm_provider=LLMProvider.OPENAI, openai_api_key=openai_api_key)
    elif use_local_model:
        return EnhancedNLU(llm_provider=LLMProvider.LOCAL_MODEL, local_model=use_local_model)
    else:
        # LLM 없이 기본 패턴 매칭만
        return EnhancedNLU()


def test_enhanced_nlu():
    """향상된 NLU 테스트"""
    # OpenAI API 키가 있으면 사용, 없으면 패턴만 사용
    nlu = create_enhanced_nlu(openai_api_key=os.getenv('OPENAI_API_KEY'))
    
    test_cases = [
        "부평에서 먹을 만한거",
        "성수동 맛집 친구랑 가기 좋은 곳",
        "1만5천원 이하로 치킨 추천해줘",
        "김치찌개나 된장찌개 매운거로",
        "혼밥하기 좋은 분식집"
    ]
    
    print("=" * 80)
    print("향상된 NLU 테스트")
    print("=" * 80)
    
    for text in test_cases:
        result = nlu.extract_info_enhanced(text)
        
        print(f"입력: {text}")
        print(f"의도: {result.intent.value}")
        print(f"위치: {result.entities.location_preference}")
        print(f"음식: {result.entities.food_type}")
        print(f"예산: {result.entities.budget}")
        print(f"동반자: {result.entities.companions}")
        print(f"요구사항: {result.entities.special_requirements}")
        print(f"신뢰도: {result.confidence:.3f} ({result.confidence_level.value})")
        print(f"방법: {result.extraction_method}")
        if result.reasoning:
            print(f"추론: {result.reasoning}")
        print("-" * 60)
    
    # 통계 출력
    stats = nlu.get_extraction_statistics()
    print(f"추출 통계: {stats}")


if __name__ == "__main__":
    test_enhanced_nlu()