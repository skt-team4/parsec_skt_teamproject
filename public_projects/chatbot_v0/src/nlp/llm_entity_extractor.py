"""
LLM 기반 엔티티 추출기
기존 하드코딩된 패턴 매칭을 자연어 이해로 개선
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """추출 가능한 엔티티 타입"""
    LOCATION = "location"
    FOOD_TYPE = "food_type"
    BUDGET = "budget"
    COMPANIONS = "companions"
    TIME = "time"
    TASTE_PREFERENCE = "taste_preference"
    SPECIAL_REQUIREMENTS = "special_requirements"


@dataclass
class ExtractedEntityResult:
    """LLM으로 추출된 엔티티 결과"""
    entities: Dict[str, Any]
    confidence: float
    reasoning: str
    raw_response: str


class LLMEntityExtractor:
    """LLM 기반 엔티티 추출기"""
    
    def __init__(self, llm_model=None):
        self.llm_model = llm_model
        self.extraction_prompts = self._build_extraction_prompts()
        
    def _build_extraction_prompts(self) -> Dict[str, str]:
        """엔티티별 추출 프롬프트 구성"""
        return {
            "comprehensive": """
다음 사용자 입력에서 음식 관련 정보를 JSON 형태로 추출해주세요:

사용자 입력: "{user_input}"

추출할 정보:
1. location: 위치 (예: 부평, 성수동, 강남역 주변, 우리 동네 등)
2. food_type: 음식 종류 (예: 치킨, 김치찌개, 한식, 양식 등)
3. budget: 예산 (원 단위 숫자, 예: 10000, 15000)
4. companions: 동반자 (예: ["혼자"], ["친구"], ["가족"])
5. time_preference: 시간 선호 (예: "지금", "점심", "저녁")
6. taste_preference: 맛 선호 (예: "매운", "순한", "상관없음")
7. special_requirements: 특별 요구사항 (예: ["배달", "포장", "빠른", "건강한"])

인식 규칙:
- "부평에서", "부평쪽", "부평 근처" 모두 location: "부평"
- "1만5천원", "15000원", "만오천원" 모두 budget: 15000
- "김치찌개나 된장찌개" → food_type: "한식-찌개류"
- "저렴한" → special_requirements: ["저렴한"]
- "혼밥하기 좋은" → companions: ["혼자"], special_requirements: ["혼밥친화적"]

응답 형식:
```json
{
  "location": "추출된 위치 또는 null",
  "food_type": "추출된 음식 타입 또는 null", 
  "budget": 숫자 또는 null,
  "companions": ["배열"] 또는 null,
  "time_preference": "추출된 시간 또는 null",
  "taste_preference": "추출된 맛 선호 또는 null",
  "special_requirements": ["배열"] 또는 null,
  "confidence": 0.0-1.0,
  "reasoning": "추출 이유 간단 설명"
}
```
""",
            
            "location_focused": """
다음 텍스트에서 위치 정보를 자세히 분석해주세요:

입력: "{user_input}"

위치 표현의 다양한 형태:
- 명시적 지명: "부평", "성수동", "강남역"
- 관계적 표현: "근처", "주변", "인근", "쪽"
- 상대적 표현: "우리 동네", "여기서", "이 근처"
- 교통 기준: "지하철역", "버스정류장"

응답 형식:
```json
{
  "location": "정규화된 위치명",
  "location_type": "specific|relative|transport",
  "original_expression": "원본 표현",
  "confidence": 0.0-1.0,
  "alternatives": ["다른 가능한 해석들"]
}
```
""",
            
            "budget_focused": """
다음 텍스트에서 예산/가격 정보를 추출하고 해석해주세요:

입력: "{user_input}"

예산 표현 형태:
- 직접적: "1만원", "15000원", "만오천원"
- 간접적: "저렴한", "비싸지 않은", "가성비 좋은"  
- 상황적: "점심값", "회식비", "학생 용돈"
- 범위형: "5천원-1만원", "1만원 이하"

가격대 해석:
- "저렴한" → 5000-8000원
- "적당한" → 8000-15000원
- "회식용" → 20000-30000원

응답 형식:
```json
{
  "budget": 원 단위 숫자,
  "budget_range": {"min": 최소, "max": 최대},
  "budget_type": "exact|range|contextual",
  "original_expression": "원본 표현",
  "confidence": 0.0-1.0
}
```
""",
            
            "food_detailed": """
다음 텍스트에서 음식 관련 정보를 상세히 추출해주세요:

입력: "{user_input}"

분석할 요소:
1. 구체적 메뉴: "양념치킨", "김치찌개", "마르게리타 피자"
2. 카테고리: "한식", "양식", "분식", "아시안"
3. 조리법/스타일: "양념", "후라이드", "매운", "순한"
4. 식사 타입: "점심", "간식", "야식", "디저트"

카테고리 매핑:
- "김치찌개", "된장찌개" → "한식-찌개류"
- "양념치킨", "후라이드치킨" → "치킨-" + 스타일
- "불고기버거" → "패스트푸드-버거"

응답 형식:
```json
{
  "food_type": "메인 카테고리",
  "specific_dish": "구체적 메뉴명",
  "cooking_style": "조리법/스타일",
  "meal_type": "식사 유형",
  "cuisine_origin": "요리 원산지",
  "confidence": 0.0-1.0,
  "alternatives": ["다른 해석 가능성들"]
}
```
"""
        }
    
    def extract_entities_comprehensive(self, user_input: str) -> ExtractedEntityResult:
        """종합적 엔티티 추출"""
        if not self.llm_model:
            raise ValueError("LLM 모델이 설정되지 않았습니다.")
        
        prompt = self.extraction_prompts["comprehensive"].format(user_input=user_input)
        
        try:
            response = self.llm_model.generate(prompt, max_new_tokens=200)
            
            # JSON 응답 파싱
            entities, confidence, reasoning = self._parse_json_response(response)
            
            return ExtractedEntityResult(
                entities=entities,
                confidence=confidence,
                reasoning=reasoning,
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"LLM 엔티티 추출 실패: {e}")
            return self._fallback_extraction(user_input)
    
    def extract_location_detailed(self, user_input: str) -> Dict[str, Any]:
        """위치 정보 상세 추출"""
        if not self.llm_model:
            return self._fallback_location_extraction(user_input)
        
        prompt = self.extraction_prompts["location_focused"].format(user_input=user_input)
        
        try:
            response = self.llm_model.generate(prompt, max_new_tokens=100)
            return self._parse_json_response(response)[0]
        except Exception as e:
            logger.error(f"위치 상세 추출 실패: {e}")
            return self._fallback_location_extraction(user_input)
    
    def extract_budget_detailed(self, user_input: str) -> Dict[str, Any]:
        """예산 정보 상세 추출"""
        if not self.llm_model:
            return self._fallback_budget_extraction(user_input)
        
        prompt = self.extraction_prompts["budget_focused"].format(user_input=user_input)
        
        try:
            response = self.llm_model.generate(prompt, max_new_tokens=100)
            return self._parse_json_response(response)[0]
        except Exception as e:
            logger.error(f"예산 상세 추출 실패: {e}")
            return self._fallback_budget_extraction(user_input)
    
    def extract_food_detailed(self, user_input: str) -> Dict[str, Any]:
        """음식 정보 상세 추출"""
        if not self.llm_model:
            return self._fallback_food_extraction(user_input)
        
        prompt = self.extraction_prompts["food_detailed"].format(user_input=user_input)
        
        try:
            response = self.llm_model.generate(prompt, max_new_tokens=150)
            return self._parse_json_response(response)[0]
        except Exception as e:
            logger.error(f"음식 상세 추출 실패: {e}")
            return self._fallback_food_extraction(user_input)
    
    def _parse_json_response(self, response: str) -> Tuple[Dict, float, str]:
        """LLM JSON 응답 파싱"""
        try:
            # JSON 블록 추출
            json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # JSON 블록이 없으면 전체에서 JSON 찾기
                json_str = response
            
            # JSON 파싱
            data = json.loads(json_str)
            
            entities = {k: v for k, v in data.items() 
                       if k not in ['confidence', 'reasoning']}
            confidence = data.get('confidence', 0.5)
            reasoning = data.get('reasoning', '파싱됨')
            
            return entities, confidence, reasoning
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 파싱 실패: {e}")
            # 간단한 키워드 추출로 폴백
            return self._extract_keywords_fallback(response), 0.3, "JSON 파싱 실패"
        except Exception as e:
            logger.error(f"응답 처리 실패: {e}")
            return {}, 0.1, f"오류: {e}"
    
    def _extract_keywords_fallback(self, text: str) -> Dict[str, Any]:
        """키워드 기반 폴백 추출"""
        entities = {}
        
        # 위치 키워드
        location_keywords = ['강남', '홍대', '신촌', '명동', '부평', '성수', '판교']
        for loc in location_keywords:
            if loc in text:
                entities['location'] = loc
                break
        
        # 음식 키워드
        food_keywords = ['치킨', '피자', '햄버거', '한식', '중식', '일식', '양식']
        for food in food_keywords:
            if food in text:
                entities['food_type'] = food
                break
        
        # 예산 패턴
        budget_pattern = r'(\d+)\s*(원|만원|천원)'
        budget_match = re.search(budget_pattern, text)
        if budget_match:
            amount = int(budget_match.group(1))
            unit = budget_match.group(2)
            if unit == '만원':
                entities['budget'] = amount * 10000
            elif unit == '천원':
                entities['budget'] = amount * 1000
            else:
                entities['budget'] = amount
        
        return entities
    
    def _fallback_extraction(self, user_input: str) -> ExtractedEntityResult:
        """LLM 실패시 폴백 추출"""
        entities = self._extract_keywords_fallback(user_input)
        return ExtractedEntityResult(
            entities=entities,
            confidence=0.4,
            reasoning="폴백 추출 사용",
            raw_response=""
        )
    
    def _fallback_location_extraction(self, text: str) -> Dict[str, Any]:
        """위치 폴백 추출"""
        # 기존 패턴 매칭 로직
        patterns = [
            r'(.+?)\s*근처', r'(.+?)\s*주변', r'(.+?)에서', 
            r'(.+?)쪽', r'(.+?)\s*근방'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                location = match.group(1).strip()
                return {
                    'location': location,
                    'location_type': 'pattern_matched',
                    'confidence': 0.6
                }
        
        # 주요 지역명 직접 매칭
        major_locations = [
            '강남', '홍대', '신촌', '명동', '부평', '성수', '판교',
            '이태원', '종로', '강북', '노원', '잠실', '건대'
        ]
        
        for loc in major_locations:
            if loc in text:
                return {
                    'location': loc,
                    'location_type': 'direct_match',
                    'confidence': 0.7
                }
        
        return {'location': None, 'confidence': 0.0}
    
    def _fallback_budget_extraction(self, text: str) -> Dict[str, Any]:
        """예산 폴백 추출"""
        # 숫자 패턴
        budget_patterns = [
            r'(\d+)\s*만\s*(\d+)\s*천',  # 1만5천
            r'(\d+)\s*만원',             # 1만원
            r'(\d+)\s*천원',             # 5천원
            r'(\d+)원',                  # 10000원
        ]
        
        for pattern in budget_patterns:
            match = re.search(pattern, text)
            if match:
                if '만' in pattern and '천' in pattern:
                    # 1만5천 형태
                    man = int(match.group(1))
                    chun = int(match.group(2))
                    budget = man * 10000 + chun * 1000
                elif '만원' in pattern:
                    budget = int(match.group(1)) * 10000
                elif '천원' in pattern:
                    budget = int(match.group(1)) * 1000
                else:
                    budget = int(match.group(1))
                
                return {
                    'budget': budget,
                    'budget_type': 'exact',
                    'confidence': 0.8
                }
        
        # 상황별 예산 추정
        if '저렴한' in text or '싸게' in text:
            return {'budget': 7000, 'budget_type': 'contextual', 'confidence': 0.5}
        elif '회식' in text:
            return {'budget': 25000, 'budget_type': 'contextual', 'confidence': 0.6}
        elif '학생' in text:
            return {'budget': 6000, 'budget_type': 'contextual', 'confidence': 0.5}
        
        return {'budget': None, 'confidence': 0.0}
    
    def _fallback_food_extraction(self, text: str) -> Dict[str, Any]:
        """음식 폴백 추출"""
        # 구체적 메뉴
        specific_foods = {
            '양념치킨': {'category': '치킨', 'style': '양념'},
            '후라이드치킨': {'category': '치킨', 'style': '후라이드'},
            '김치찌개': {'category': '한식', 'subcategory': '찌개'},
            '된장찌개': {'category': '한식', 'subcategory': '찌개'},
            '마르게리타': {'category': '양식', 'subcategory': '피자'}
        }
        
        for food, info in specific_foods.items():
            if food in text:
                return {
                    'food_type': info['category'],
                    'specific_dish': food,
                    'cooking_style': info.get('style'),
                    'confidence': 0.8
                }
        
        # 카테고리 매칭
        categories = ['치킨', '피자', '햄버거', '파스타', '한식', '중식', '일식', '양식']
        for cat in categories:
            if cat in text:
                return {
                    'food_type': cat,
                    'confidence': 0.7
                }
        
        return {'food_type': None, 'confidence': 0.0}
    
    def enhance_nlu_entities(self, nlu_entities: Dict, user_input: str) -> Dict[str, Any]:
        """기존 NLU 결과를 LLM으로 보강"""
        try:
            llm_result = self.extract_entities_comprehensive(user_input)
            
            # 기존 NLU와 LLM 결과 병합
            enhanced = nlu_entities.copy()
            
            # LLM이 더 확실한 경우 교체
            if llm_result.confidence > 0.7:
                for key, value in llm_result.entities.items():
                    if value is not None:
                        # 기존 값이 없거나 LLM이 더 상세한 정보를 제공하는 경우
                        if (key not in enhanced or enhanced[key] is None or
                            (isinstance(value, str) and len(value) > len(str(enhanced.get(key, ''))))):
                            enhanced[key] = value
            
            return enhanced
            
        except Exception as e:
            logger.error(f"NLU 보강 실패: {e}")
            return nlu_entities


def create_llm_enhanced_extractor(llm_model) -> LLMEntityExtractor:
    """LLM 기반 엔티티 추출기 생성"""
    return LLMEntityExtractor(llm_model)


def test_llm_extraction():
    """LLM 엔티티 추출 테스트"""
    # 테스트용 모의 LLM (실제로는 OpenAI API나 로컬 모델 사용)
    class MockLLM:
        def generate(self, prompt: str, max_new_tokens: int = 200) -> str:
            # 간단한 모의 응답
            if "부평에서 먹을 만한거" in prompt:
                return '''```json
{
  "location": "부평",
  "food_type": null,
  "budget": null,
  "companions": null,
  "time_preference": null,
  "taste_preference": null,
  "special_requirements": ["일반 추천"],
  "confidence": 0.8,
  "reasoning": "부평 지역에서 일반적인 음식 추천 요청"
}
```'''
            return '{"confidence": 0.3}'
    
    extractor = LLMEntityExtractor(MockLLM())
    
    test_cases = [
        "부평에서 먹을 만한거",
        "1만5천원 이하로 치킨 추천해줘",
        "성수동 맛집 친구랑 가기 좋은 곳",
        "김치찌개나 된장찌개 매운거로",
        "혼밥하기 좋은 분식집"
    ]
    
    print("=" * 60)
    print("LLM 엔티티 추출 테스트")
    print("=" * 60)
    
    for text in test_cases:
        result = extractor.extract_entities_comprehensive(text)
        print(f"입력: {text}")
        print(f"엔티티: {result.entities}")
        print(f"신뢰도: {result.confidence}")
        print(f"추론: {result.reasoning}")
        print("-" * 40)


if __name__ == "__main__":
    test_llm_extraction()