"""
캐릭터 감정 상태 결정 모듈
"""

from typing import Dict, Tuple
from src.data.data_structure import IntentType


class EmotionDetector:
    """사용자 입력과 챗봇 응답에 따른 감정 결정"""
    
    def __init__(self):
        # 의도별 기본 감정
        self.intent_emotions = {
            IntentType.FOOD_REQUEST: "excited",      # 음식 추천 요청 → 신남
            IntentType.BUDGET_INQUIRY: "thinking",   # 예산 문의 → 생각중
            IntentType.LOCATION_INQUIRY: "thinking", # 위치 문의 → 생각중
            IntentType.TIME_INQUIRY: "thinking",     # 시간 문의 → 생각중
            IntentType.COUPON_INQUIRY: "excited",    # 쿠폰 문의 → 신남
            IntentType.MENU_OPTION: "happy",         # 메뉴 옵션 → 행복
            IntentType.GENERAL_CHAT: "happy",        # 일반 대화 → 행복
            IntentType.GOODBYE: "sad",               # 작별 인사 → 슬픔
            IntentType.BALANCE_CHECK: "thinking",    # 잔액 확인 → 생각중
            IntentType.BALANCE_CHARGE: "happy"       # 충전 → 행복
        }
        
        # 감정 트리거 키워드
        self.emotion_keywords = {
            "excited": ["맛있", "최고", "좋아", "추천", "인기", "할인", "쿠폰"],
            "happy": ["안녕", "반가", "네", "좋", "괜찮"],
            "thinking": ["글쎄", "어떤", "뭐", "생각", "고민"],
            "confused": ["모르", "어려", "이해", "뭔지", "무슨"],
            "sad": ["안녕히", "잘가", "다음에", "아쉽", "없"]
        }
        
    def detect_emotion(
        self, 
        intent: IntentType,
        user_text: str,
        response_text: str,
        context: Dict = None
    ) -> Tuple[str, float]:
        """
        감정 상태 결정
        
        Returns:
            emotion: 감정 상태 (happy, excited, thinking, confused, sad)
            confidence: 감정 신뢰도 (0.0 ~ 1.0)
        """
        # 1. 의도 기반 기본 감정
        base_emotion = self.intent_emotions.get(intent, "happy")
        emotion_scores = {
            "happy": 0.3,
            "excited": 0.0,
            "thinking": 0.0,
            "confused": 0.0,
            "sad": 0.0
        }
        emotion_scores[base_emotion] = 0.5
        
        # 2. 사용자 텍스트 분석
        user_text_lower = user_text.lower()
        for emotion, keywords in self.emotion_keywords.items():
            for keyword in keywords:
                if keyword in user_text_lower:
                    emotion_scores[emotion] += 0.2
                    
        # 3. 응답 텍스트 분석
        response_text_lower = response_text.lower()
        
        # 추천이 포함된 경우 → excited
        if "추천" in response_text_lower or "어때요" in response_text_lower:
            emotion_scores["excited"] += 0.3
            
        # 질문이 포함된 경우 → thinking
        if "?" in response_text or "어떤" in response_text_lower:
            emotion_scores["thinking"] += 0.2
            
        # 인사말 → happy
        if "안녕" in response_text_lower or "반가" in response_text_lower:
            emotion_scores["happy"] += 0.3
            
        # 4. 컨텍스트 기반 조정
        if context:
            # 첫 대화 → excited
            if context.get("is_first_interaction", False):
                emotion_scores["excited"] += 0.2
                
            # 잔액 부족 → sad
            if context.get("low_balance", False):
                emotion_scores["sad"] += 0.3
                
            # 추천 실패 → confused
            if context.get("no_recommendations", False):
                emotion_scores["confused"] += 0.3
                
        # 5. 최종 감정 결정
        max_emotion = max(emotion_scores.items(), key=lambda x: x[1])
        emotion = max_emotion[0]
        confidence = min(max_emotion[1], 1.0)
        
        # 6. 특수 케이스 처리
        # 물음표가 많으면 confused
        if user_text.count("?") >= 2:
            emotion = "confused"
            confidence = 0.8
            
        # 감탄사가 많으면 excited
        if user_text.count("!") >= 2 or response_text.count("!") >= 2:
            emotion = "excited"
            confidence = 0.8
            
        return emotion, confidence
    
    def get_emotion_transitions(self, current_emotion: str) -> Dict[str, float]:
        """
        자연스러운 감정 전이 확률
        캐릭터가 갑자기 감정이 바뀌지 않도록
        """
        transitions = {
            "happy": {
                "happy": 0.6,
                "excited": 0.3,
                "thinking": 0.1,
                "confused": 0.0,
                "sad": 0.0
            },
            "excited": {
                "happy": 0.4,
                "excited": 0.5,
                "thinking": 0.1,
                "confused": 0.0,
                "sad": 0.0
            },
            "thinking": {
                "happy": 0.2,
                "excited": 0.1,
                "thinking": 0.5,
                "confused": 0.2,
                "sad": 0.0
            },
            "confused": {
                "happy": 0.1,
                "excited": 0.0,
                "thinking": 0.4,
                "confused": 0.4,
                "sad": 0.1
            },
            "sad": {
                "happy": 0.3,
                "excited": 0.0,
                "thinking": 0.2,
                "confused": 0.0,
                "sad": 0.5
            }
        }
        
        return transitions.get(current_emotion, transitions["happy"])