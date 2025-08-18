"""
나비얌 챗봇 보안 모듈

사용자 입력 검증 및 prompt injection 방어
"""

import re
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """입력 검증 결과"""
    is_valid: bool
    sanitized_input: str
    error_message: Optional[str] = None
    risk_level: str = "low"  # low, medium, high


class InputValidator:
    """사용자 입력 검증 및 sanitization"""
    
    def __init__(self):
        # 위험한 패턴 정의
        self.injection_patterns = [
            # 시스템 프롬프트 변경 시도
            r"(ignore|forget|disregard).*previous.*instructions?",
            r"(new|change|update).*system.*prompt",
            r"you are now",
            r"act as if",
            r"pretend to be",
            
            # 민감한 정보 추출 시도
            r"(show|tell|give).*system.*prompt",
            r"what.*your.*instructions?",
            r"reveal.*internal",
            
            # 역할 변경 시도
            r"(admin|root|developer).*mode",
            r"debug.*mode",
            r"maintenance.*mode",
            
            # SQL/코드 주입 패턴
            r"(select|insert|update|delete|drop).*from",
            r"exec\(|eval\(|system\(",
            r"<script|javascript:",
            
            # 탈옥 시도
            r"DAN|dan mode|jailbreak",
            r"unlock.*capabilities",
            r"remove.*restrictions"
        ]
        
        # 허용된 특수문자
        self.allowed_special_chars = ".,!?'\"()-_@# "
        
        # 최대 입력 길이
        self.max_input_length = 500
        
        # 금지된 키워드 (아동 보호)
        self.blocked_keywords = [
            # 부적절한 콘텐츠
            "술", "담배", "마약",
            "폭력", "욕설", "비속어",
            # 위험한 요청
            "해킹", "크래킹", "바이러스"
        ]
    
    def validate_input(self, user_input: str) -> ValidationResult:
        """사용자 입력 검증"""
        if not user_input:
            return ValidationResult(
                is_valid=False,
                sanitized_input="",
                error_message="입력이 비어있습니다"
            )
        
        # 1. 길이 체크
        if len(user_input) > self.max_input_length:
            return ValidationResult(
                is_valid=False,
                sanitized_input=user_input[:self.max_input_length],
                error_message=f"입력이 너무 깁니다 (최대 {self.max_input_length}자)",
                risk_level="high"
            )
        
        # 2. 단순 반복 탐지 (치킨치킨치킨... 같은 패턴)
        if len(user_input) > 20:
            # 고유 문자 비율이 5% 미만이면 반복으로 간주
            unique_char_ratio = len(set(user_input)) / len(user_input)
            if unique_char_ratio < 0.05:
                logger.warning(f"반복 입력 탐지: 고유 문자 비율 {unique_char_ratio:.2%}")
                return ValidationResult(
                    is_valid=False,
                    sanitized_input="",
                    error_message="같은 내용을 반복하지 말고 제대로 질문해주세요!",
                    risk_level="high"
                )
            
            # 3-5글자 패턴이 계속 반복되는 경우 (예: 치킨치킨치킨)
            for pattern_len in [2, 3, 4, 5]:
                if len(user_input) >= pattern_len * 5:  # 최소 5번 반복
                    pattern = user_input[:pattern_len]
                    if pattern * (len(user_input) // pattern_len) == user_input[:len(pattern) * (len(user_input) // pattern_len)]:
                        logger.warning(f"패턴 반복 탐지: '{pattern}' 반복")
                        return ValidationResult(
                            is_valid=False,
                            sanitized_input="",
                            error_message="반복하지 말고 진짜 궁금한 거 물어봐주세요!",
                            risk_level="high"
                        )
        
        # 3. 의미 없는 문자열 탐지 (ㅁㄴㅇㄹ, asdfasdf 등)
        # 한글 자음/모음만 10자 이상
        if re.search(r'[ㄱ-ㅎㅏ-ㅣ]{10,}', user_input):
            logger.warning("의미 없는 한글 자음/모음 탐지")
            return ValidationResult(
                is_valid=False,
                sanitized_input="",
                error_message="제대로 된 한글로 질문해주세요!",
                risk_level="high"
            )
        
        # 키보드 연타 패턴 (asdf, qwer, zxcv 등)
        keyboard_patterns = [
            r'[asdf]{8,}', r'[qwer]{8,}', r'[zxcv]{8,}',
            r'[jkl;]{8,}', r'[1234]{8,}', r'[!@#$]{8,}'
        ]
        for pattern in keyboard_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                logger.warning(f"키보드 연타 패턴 탐지: {pattern}")
                return ValidationResult(
                    is_valid=False,
                    sanitized_input="",
                    error_message="장난치지 말고 진짜 먹고 싶은 거 물어봐주세요!",
                    risk_level="high"
                )
        
        # 4. Injection 패턴 검사
        risk_level = "low"
        for pattern in self.injection_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                logger.warning(f"잠재적 injection 탐지: {pattern}")
                risk_level = "high"
                
                # 위험한 부분 제거
                user_input = re.sub(pattern, "[제거됨]", user_input, flags=re.IGNORECASE)
        
        # 3. 금지된 키워드 검사
        for keyword in self.blocked_keywords:
            if keyword in user_input:
                return ValidationResult(
                    is_valid=False,
                    sanitized_input="",
                    error_message=f"부적절한 내용이 포함되어 있습니다: {keyword}",
                    risk_level="high"
                )
        
        # 4. 특수문자 제거 (허용된 것 제외)
        sanitized = self._sanitize_text(user_input)
        
        # 5. 연속된 공백 정리
        sanitized = " ".join(sanitized.split())
        
        return ValidationResult(
            is_valid=True,
            sanitized_input=sanitized,
            risk_level=risk_level
        )
    
    def _sanitize_text(self, text: str) -> str:
        """텍스트 정리"""
        # 허용된 문자만 남기기
        allowed_chars = set(self.allowed_special_chars)
        sanitized = ""
        
        for char in text:
            if char.isalnum() or char in allowed_chars or char.isspace():
                sanitized += char
            else:
                # 허용되지 않은 특수문자는 공백으로 대체
                sanitized += " "
        
        return sanitized.strip()
    
    def validate_api_request(self, request_data: Dict[str, Any]) -> ValidationResult:
        """API 요청 검증"""
        # 필수 필드 확인
        if 'user_input' not in request_data:
            return ValidationResult(
                is_valid=False,
                sanitized_input="",
                error_message="user_input 필드가 필요합니다"
            )
        
        # 사용자 입력 검증
        user_input = str(request_data.get('user_input', ''))
        validation_result = self.validate_input(user_input)
        
        # 추가 필드 검증 (있는 경우)
        if 'user_id' in request_data:
            user_id = str(request_data['user_id'])
            if not user_id.isalnum() or len(user_id) > 50:
                return ValidationResult(
                    is_valid=False,
                    sanitized_input="",
                    error_message="잘못된 user_id 형식입니다"
                )
        
        return validation_result


class RateLimiter:
    """요청 속도 제한"""
    
    def __init__(self, max_requests_per_minute: int = 30):
        self.max_requests = max_requests_per_minute
        self.requests: Dict[str, List[float]] = {}
    
    def check_rate_limit(self, user_id: str) -> bool:
        """속도 제한 확인"""
        import time
        current_time = time.time()
        
        if user_id not in self.requests:
            self.requests[user_id] = []
        
        # 1분 이상 지난 요청 제거
        self.requests[user_id] = [
            t for t in self.requests[user_id]
            if current_time - t < 60
        ]
        
        # 제한 확인
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        
        # 요청 기록
        self.requests[user_id].append(current_time)
        return True


class ContentFilter:
    """콘텐츠 필터링 (아동 보호)"""
    
    def __init__(self):
        self.inappropriate_patterns = [
            # 성인 콘텐츠
            r"성인|19금|야한",
            # 폭력적 내용
            r"살인|폭행|때리",
            # 위험한 행동
            r"자해|자살|위험한"
        ]
    
    def is_safe_for_children(self, text: str) -> bool:
        """아동에게 안전한 콘텐츠인지 확인"""
        for pattern in self.inappropriate_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        return True
    
    def filter_response(self, response: str) -> str:
        """응답 필터링"""
        if not self.is_safe_for_children(response):
            return "죄송해요, 그 내용은 여러분에게 적합하지 않아요. 다른 것을 물어봐 주세요!"
        return response


# 전역 인스턴스
_input_validator: Optional[InputValidator] = None
_rate_limiter: Optional[RateLimiter] = None
_content_filter: Optional[ContentFilter] = None


def get_input_validator() -> InputValidator:
    """전역 입력 검증기 반환"""
    global _input_validator
    if _input_validator is None:
        _input_validator = InputValidator()
    return _input_validator


def get_rate_limiter() -> RateLimiter:
    """전역 속도 제한기 반환"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_content_filter() -> ContentFilter:
    """전역 콘텐츠 필터 반환"""
    global _content_filter
    if _content_filter is None:
        _content_filter = ContentFilter()
    return _content_filter