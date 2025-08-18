"""
나비얌 챗봇 이모지 통합 관리 시스템
웹/Android/iOS 환경에서 일관된 이모지 경험 제공
"""

import re
import random
from typing import Dict, List, Optional, Union
from enum import Enum
from dataclasses import dataclass

class EmojiContext(Enum):
    """이모지 사용 상황 분류"""
    GREETING = "greeting"           # 인사, 환영
    FOOD_RECOMMENDATION = "food"    # 음식 추천
    POSITIVE_FEEDBACK = "positive"  # 긍정적 반응
    APPRECIATION = "thanks"         # 감사 표현
    CELEBRATION = "celebration"     # 축하, 성공
    ENCOURAGEMENT = "encourage"     # 격려, 응원
    FRIENDLY = "friendly"          # 친근함
    EXCITEMENT = "excitement"      # 흥미, 재미
    GENERAL = "general"            # 일반적 상황

class PlatformType(Enum):
    """플랫폼 타입"""
    WEB = "web"
    ANDROID = "android" 
    IOS = "ios"
    UNKNOWN = "unknown"

@dataclass
class EmojiSet:
    """플랫폼별 이모지 세트"""
    primary: str        # 주 이모지
    alternatives: List[str]  # 대체 이모지들
    weight: float = 1.0     # 선택 가중치

class NaviyamEmojiManager:
    """나비얌 전용 이모지 관리자"""
    
    def __init__(self):
        # 나비얌 브랜드 이모지 정의
        self.brand_emojis = {
            EmojiContext.GREETING: EmojiSet(
                primary="😊",
                alternatives=["🤗", "😄", "👋"]
            ),
            EmojiContext.FOOD_RECOMMENDATION: EmojiSet(
                primary="🍽️",
                alternatives=["🍴", "😋", "👍", "✨"]
            ),
            EmojiContext.POSITIVE_FEEDBACK: EmojiSet(
                primary="👍",
                alternatives=["😊", "🎉", "✨"]
            ),
            EmojiContext.APPRECIATION: EmojiSet(
                primary="😊",
                alternatives=["🙏", "💙", "✨"]
            ),
            EmojiContext.CELEBRATION: EmojiSet(
                primary="🎉",
                alternatives=["🎊", "✨", "👏", "🥳"]
            ),
            EmojiContext.ENCOURAGEMENT: EmojiSet(
                primary="💪",
                alternatives=["✨", "👍", "😊", "🌟"]
            ),
            EmojiContext.FRIENDLY: EmojiSet(
                primary="😊",
                alternatives=["🤗", "😄", "💝"]
            ),
            EmojiContext.EXCITEMENT: EmojiSet(
                primary="✨",
                alternatives=["🎉", "😆", "🔥", "⭐"]
            ),
            EmojiContext.GENERAL: EmojiSet(
                primary="😊",
                alternatives=["👍", "✨"]
            )
        }
        
        # 아동 친화적 이모지 (나비얌 특화)
        self.child_friendly = {
            "positive": ["😊", "😄", "🤗", "👍", "✨", "🌟"],
            "food": ["🍽️", "🍴", "😋", "🎂", "🍎", "🥗"],
            "celebration": ["🎉", "🎊", "👏", "🥳", "🎈", "🎁"],
            "encouragement": ["💪", "🌟", "⭐", "👍", "✨", "💝"],
            "nature": ["🌸", "🌺", "🦋", "🌈", "☀️", "🌙"]
        }
        
        # 플랫폼별 최적화 (필요시 확장)
        self.platform_optimized = {
            PlatformType.WEB: {},      # 모든 이모지 지원
            PlatformType.ANDROID: {},  # 모든 이모지 지원  
            PlatformType.IOS: {},      # 모든 이모지 지원
        }
        
        # 문장 종료 이모지 패턴
        self.sentence_enders = [".", "!", "?", "😊", "✨", "🍽️", "👍", "🎉"]
        
    def get_emoji(
        self, 
        context: EmojiContext, 
        platform: PlatformType = PlatformType.WEB,
        use_alternative: bool = False
    ) -> str:
        """
        상황에 맞는 이모지 반환
        
        Args:
            context: 사용 상황
            platform: 플랫폼 타입
            use_alternative: 대체 이모지 사용 여부
            
        Returns:
            적절한 이모지 문자열
        """
        emoji_set = self.brand_emojis.get(context, self.brand_emojis[EmojiContext.GENERAL])
        
        if use_alternative and emoji_set.alternatives:
            return random.choice(emoji_set.alternatives)
        else:
            return emoji_set.primary
    
    def get_random_emoji(self, context: EmojiContext, count: int = 1) -> List[str]:
        """랜덤 이모지 선택"""
        emoji_set = self.brand_emojis.get(context, self.brand_emojis[EmojiContext.GENERAL])
        all_emojis = [emoji_set.primary] + emoji_set.alternatives
        
        return random.sample(all_emojis, min(count, len(all_emojis)))
    
    def add_contextual_emoji(
        self, 
        text: str, 
        context: EmojiContext,
        position: str = "end",
        platform: PlatformType = PlatformType.WEB
    ) -> str:
        """
        텍스트에 상황에 맞는 이모지 추가
        
        Args:
            text: 원본 텍스트
            context: 이모지 컨텍스트
            position: 이모지 위치 ("start", "end", "both")
            platform: 플랫폼 타입
            
        Returns:
            이모지가 추가된 텍스트
        """
        if not text.strip():
            return text
            
        emoji = self.get_emoji(context, platform)
        
        if position == "start":
            return f"{emoji} {text.strip()}"
        elif position == "end":
            # 문장 끝에 이미 이모지가 있는지 확인
            if not any(text.strip().endswith(ender) for ender in self.sentence_enders):
                return f"{text.strip()} {emoji}"
            return text
        elif position == "both":
            start_emoji = self.get_emoji(context, platform)
            end_emoji = self.get_emoji(context, platform, use_alternative=True)
            return f"{start_emoji} {text.strip()} {end_emoji}"
        
        return text
    
    def enhance_response_with_emojis(
        self, 
        text: str, 
        intent_type: str = None,
        platform: PlatformType = PlatformType.WEB
    ) -> str:
        """
        응답 텍스트를 분석하여 적절한 이모지 추가
        
        Args:
            text: 응답 텍스트
            intent_type: 의도 타입 (선택사항)
            platform: 플랫폼 타입
            
        Returns:
            이모지가 향상된 텍스트
        """
        if not text.strip():
            return text
            
        # 인텐트별 컨텍스트 매핑
        intent_context_map = {
            "FOOD_RECOMMENDATION": EmojiContext.FOOD_RECOMMENDATION,
            "GREETING": EmojiContext.GREETING,
            "THANKS": EmojiContext.APPRECIATION,
            "GENERAL_CHAT": EmojiContext.FRIENDLY
        }
        
        # 키워드 기반 컨텍스트 감지
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["안녕", "반가", "환영", "처음"]):
            context = EmojiContext.GREETING
        elif any(word in text_lower for word in ["추천", "음식", "맛있", "드세요", "드실"]):
            context = EmojiContext.FOOD_RECOMMENDATION
        elif any(word in text_lower for word in ["감사", "고마", "천만", "별말씀"]):
            context = EmojiContext.APPRECIATION
        elif any(word in text_lower for word in ["축하", "성공", "완료", "좋아요"]):
            context = EmojiContext.CELEBRATION
        elif any(word in text_lower for word in ["화이팅", "힘내", "응원", "격려"]):
            context = EmojiContext.ENCOURAGEMENT
        else:
            # 인텐트 기반 또는 기본값
            context = intent_context_map.get(intent_type, EmojiContext.FRIENDLY)
        
        return self.add_contextual_emoji(text, context, "end", platform)
    
    def clean_duplicate_emojis(self, text: str) -> str:
        """중복 이모지 정리"""
        # 연속된 동일 이모지 제거
        emoji_pattern = r'([😊🎉✨👍🤗😄🍽️💪🌟⭐🎊👏🥳])\1+'
        text = re.sub(emoji_pattern, r'\1', text)
        
        # 너무 많은 이모지 제한 (최대 2개)
        emoji_count = len(re.findall(r'[😊🎉✨👍🤗😄🍽️💪🌟⭐🎊👏🥳]', text))
        if emoji_count > 2:
            # 뒤에서부터 이모지 제거
            emojis_found = list(re.finditer(r'[😊🎉✨👍🤗😄🍽️💪🌟⭐🎊👏🥳]', text))
            if len(emojis_found) > 2:
                # 마지막 2개만 유지
                for match in emojis_found[:-2]:
                    text = text[:match.start()] + text[match.end():]
                    
        return text
    
    def get_child_friendly_emojis(self, category: str = "positive") -> List[str]:
        """아동 친화적 이모지 목록 반환"""
        return self.child_friendly.get(category, self.child_friendly["positive"])
    
    def detect_platform(self, user_agent: str = None) -> PlatformType:
        """User-Agent 기반 플랫폼 감지 (웹 서비스용)"""
        if not user_agent:
            return PlatformType.UNKNOWN
            
        user_agent_lower = user_agent.lower()
        
        if "android" in user_agent_lower:
            return PlatformType.ANDROID
        elif "iphone" in user_agent_lower or "ipad" in user_agent_lower:
            return PlatformType.IOS
        else:
            return PlatformType.WEB
    
    def validate_emoji_support(self, emoji: str, platform: PlatformType) -> bool:
        """플랫폼별 이모지 지원 여부 확인"""
        # 현재는 모든 플랫폼에서 기본 이모지 지원
        # 향후 특수 이모지나 새로운 이모지 추가 시 사용
        return True

# 전역 이모지 매니저 인스턴스
naviyam_emoji_manager = NaviyamEmojiManager()

# 편의 함수들
def add_emoji(text: str, context: str = "friendly", platform: str = "web") -> str:
    """간단한 이모지 추가 함수"""
    try:
        context_enum = EmojiContext(context)
    except ValueError:
        context_enum = EmojiContext.FRIENDLY
        
    try:
        platform_enum = PlatformType(platform)
    except ValueError:
        platform_enum = PlatformType.WEB
        
    return naviyam_emoji_manager.add_contextual_emoji(text, context_enum, "end", platform_enum)

def enhance_response(text: str, intent: str = None, platform: str = "web") -> str:
    """응답 텍스트 이모지 향상"""
    try:
        platform_enum = PlatformType(platform)
    except ValueError:
        platform_enum = PlatformType.WEB
        
    enhanced = naviyam_emoji_manager.enhance_response_with_emojis(text, intent, platform_enum)
    return naviyam_emoji_manager.clean_duplicate_emojis(enhanced)

def get_food_emoji() -> str:
    """음식 관련 이모지 반환"""
    return naviyam_emoji_manager.get_emoji(EmojiContext.FOOD_RECOMMENDATION)

def get_greeting_emoji() -> str:
    """인사 이모지 반환"""
    return naviyam_emoji_manager.get_emoji(EmojiContext.GREETING)

# 테스트 함수
if __name__ == "__main__":
    print("=== 나비얌 이모지 매니저 테스트 ===")
    
    manager = NaviyamEmojiManager()
    
    # 컨텍스트별 이모지 테스트
    contexts = [
        ("안녕하세요! 오늘 뭐 드시고 싶나요?", "greeting"),
        ("치킨집 추천드릴게요!", "food"), 
        ("감사합니다!", "thanks"),
        ("축하드려요!", "celebration")
    ]
    
    for text, context in contexts:
        enhanced = enhance_response(text, context)
        print(f"원본: {text}")
        print(f"향상: {enhanced}")
        print()
    
    # 플랫폼별 테스트
    platforms = ["web", "android", "ios"]
    test_text = "맛있는 음식 추천해드릴게요"
    
    for platform in platforms:
        result = add_emoji(test_text, "food", platform)
        print(f"{platform}: {result}")