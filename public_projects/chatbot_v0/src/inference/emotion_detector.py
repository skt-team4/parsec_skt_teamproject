"""
감정 표현 빠른 감지 모듈
RAG 검색 불필요한 케이스 조기 판별
"""

import re
from typing import Tuple, Optional

class EmotionDetector:
    """감정 표현 감지기"""
    
    def __init__(self):
        # 감정 표현 패턴
        self.emotion_patterns = {
            'sad': [r'ㅠ+', r'ㅜ+', r'T[._]T', r'흑+', r'엉엉', r'슬퍼', r'우울'],
            'hungry': [r'배고파', r'배고픔', r'허기', r'먹고\s*싶', r'출출'],
            'confused': [r'뭐\s*먹지', r'모르겠', r'고민', r'추천\s*해'],
            'happy': [r'ㅎㅎ+', r'ㅋㅋ+', r'하하', r'히히', r'좋아', r'기뻐'],
            'greeting': [r'안녕', r'하이', r'헬로', r'반가워'],
            'thanks': [r'고마워', r'감사', r'땡큐', r'ㄱㅅ'],
        }
        
        # 빠른 응답 템플릿
        self.quick_responses = {
            'sad': [
                "맛있는 거 먹고 기운내요! 🍕 어떤 음식이 먹고 싶으세요?",
                "힘내세요! 맛있는 음식 추천해드릴게요 😊 뭐가 좋을까요?",
            ],
            'hungry': [
                "배고프시군요! 🍽️ 어떤 종류의 음식이 드시고 싶으세요?",
                "든든한 한 끼 추천해드릴게요! 예산은 얼마나 되세요?",
            ],
            'confused': [
                "오늘은 치킨이나 피자 어떠세요? 🍗🍕",
                "요즘 인기 있는 메뉴들 추천해드릴까요?",
            ],
            'happy': [
                "기분 좋으시네요! 😊 맛있는 거 드시고 더 행복해지세요!",
                "좋은 하루네요! 특별한 메뉴 추천해드릴까요?",
            ],
            'greeting': [
                "안녕하세요! 맛있는 음식 찾아드릴게요! 🍽️",
                "반가워요! 오늘 뭐 드시고 싶으세요?",
            ],
            'thanks': [
                "천만에요! 맛있게 드세요! 😊",
                "도움이 되어서 기뻐요! 또 필요하면 말씀해주세요!",
            ]
        }
    
    def detect_emotion(self, intent=None, user_text: str = "", response_text: str = "", context: dict = None) -> Tuple[Optional[str], float]:
        """
        감정 표현 감지 (챗봇 인터페이스와 호환)
        Returns: (emotion_type, confidence)
        """
        # 실제로는 user_text를 주로 사용
        text = user_text if user_text else response_text
        text_lower = text.lower().strip()
        
        # 너무 짧은 입력 체크
        if len(text_lower) <= 3:
            # 이모티콘만 있는 경우
            for emotion, patterns in self.emotion_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, text_lower):
                        return emotion, 0.9
        
        # 일반 감정 패턴 체크
        for emotion, patterns in self.emotion_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    # 텍스트 길이에 따라 신뢰도 조정
                    confidence = 0.8 if len(text_lower) > 10 else 0.95
                    return emotion, confidence
        
        return None, 0.0
    
    def get_quick_response(self, emotion: str) -> str:
        """감정에 대한 빠른 응답 반환"""
        import random
        responses = self.quick_responses.get(emotion, [])
        if responses:
            return random.choice(responses)
        return "무엇을 도와드릴까요? 😊"
    
    def should_skip_rag(self, text: str) -> bool:
        """RAG 검색을 건너뛸지 판단"""
        emotion, confidence = self.detect_emotion(user_text=text)
        
        # 감정 표현만 있고 구체적 요청이 없으면 RAG 스킵
        if emotion and confidence > 0.8:
            # 음식 관련 키워드가 있는지 체크
            food_keywords = ['치킨', '피자', '한식', '중식', '일식', '먹', '음식', '메뉴', '추천']
            has_food_request = any(keyword in text for keyword in food_keywords)
            
            if not has_food_request:
                return True  # RAG 검색 스킵
        
        return False
    
    def get_emotion_transitions(self, current_emotion: str) -> dict:
        """감정 전이 확률 반환"""
        transitions = {
            'happy': {'happy': 0.7, 'thinking': 0.2, 'excited': 0.1},
            'sad': {'thinking': 0.4, 'happy': 0.3, 'sad': 0.3},
            'confused': {'thinking': 0.5, 'happy': 0.3, 'confused': 0.2},
            'excited': {'happy': 0.5, 'excited': 0.3, 'thinking': 0.2},
            'thinking': {'happy': 0.4, 'thinking': 0.3, 'confused': 0.3}
        }
        return transitions.get(current_emotion, {'happy': 0.5, 'thinking': 0.5})