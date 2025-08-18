#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
짧은 응답 처리기
대화 맥락에 따라 "아니", "ㄴㄴ" 등을 다르게 해석
"""

import logging
from typing import List, Dict, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class DialogState(Enum):
    """대화 상태"""
    GREETING = "greeting"           # 인사 중
    FOOD_RECOMMENDATION = "food_rec" # 음식 추천 중  
    GENERAL_CHAT = "chat"           # 일반 대화
    WAITING_RESPONSE = "waiting"    # 응답 대기
    UNKNOWN = "unknown"


class ShortResponseHandler:
    """짧은 응답 전용 처리기"""
    
    # 짧은 응답 패턴
    NEGATIVE_PATTERNS = ['아니', '아뇨', 'ㄴㄴ', '노', '싫어', '별로', 'no']
    POSITIVE_PATTERNS = ['응', '네', 'ㅇㅇ', '좋아', '그래', 'ㅇㅋ', 'ok', 'yes']
    NEUTRAL_PATTERNS = ['글쎄', '몰라', '음', '아무거나', '상관없어']
    
    def is_short_response(self, text: str) -> bool:
        """짧은 응답인지 확인"""
        cleaned = text.strip()
        return len(cleaned) <= 5
    
    def get_dialog_state(self, conversation_history: List[Dict]) -> DialogState:
        """대화 히스토리에서 현재 상태 파악"""
        
        if not conversation_history:
            return DialogState.UNKNOWN
            
        # 최근 2개 대화 확인
        recent = conversation_history[-2:] if len(conversation_history) >= 2 else conversation_history
        
        for msg in reversed(recent):
            if msg.get('role') in ['assistant', 'system']:
                content = msg.get('content', '').lower()
                
                # 음식 추천 중
                if any(word in content for word in ['추천', '어때', '맛집', '먹', '메뉴']):
                    return DialogState.FOOD_RECOMMENDATION
                    
                # 인사 중
                elif any(word in content for word in ['안녕', '잘 지내', '요즘']):
                    return DialogState.GREETING
                    
                # 일반 대화
                elif any(word in content for word in ['그렇구나', '알겠어', '네']):
                    return DialogState.GENERAL_CHAT
        
        return DialogState.GENERAL_CHAT
    
    def interpret(
        self, 
        text: str, 
        conversation_history: List[Dict],
        base_intent: str = None
    ) -> Tuple[str, float, Dict]:
        """짧은 응답 해석"""
        
        if not self.is_short_response(text):
            return base_intent, 0.5, {}
        
        text_lower = text.lower().strip()
        dialog_state = self.get_dialog_state(conversation_history)
        
        # 대화 상태별 해석
        if dialog_state == DialogState.FOOD_RECOMMENDATION:
            # 음식 추천 중 "아니" = 다른 추천 원함 (MODIFY_REQUEST로)
            if any(p in text_lower for p in self.NEGATIVE_PATTERNS):
                # 부정 피드백을 MODIFY_REQUEST로 반환해야 함!
                return "modify_request", 0.9, {
                    "feedback_type": "negative",
                    "wants_alternative": True,
                    "intent_source": "short_negative_food_context"
                }
            elif any(p in text_lower for p in self.POSITIVE_PATTERNS):
                return "선택확정", 0.95, {
                    "feedback_type": "positive"
                }
            else:
                return "음식추천", 0.7, {
                    "feedback_type": "neutral"
                }
                
        elif dialog_state == DialogState.GREETING:
            # 인사 중 "아니" = 안 좋다는 의미
            if any(p in text_lower for p in self.NEGATIVE_PATTERNS):
                return "일반대화", 0.85, {
                    "sentiment": "negative"
                }
            elif any(p in text_lower for p in self.POSITIVE_PATTERNS):
                return "일반대화", 0.85, {
                    "sentiment": "positive"  
                }
            else:
                return "일반대화", 0.8, {
                    "sentiment": "neutral"
                }
                
        else:  # GENERAL_CHAT or UNKNOWN
            # 일반 대화 중 짧은 응답 = 일반대화 계속
            return "일반대화", 0.8, {
                "response_type": "short",
                "sentiment": self._detect_sentiment(text_lower)
            }
    
    def _detect_sentiment(self, text: str) -> str:
        """감정 분석"""
        if any(p in text for p in self.NEGATIVE_PATTERNS):
            return "negative"
        elif any(p in text for p in self.POSITIVE_PATTERNS):
            return "positive"
        else:
            return "neutral"


# 싱글톤 인스턴스
_handler = None

def get_short_response_handler() -> ShortResponseHandler:
    global _handler
    if _handler is None:
        _handler = ShortResponseHandler()
    return _handler