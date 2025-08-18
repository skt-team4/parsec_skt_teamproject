"""
LLM 기반 NLU를 위한 프롬프트 템플릿 모음
다양한 상황과 요구사항에 맞는 프롬프트 제공
"""

from typing import Dict, List, Any
from enum import Enum


class PromptType(Enum):
    """프롬프트 타입"""
    COMPREHENSIVE = "comprehensive"
    LOCATION_FOCUSED = "location_focused"  
    BUDGET_FOCUSED = "budget_focused"
    FOOD_FOCUSED = "food_focused"
    CONTEXT_AWARE = "context_aware"
    VALIDATION = "validation"


class PromptTemplates:
    """프롬프트 템플릿 관리 클래스"""
    
    def __init__(self):
        self.templates = self._build_templates()
        
    def _build_templates(self) -> Dict[str, str]:
        """프롬프트 템플릿 구축"""
        return {
            
            # 종합 추출 프롬프트
            "comprehensive": """
당신은 한국어 음식 추천 대화에서 정보를 추출하는 전문가입니다.

사용자 입력: "{user_input}"

다음 정보를 JSON 형태로 정확히 추출해주세요:

📍 LOCATION (위치):
- 패턴 인식: "부평에서", "부평쪽", "부평 근처", "부평 주변" → "부평"
- 역명: "강남역 주변", "서울역 근처" → "강남역", "서울역"  
- 상대적 표현: "우리 동네", "여기서", "이 근처" → "현재위치"
- 구체적 지명: "성수동", "홍대입구", "명동" → 그대로

🍽️ FOOD_TYPE (음식 종류):
- 구체적 메뉴: "양념치킨" → "치킨-양념", "김치찌개" → "한식-찌개"
- 복수 옵션: "김치찌개나 된장찌개" → "한식-찌개류"
- 카테고리: "한식", "중식", "양식", "분식", "아시안" 등
- 조리법 포함: "매운 떡볶이" → "분식-떡볶이-매운"

💰 BUDGET (예산, 원 단위):
- 직접 표현: "1만원" → 10000, "15000원" → 15000
- 복합 표현: "1만5천원" → 15000, "이만오천원" → 25000  
- 상황별 추정: "저렴한" → 7000, "학생 용돈" → 6000, "회식비" → 25000
- 범위 표현: "5천원-1만원" → 7500 (중간값)

👥 COMPANIONS (동반자):
- "친구랑", "친구와 함께" → ["친구"]
- "혼자", "혼밥" → ["혼자"]
- "가족끼리", "부모님과" → ["가족"]
- "연인과", "남친이랑" → ["연인"]

⏰ DINING_CONTEXT (식사 상황):
- 시간: "점심", "저녁", "야식", "브런치"
- 상황: "회식", "데이트", "가족식사", "혼밥"
- 긴급도: "지금 당장", "빠르게", "급해"

⭐ SPECIAL_REQUIREMENTS (특별 요구사항):
- 서비스: "배달", "포장", "매장 취식"
- 특성: "빠른", "조용한", "넓은", "주차 편한"
- 맛: "매운", "순한", "달콤한"  
- 기타: "혼밥하기 좋은", "인스타 감성", "가성비"

응답 형식 (다른 설명 없이 JSON만):
{{
  "location": "위치명 또는 null",
  "food_type": "음식 종류 또는 null",
  "budget": 숫자 또는 null,
  "companions": ["배열"] 또는 null,
  "dining_context": "상황 또는 null", 
  "special_requirements": ["배열"] 또는 null,
  "confidence": 0.0-1.0,
  "reasoning": "추출 근거 한 줄"
}}
""",

            # 위치 집중 추출
            "location_focused": """
사용자 입력에서 위치 정보를 자세히 분석해주세요.

입력: "{user_input}"

위치 표현 패턴별 처리:

🎯 직접 지명:
- "부평", "성수동", "강남역" → 그대로 인식
- 동/구 단위: "마포구", "강남구" → "마포", "강남"

🔄 관계 표현:
- "부평 근처", "부평 주변", "부평쪽" → "부평"
- "강남역 인근", "서울역 부근" → "강남역", "서울역"

📍 상대 위치:
- "우리 동네", "여기서", "이 근처" → "현재위치"
- "회사 근처", "집 주변" → "개인위치"

🚇 교통 기준:
- "지하철역 근처" → "지하철역"
- "버스 정류장 근처" → "버스정류장"

특별 처리:
- 여러 지역 언급시 첫 번째를 주 위치로
- "또는", "이나" 연결시 모두 대안으로 기록

응답 형식:
{{
  "primary_location": "주 위치",
  "location_type": "specific|relative|transport",
  "alternatives": ["다른 가능한 위치들"],
  "original_expressions": ["원본 표현들"],
  "confidence": 0.0-1.0,
  "geographic_scope": "neighborhood|district|city"
}}
""",

            # 예산 집중 추출  
            "budget_focused": """
사용자 입력에서 예산 관련 정보를 추출하고 해석해주세요.

입력: "{user_input}"

예산 패턴 분석:

💵 직접 금액:
- "1만원", "10000원" → 10000
- "1만5천원", "15000원", "만오천원" → 15000
- "이만원", "2만원", "20000원" → 20000

💸 간접 표현:
- "저렴한", "싸게", "경제적인" → 5000-8000 추정
- "적당한", "보통", "무난한" → 8000-15000 추정  
- "비싸도 괜찮아", "가격 상관없어" → 20000+ 추정

🎯 상황별 예산:
- "학생 용돈", "학식 수준" → 4000-6000
- "직장인 점심값" → 7000-12000
- "회식비", "회사 경비" → 20000-30000
- "데이트비", "특별한 날" → 15000-25000

📊 범위 표현:
- "5천원-1만원" → min: 5000, max: 10000
- "1만원 이하", "만원 밑으로" → max: 10000
- "최소 1만원", "1만원 이상" → min: 10000

응답 형식:
{{
  "budget": 추정 금액 (원),
  "budget_range": {{"min": 최소, "max": 최대}},
  "budget_type": "exact|estimated|range|contextual", 
  "confidence_level": "high|medium|low",
  "original_expression": "원본 표현",
  "reasoning": "추정 근거"
}}
""",

            # 음식 집중 추출
            "food_focused": """  
사용자 입력에서 음식 관련 정보를 상세 분석해주세요.

입력: "{user_input}"

음식 분류 체계:

🍚 한식:
- 찌개류: "김치찌개", "된장찌개", "순두부찌개"
- 구이류: "갈비", "삼겹살", "불고기"  
- 면류: "냉면", "비빔면", "잔치국수"

🍕 양식:
- 이탈리안: "파스타", "피자", "리조또"
- 패스트푸드: "햄버거", "핫도그", "샌드위치"
- 기타: "스테이크", "샐러드"

🍜 중식:
- 면류: "짜장면", "짬뽕", "우동"
- 요리: "탕수육", "깐풍기", "마파두부"

🍛 일식:
- "초밥", "사시미", "라멘", "돈까스", "카레"

🍤 아시안:
- 동남아: "쌀국수", "팟타이", "똠양꿍"
- 기타: "인도 커리"

🍗 치킨/닭요리:
- 스타일: "후라이드", "양념", "간장", "마늘"
- 부위: "윙", "다리", "순살"

세부 분석:
- 조리법 포함: "매운 떡볶이" → 분식-떡볶이-매운
- 복수 옵션: "김치찌개나 된장찌개" → 한식-찌개류
- 퓨전 요리: "불고기버거" → 퓨전-버거-불고기

응답 형식:
{{
  "main_category": "주 카테고리",
  "sub_category": "세부 분류",  
  "specific_dishes": ["구체적 메뉴들"],
  "cooking_method": "조리법",
  "taste_profile": "맛 특성",
  "cuisine_origin": "요리 기원",
  "fusion_elements": ["퓨전 요소들"],
  "confidence": 0.0-1.0
}}
""",

            # 맥락 인식 프롬프트
            "context_aware": """
이전 대화를 참고하여 현재 요청을 분석해주세요.

대화 기록:
{conversation_history}

현재 입력: "{user_input}"

맥락 분석 포인트:

🔗 참조 해결:
- "거기서", "그 근처" → 이전 언급 위치 참조
- "그거", "그런 거", "비슷한 거" → 이전 음식 타입 참조
- "더 싼", "더 비싼" → 이전 예산 대비 조정

📈 선호도 누적:
- 반복 언급된 지역 → 선호 지역으로 인식
- 자주 찾는 음식 종류 → 선호 음식으로 기록
- 예산 패턴 → 평소 예산대 파악

🎯 의도 진화:
- 구체화: "맛집" → "치킨집" → "양념치킨"
- 확장: "점심" → "회식" → "회사 근처 회식"
- 변경: "중식" → "한식으로 바꿀래"

응답 형식:
{{
  "resolved_entities": {{
    "location": "해결된 위치",
    "food_type": "해결된 음식 타입", 
    "budget": "조정된 예산"
  }},
  "context_references": ["참조한 이전 정보들"],
  "preference_updates": ["새로 파악된 선호도"],
  "conversation_stage": "초기|구체화|결정",
  "confidence": 0.0-1.0
}}
""",

            # 검증 프롬프트
            "validation": """
추출된 정보의 정확성과 일관성을 검증해주세요.

원본 입력: "{user_input}"
추출 결과: {extracted_entities}

검증 항목:

✅ 엔티티 정확성:
- 위치명이 실제 존재하는 지명인가?
- 음식 분류가 올바른가?
- 예산이 현실적인 범위인가?

🔍 일관성 검사:
- 의도와 엔티티가 맞는가?
- 동반자와 상황이 조화로운가?
- 특별 요구사항이 모순되지 않는가?

⚠️ 위험 요소:
- 추출 오류 가능성
- 모호한 표현으로 인한 오해
- 문맥상 누락된 정보

응답 형식:
{{
  "validation_passed": true/false,
  "accuracy_score": 0.0-1.0,
  "issues": ["발견된 문제점들"],
  "suggestions": ["개선 제안사항"],
  "confidence_adjustment": +0.1/-0.1,
  "recommended_action": "accept|review|reject"
}}
""",

            # Few-shot 예시 프롬프트  
            "few_shot_examples": """
다음 예시들을 참고하여 정보를 추출해주세요:

예시 1:
입력: "부평에서 먹을 만한거"
출력: {{"location": "부평", "food_type": null, "confidence": 0.7}}

예시 2:  
입력: "1만5천원 이하로 치킨 추천해줘"
출력: {{"budget": 15000, "food_type": "치킨", "confidence": 0.9}}

예시 3:
입력: "성수동 맛집 친구랑 가기 좋은 곳"  
출력: {{"location": "성수동", "companions": ["친구"], "special_requirements": ["분위기좋은"], "confidence": 0.8}}

현재 입력: "{user_input}"
출력:
""",

            # 오류 처리 프롬프트
            "error_handling": """
다음 입력에서 정보 추출이 어려운 경우의 처리 방법:

입력: "{user_input}"

처리 전략:

🤔 모호한 경우:
- "뭐 먹지?" → food_type: null, 일반적 추천 요청으로 처리
- "저기 가자" → location: "이전_맥락_참조"

❓ 불완전한 정보:
- "치킨 비싼거" → food_type: "치킨", budget: 높은_가격대_추정
- "친구랑" → companions: ["친구"], 다른 정보는 null

🚫 추출 불가:
- 의미를 알 수 없는 경우 → 모든 필드 null
- 음식과 무관한 경우 → confidence: 0.0

응답 형식:
{{
  "extraction_possible": true/false,
  "extracted_entities": {{}},
  "uncertainty_flags": ["불확실한 필드들"], 
  "fallback_strategy": "추천_전략",
  "confidence": 0.0-1.0
}}
"""
        }
    
    def get_prompt(self, prompt_type: PromptType, **kwargs) -> str:
        """프롬프트 가져오기"""
        template = self.templates.get(prompt_type.value)
        if not template:
            raise ValueError(f"알 수 없는 프롬프트 타입: {prompt_type}")
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"프롬프트 템플릿에 필요한 매개변수가 없습니다: {e}")
    
    def get_comprehensive_prompt(self, user_input: str) -> str:
        """종합 추출 프롬프트"""
        return self.get_prompt(PromptType.COMPREHENSIVE, user_input=user_input)
    
    def get_location_prompt(self, user_input: str) -> str:
        """위치 집중 프롬프트"""
        return self.get_prompt(PromptType.LOCATION_FOCUSED, user_input=user_input)
    
    def get_budget_prompt(self, user_input: str) -> str:
        """예산 집중 프롬프트"""
        return self.get_prompt(PromptType.BUDGET_FOCUSED, user_input=user_input)
    
    def get_food_prompt(self, user_input: str) -> str:
        """음식 집중 프롬프트"""
        return self.get_prompt(PromptType.FOOD_FOCUSED, user_input=user_input)
    
    def get_context_prompt(self, user_input: str, conversation_history: List[str]) -> str:
        """맥락 인식 프롬프트"""
        history_text = "\n".join([f"- {msg}" for msg in conversation_history[-5:]])
        return self.get_prompt(
            PromptType.CONTEXT_AWARE,
            user_input=user_input,
            conversation_history=history_text
        )
    
    def get_validation_prompt(self, user_input: str, extracted_entities: Dict) -> str:
        """검증 프롬프트"""
        import json
        entities_text = json.dumps(extracted_entities, ensure_ascii=False, indent=2)
        return self.get_prompt(
            PromptType.VALIDATION,
            user_input=user_input,
            extracted_entities=entities_text
        )
    
    def create_custom_prompt(self, base_template: str, examples: List[Dict] = None,
                           constraints: List[str] = None) -> str:
        """커스텀 프롬프트 생성"""
        prompt = base_template
        
        # 예시 추가
        if examples:
            example_text = "\n\n예시:\n"
            for i, example in enumerate(examples, 1):
                example_text += f"예시 {i}:\n"
                example_text += f"입력: \"{example['input']}\"\n"
                example_text += f"출력: {example['output']}\n\n"
            prompt += example_text
        
        # 제약조건 추가
        if constraints:
            constraint_text = "\n제약조건:\n"
            for constraint in constraints:
                constraint_text += f"- {constraint}\n"
            prompt += constraint_text
        
        return prompt
    
    def optimize_prompt_for_model(self, base_prompt: str, model_type: str) -> str:
        """모델별 프롬프트 최적화"""
        if model_type.lower() in ["gpt-3.5-turbo", "gpt-4"]:
            # OpenAI 모델용: 구조화된 형태
            return f"시스템: 당신은 한국어 NLU 전문가입니다.\n\n{base_prompt}"
        
        elif model_type.lower() in ["claude", "claude-3"]:
            # Claude용: 친근한 어조
            return f"안녕하세요! 다음 작업을 도와주세요:\n\n{base_prompt}"
        
        elif "llama" in model_type.lower() or "alpaca" in model_type.lower():
            # Llama/Alpaca용: 간결한 instruction 형태
            return f"### Instruction:\n{base_prompt}\n\n### Response:"
        
        else:
            # 일반적인 형태
            return base_prompt


# 전역 인스턴스
prompt_templates = PromptTemplates()


def test_prompt_templates():
    """프롬프트 템플릿 테스트"""
    
    test_cases = [
        {
            "input": "부평에서 먹을 만한거",
            "expected": {"location": "부평", "food_type": None}
        },
        {
            "input": "1만5천원 이하로 치킨 추천해줘", 
            "expected": {"budget": 15000, "food_type": "치킨"}
        }
    ]
    
    print("=" * 80)
    print("프롬프트 템플릿 테스트")
    print("=" * 80)
    
    for case in test_cases:
        user_input = case["input"]
        
        # 종합 프롬프트
        comprehensive = prompt_templates.get_comprehensive_prompt(user_input)
        print(f"입력: {user_input}")
        print(f"종합 프롬프트 길이: {len(comprehensive)} 문자")
        
        # 위치 집중 프롬프트  
        location = prompt_templates.get_location_prompt(user_input)
        print(f"위치 프롬프트 길이: {len(location)} 문자")
        
        print("-" * 60)
    
    # 맥락 프롬프트 테스트
    conversation_history = [
        "강남에서 맛집 찾고 있어",
        "한식이 좋겠어", 
        "예산은 1만원 정도"
    ]
    
    context_prompt = prompt_templates.get_context_prompt(
        "그 근처에 뭐 있어?", conversation_history
    )
    print("맥락 프롬프트 생성 완료")
    print(f"맥락 프롬프트 길이: {len(context_prompt)} 문자")


if __name__ == "__main__":
    test_prompt_templates()