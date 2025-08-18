"""
LLM 기반 입력 정규화 모듈
복잡한 자연어를 정리된 형태로 변환 + 아동 친화적 응답 생성
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class LLMNormalizedOutput:
    """LLM이 구조화한 출력"""
    normalized_text: str  # 정리된 문장
    identified_entities: Dict[str, Any]  # 추출된 엔티티들
    context_resolution: Dict[str, Any]  # 맥락 해결 정보
    confidence: float  # LLM 신뢰도
    raw_llm_output: str  # 원본 LLM 응답

class LLMNormalizer:
    """LLM 기반 입력 정규화기"""

    def __init__(self, model=None):
        self.model = model

    def normalize_user_input(
        self,
        user_input: str,
        conversation_history: List[Dict] = None,
        user_context: Dict = None
    ) -> LLMNormalizedOutput:
        """사용자 입력을 LLM으로 구조화 (데이터 추출 전용)"""

        if not self.model:
            # LLM 없으면 원본 그대로 반환
            return LLMNormalizedOutput(
                normalized_text=user_input,
                identified_entities={},
                context_resolution={},
                confidence=0.5,
                raw_llm_output=""
            )

        try:
            # 데이터 추출 전용 프롬프트 구성
            prompt = self._build_data_extraction_prompt(
                user_input, conversation_history, user_context
            )

            # LLM 실행
            llm_result = self.model.generate_text(
                prompt=prompt,
                max_new_tokens=100,
                temperature=0.1  # 낮은 온도로 일관성 확보
            )

            # JSON 파싱
            parsed_output = self._parse_llm_output(llm_result["text"])

            return LLMNormalizedOutput(
                normalized_text=parsed_output.get("normalized_text", user_input),
                identified_entities=parsed_output.get("identified_entities", {}),
                context_resolution=parsed_output.get("context_resolution", {}),
                confidence=parsed_output.get("confidence", 0.8),
                raw_llm_output=llm_result["text"]
            )

        except Exception as e:
            logger.error(f"LLM 정규화 실패: {e}")
            # 실패시 원본 반환
            return LLMNormalizedOutput(
                normalized_text=user_input,
                identified_entities={},
                context_resolution={},
                confidence=0.3,
                raw_llm_output=str(e)
            )

    def generate_child_friendly_response(
        self,
        extracted_info,
        recommendations: List[Dict],
        conversation_context: List[Dict] = None,
        user_profile = None,
        temperature: float = 0.5
    ) -> str:
        """아동 친화적 응답 생성 (LLM 사용)"""

        if not self.model:
            return ""

        try:
            # 아동 응답 전용 프롬프트 구성
            prompt = self._build_child_friendly_prompt(
                extracted_info, recommendations, conversation_context, user_profile
            )

            # LLM 실행
            llm_result = self.model.generate_text(
                prompt=prompt,
                max_new_tokens=100,
                temperature=temperature  # 전달받은 temperature 사용
            )

            # 응답 정제
            return self._clean_child_response(llm_result["text"])

        except Exception as e:
            logger.error(f"아동 친화적 응답 생성 실패: {e}")
            return ""

    def _build_data_extraction_prompt(
        self,
        user_input: str,
        conversation_history: List[Dict],
        user_context: Dict
    ) -> str:
        """데이터 추출 전용 프롬프트 구성"""

        prompt_parts = [
            "음식 주문 정보를 구조화하는 AI입니다. 사용자 입력에서 핵심 정보만 추출하세요.",
            ""
        ]

        # Few-shot 예시들
        prompt_parts.extend([
            "예시:",
            '입력: "치킨 먹고 싶어"',
            '출력: {"normalized_text": "치킨을 주문하고 싶습니다", "food_type": "치킨", "budget": null, "companions": [], "confidence": 0.9}',
            '',
            '입력: "친구 2명이랑 1만원으로 뭐 먹을까?"', 
            '출력: {"normalized_text": "친구 2명과 함께 1만원 예산으로 음식을 찾고 있습니다", "food_type": null, "budget": 10000, "companions": ["친구"], "confidence": 0.8}',
            '',
            '입력: "매운거 말고 순한걸로"',
            '출력: {"normalized_text": "매운 음식 대신 순한 음식을 원합니다", "food_type": null, "budget": null, "companions": [], "taste_preference": "순한", "confidence": 0.9}',
            ""
        ])

        # 대화 맥락 (최근 1개만)
        if conversation_history and conversation_history[-1:]:
            last_conv = conversation_history[-1]
            prompt_parts.append(f"이전대화: 사용자「{last_conv.get('user_input', '')}」→ AI「{last_conv.get('bot_response', '')[:30]}...」")
            prompt_parts.append("")

        # 사용자 맥락 (간결하게)
        if user_context:
            context_info = []
            if user_context.get("preferred_foods"):
                context_info.append(f"선호음식:{user_context['preferred_foods'][0]}")
            if user_context.get("usual_budget"):
                context_info.append(f"평소예산:{user_context['usual_budget']}원")
            if context_info:
                prompt_parts.append(f"사용자정보: {', '.join(context_info)}")
                prompt_parts.append("")

        # 현재 입력 및 출력 요청
        prompt_parts.extend([
            f'입력: "{user_input}"',
            '출력 (JSON만):',
            '{"normalized_text": "명확한 문장", "food_type": "음식종류또는null", "budget": 숫자또는null, "companions": ["동반자들"], "taste_preference": "맛선호또는null", "urgency": "급함/보통/여유또는null", "special_requests": ["특별요청들"], "confidence": 0.0~1.0}'
        ])

        return "\n".join(prompt_parts)

    def _build_child_friendly_prompt(
        self,
        extracted_info,
        recommendations: List[Dict],
        conversation_context: List[Dict] = None,
        user_profile = None
    ) -> str:
        """아동 친화적 응답 프롬프트 구성"""

        prompt_parts = [
            "당신은 '나비얌' - 아이들을 위한 친근한 음식 추천 AI입니다.",
            "특징: 밝고 따뜻한 언니/누나 톤, 간단명료, 이모티콘 사용 😊✨",
            "중요: 반드시 구체적인 가게 이름과 메뉴를 추천해주세요!",
            ""
        ]

        # Few-shot 예시들
        prompt_parts.extend([
            "예시:",
            '사용자: "치킨 먹고 싶어"',
            '나비얌: "치킨 좋아요! 맛있는 착한가게 치킨 추천해드릴게요 🍗✨"',
            '',
            '사용자: "예산이 부족해요"', 
            '나비얌: "괜찮아요! 저렴하면서도 맛있는 곳 찾아드릴게요 😊"',
            '',
            '사용자: "고마워요"',
            '나비얌: "천만에요! 맛있게 드세요 🍽️"',
            ""
        ])

        # 개인화 정보 (간소화)
        if user_profile and hasattr(user_profile, 'preferred_categories') and user_profile.preferred_categories:
            prompt_parts.append(f"사용자선호: {user_profile.preferred_categories[0]}")
            prompt_parts.append("")

        # 대화 맥락 (최근 1개만)
        if conversation_context and conversation_context[-1:]:
            last_ctx = conversation_context[-1]
            prompt_parts.append(f"이전: 사용자「{last_ctx.get('user_input', '')}」→ 나비얌「{last_ctx.get('bot_response', '')[:20]}...」")
            prompt_parts.append("")

        # 현재 입력
        prompt_parts.append(f'사용자: "{extracted_info.raw_text}"')

        # 추천 정보 (간결하게)
        if recommendations:
            rec_info = []
            for rec in recommendations[:2]:  # 최대 2개만
                shop_name = rec.get('shop_name', '')
                menu_name = rec.get('menu_name', '')
                price = rec.get('price', 0)
                is_good = rec.get('is_good_influence_shop', False)
                rec_info.append(f"🏪 {shop_name}의 {menu_name} ({price:,}원){'[착한가게]' if is_good else ''}")
            prompt_parts.append(f"추천가능: {', '.join(rec_info)}")
            prompt_parts.append("")

        prompt_parts.extend([
            "나비얌의 따뜻한 응답 (반드시 가게 이름과 메뉴 포함, 1-2문장):",
            "형식: [가게이름]의 [메뉴이름]을 추천해요!",
            ""
        ])

        return "\n".join(prompt_parts)

    def _build_user_context(self, user_profile) -> str:
        """UserProfile → 프롬프트 텍스트 변환"""
        if not user_profile:
            return ""
            
        context_parts = []
        
        # 선호 음식 카테고리
        if user_profile.preferred_categories:
            context_parts.append(f"- 좋아하는 음식: {', '.join(user_profile.preferred_categories)}")
        
        # 평균 예산
        if user_profile.average_budget:
            context_parts.append(f"- 평소 예산: {user_profile.average_budget}원 내외")
        
        # 맛 선호도
        if hasattr(user_profile, 'taste_preferences') and user_profile.taste_preferences:
            taste_info = []
            for taste, score in user_profile.taste_preferences.items():
                if score > 0.7:
                    level = "매우 좋아함"
                elif score > 0.3:
                    level = "좋아함"
                else:
                    level = "보통"
                taste_info.append(f"{taste} {level}")
            if taste_info:
                context_parts.append(f"- 맛 선호: {', '.join(taste_info)}")
        
        # 동반자 패턴
        if hasattr(user_profile, 'companion_patterns') and user_profile.companion_patterns:
            context_parts.append(f"- 주로 함께: {', '.join(user_profile.companion_patterns)}")
        
        # 대화 스타일
        if hasattr(user_profile, 'conversation_style') and user_profile.conversation_style:
            style_map = {
                "friendly": "친근한 대화 선호",
                "formal": "정중한 대화 선호", 
                "casual": "편안한 대화 선호"
            }
            style_desc = style_map.get(user_profile.conversation_style, user_profile.conversation_style)
            context_parts.append(f"- 대화 스타일: {style_desc}")
        
        # 최근 주문 이력 (간단하게)
        if hasattr(user_profile, 'recent_orders') and user_profile.recent_orders:
            recent_foods = []
            for order in user_profile.recent_orders[-3:]:  # 최근 3개만
                if isinstance(order, dict) and 'food_type' in order:
                    recent_foods.append(order['food_type'])
            if recent_foods:
                context_parts.append(f"- 최근 주문: {', '.join(recent_foods)}")
        
        return "\n".join(context_parts)

    def _parse_llm_output(self, llm_text: str) -> Dict[str, Any]:
        """LLM 출력 JSON 파싱 (간소화)"""
        try:
            # JSON 부분 추출
            start_idx = llm_text.find('{')
            end_idx = llm_text.rfind('}') + 1

            if start_idx == -1 or end_idx == 0:
                raise ValueError("JSON 형태를 찾을 수 없음")

            json_str = llm_text[start_idx:end_idx]
            # 간단한 정제만
            json_str = json_str.replace('\n', ' ').replace('\t', ' ')
            
            parsed = json.loads(json_str)

            # 간소화된 구조로 반환
            return {
                "normalized_text": parsed.get("normalized_text", llm_text[:100]),
                "identified_entities": {
                    "food_type": parsed.get("food_type"),
                    "budget": parsed.get("budget"), 
                    "companions": parsed.get("companions", []),
                    "taste_preference": parsed.get("taste_preference"),
                    "urgency": parsed.get("urgency"),
                    "special_requests": parsed.get("special_requests", [])
                },
                "context_resolution": {},  # 필요시 나중에 확장
                "confidence": parsed.get("confidence", 0.8)
            }

        except Exception as e:
            logger.warning(f"LLM 출력 파싱 실패: {e}")
            # 파싱 실패시 기본값 반환
            return {
                "normalized_text": llm_text.strip()[:100] if llm_text.strip() else "음식 추천 요청",
                "identified_entities": {},
                "context_resolution": {},
                "confidence": 0.3
            }

    def _clean_child_response(self, response: str) -> str:
        """아동 친화적 응답 정제"""
        if not response:
            return ""

        # 불필요한 부분 제거
        response = response.strip()

        # 정지 단어 이후 제거
        stop_indicators = ["사용자:", "User:", "나비얌:", "AI:", "\n\n", "###"]
        for stop in stop_indicators:
            if stop in response:
                response = response.split(stop)[0].strip()

        # 특수 문자나 이상한 패턴 제거
        import re
        response = re.sub(r'[#\[\]]\.?', '', response)  # #, [], 제거
        response = re.sub(r'\{.*?\}', '', response)  # 중괄호 내용 제거
        response = re.sub(r'\s+', ' ', response)  # 중복 공백 제거

        # 너무 짧거나 긴 응답 처리  
        if len(response) < 8:  # 더 엄격하게
            return ""
        elif len(response) > 200:  # 길이 제한 늘림
            sentences = response.split('.')
            if len(sentences) > 1:
                response = sentences[0] + '.'
            else:
                response = response[:200] + '...'

        # 마지막 정제
        response = response.strip()
        if response and not response.endswith(('.', '!', '?', '😊', '✨', '🍽️')):
            response += '!'

        return response

    def should_use_llm_normalization(self, text: str) -> bool:
        """LLM 정규화 사용 여부 결정"""

        # 너무 짧은 입력은 LLM 불필요
        if len(text.strip()) < 5:
            return False

        # 복잡한 입력에 대해서만 LLM 사용
        complexity_indicators = [
            len(text) > 25,  # 긴 문장
            "아까" in text or "그거" in text or "저기" in text or "이거" in text,  # 참조 표현
            text.count(" ") > 6,  # 많은 단어
            any(word in text for word in ["이랑", "하고", "그리고", "근데", "그런데"]),  # 복합 표현
            "명이랑" in text or "분이랑" in text or "사람" in text,  # 인원 표현
            any(word in text for word in ["매운", "안매운", "순한", "담백한", "짜게", "싱겁게"]),  # 맛 선호도
            any(word in text for word in ["급해", "빨리", "천천히", "나중에"]),  # 시급성
        ]

        # 2개 이상의 복잡성 지표가 있으면 LLM 사용
        return sum(complexity_indicators) >= 2

    def should_use_llm_response(self, extracted_info, conversation_context) -> bool:
        """LLM 응답 생성 사용 여부 결정 (LLM 우선 전략)"""

        # LLM이 없거나 입력이 없으면 사용하지 않음
        if not extracted_info or not extracted_info.raw_text or not self.model:
            return False

        # 매우 간단한 케이스만 템플릿 사용 (예외적인 경우들)
        simple_templates_only = [
            # 너무 짧은 입력 (1-2글자)
            len(extracted_info.raw_text.strip()) <= 2,
            # 단순 인사말만 (다른 내용 없음)
            (extracted_info.raw_text.strip() in ["안녕", "하이", "헬로", "hi", "hello"] and
             extracted_info.intent.value == "general_chat"),
        ]

        # 예외적인 경우만 템플릿 사용
        if any(simple_templates_only):
            return False

        # **나머지 모든 경우는 LLM 우선 사용**
        # 음식 관련 모든 요청, 추천 요청, 일반 대화 등
        llm_preferred_cases = [
            # 1. 모든 음식 관련 요청
            extracted_info.intent.value in ["food_request", "budget_inquiry", "location_inquiry", "menu_option"],
            
            # 2. 추천 관련 키워드가 포함된 모든 입력
            any(word in extracted_info.raw_text.lower() for word in
                ["추천", "뭐먹", "먹고싶", "드시고싶", "찾아", "어떤", "좋은", "맛있는", "괜찮은"]),
            
            # 3. 일반 대화도 LLM 사용 (단순 인사말 제외)
            extracted_info.intent.value == "general_chat",
            
            # 4. 질문 형태의 모든 입력
            any(char in extracted_info.raw_text for char in ["?", "까", "뭐", "어디", "어떻", "얼마"]),
            
            # 5. 감정이나 의견이 포함된 입력
            any(word in extracted_info.raw_text.lower() for word in
                ["좋아", "싫어", "별로", "최고", "맛있", "별루", "고마워", "감사", "좋았", "아쉬웠"]),
            
            # 6. 3글자 이상의 모든 의미있는 입력
            len(extracted_info.raw_text.strip()) >= 3,
        ]

        # LLM 우선 사용 전략: 위 조건 중 하나라도 해당하면 LLM 사용
        return any(llm_preferred_cases)

    def analyze_for_learning(self, text: str) -> Dict[str, Any]:
        """학습용 텍스트 분석 (추가 기능)"""
        try:
            analysis = {
                "text_length": len(text),
                "word_count": len(text.split()),
                "has_references": any(word in text for word in ["아까", "그거", "저기", "이거"]),
                "has_complex_expressions": any(word in text for word in ["이랑", "하고", "그리고"]),
                "has_taste_preferences": any(word in text for word in ["매운", "순한", "짜게", "싱겁게"]),
                "has_urgency": any(word in text for word in ["급해", "빨리", "천천히"]),
                "has_emotions": any(word in text for word in ["고마워", "감사", "좋아", "싫어"]),
                "complexity_score": self._calculate_complexity_score(text)
            }

            return analysis
        except Exception as e:
            logger.error(f"학습용 분석 실패: {e}")
            return {}

    def _calculate_complexity_score(self, text: str) -> float:
        """텍스트 복잡도 점수 계산"""
        score = 0.0

        # 길이 기반 점수
        score += min(len(text) / 50.0, 1.0) * 0.3

        # 단어 수 기반 점수
        score += min(len(text.split()) / 15.0, 1.0) * 0.3

        # 복잡성 지표 기반 점수
        complexity_features = [
            "아까" in text, "그거" in text, "이랑" in text, "하고" in text,
            "매운" in text, "순한" in text, "급해" in text, "명이랑" in text
        ]
        score += sum(complexity_features) / len(complexity_features) * 0.4

        return min(score, 1.0)