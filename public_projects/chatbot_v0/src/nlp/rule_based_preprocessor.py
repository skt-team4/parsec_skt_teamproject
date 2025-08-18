#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
규칙 기반 전처리기 - 명백한 케이스 처리
Gemini 권고사항: 긴급 패치로 +5-8% 정확도 향상
"""

import re
from typing import Optional, Tuple


class RuleBasedPreprocessor:
    """명백한 의도를 규칙으로 먼저 처리"""
    
    def __init__(self):
        # 추천 관련 명확한 패턴
        self.recommendation_patterns = [
            (r'뭐\s*먹', 0.95),           # 뭐 먹지, 뭐 먹을까
            (r'추천', 0.90),               # 추천해줘, 추천 부탁
            (r'좋은\s*(곳|집|카페|음식)', 0.85),  # 좋은 곳
            (r'맛있는', 0.85),             # 맛있는 곳
            (r'어디.*가', 0.80),           # 어디 갈까
            (r'괜찮은', 0.80),             # 괜찮은 곳
        ]
        
        # 운영 정보 명확한 패턴
        self.operation_patterns = [
            (r'영업\s*시간', 0.95),        # 영업시간
            (r'몇\s*시.*(?:까지|부터)', 0.90),  # 몇시까지, 몇시부터
            (r'언제.*(?:열|닫|문)', 0.90),  # 언제 열어, 언제 닫아
            (r'휴무일', 0.95),             # 휴무일
            (r'오늘.*쉬', 0.90),           # 오늘 쉬어?
            (r'지금.*(?:열|영업)', 0.90),  # 지금 열어있어?
            (r'24시간', 0.95),             # 24시간
            (r'주차', 0.90),               # 주차
            (r'브레이크\s*타임', 0.95),    # 브레이크타임
        ]
        
        # 예산 관련 명확한 패턴
        self.budget_patterns = [
            (r'(?:싼|저렴|비싼)', 0.90),   # 싼거, 비싼거
            (r'가성비', 0.95),             # 가성비
            (r'[0-9]+원', 0.85),           # 5000원, 만원
            (r'할인', 0.85),               # 할인
            (r'가격', 0.80),               # 가격
            (r'얼마', 0.75),               # 얼마야
            (r'돈.*없', 0.85),             # 돈 없어
            (r'텅장', 0.90),               # 텅장
            (r'(?:쿠폰|세일)', 0.85),      # 쿠폰, 세일
        ]
        
        # 서비스 관련 명확한 패턴
        self.service_patterns = [
            (r'배달', 0.90),               # 배달
            (r'포장', 0.90),               # 포장
            (r'(?:카드|현금)', 0.85),      # 카드, 현금
            (r'(?:배민|요기요|쿠팡)', 0.90),  # 배달앱
            (r'급식카드', 0.95),           # 급식카드
            (r'(?:예약|대기)', 0.85),      # 예약, 대기
        ]
        
        # 특별 요구 명확한 패턴
        self.special_patterns = [
            (r'혼(?:자|밥)', 0.90),        # 혼자, 혼밥
            (r'데이트', 0.95),             # 데이트
            (r'(?:가족|아이)', 0.85),      # 가족, 아이
            (r'(?:조용|시끄러운)', 0.80),  # 조용한, 시끄러운
            (r'분위기', 0.75),             # 분위기
            (r'(?:단체|모임|회식)', 0.90), # 단체, 모임, 회식
        ]
    
    def preprocess(self, text: str) -> Tuple[Optional[str], float]:
        """
        텍스트를 전처리하여 명확한 의도 반환
        
        Returns:
            (의도, 신뢰도) - 없으면 (None, 0.0)
        """
        text_lower = text.lower()
        
        # 우선순위: recommendation > operation > budget > service > special
        # "오늘 뭐 먹지?" 같은 케이스를 정확히 잡기 위해 recommendation 먼저
        
        # 1. 추천 체크
        for pattern, confidence in self.recommendation_patterns:
            if re.search(pattern, text_lower):
                return "recommendation", confidence
        
        # 2. 운영 정보 체크
        for pattern, confidence in self.operation_patterns:
            if re.search(pattern, text_lower):
                return "operation", confidence
        
        # 3. 예산 체크
        for pattern, confidence in self.budget_patterns:
            if re.search(pattern, text_lower):
                return "budget", confidence
        
        # 4. 서비스 체크
        for pattern, confidence in self.service_patterns:
            if re.search(pattern, text_lower):
                return "service", confidence
        
        # 5. 특별 요구 체크
        for pattern, confidence in self.special_patterns:
            if re.search(pattern, text_lower):
                return "special", confidence
        
        # 규칙에 매칭되지 않으면 None
        return None, 0.0
    
    def process_with_model(self, text: str, model_result):
        """
        규칙과 모델 결과를 결합
        
        Args:
            text: 입력 텍스트
            model_result: 모델의 예측 결과 (intent, confidence)
        
        Returns:
            최종 의도와 신뢰도
        """
        # 규칙 기반 체크
        rule_intent, rule_confidence = self.preprocess(text)
        
        # 규칙이 높은 신뢰도로 매칭되면 규칙 우선
        if rule_intent and rule_confidence >= 0.85:
            return rule_intent, rule_confidence
        
        # 규칙이 중간 신뢰도면 모델과 비교
        if rule_intent and rule_confidence >= 0.75:
            # 모델과 일치하면 신뢰도 부스트
            if model_result.intent == rule_intent:
                return rule_intent, min(model_result.confidence * 1.2, 1.0)
            # 불일치하면 더 높은 신뢰도 선택
            elif model_result.confidence > rule_confidence:
                return model_result.intent, model_result.confidence
            else:
                return rule_intent, rule_confidence
        
        # 규칙이 없거나 낮은 신뢰도면 모델 결과 사용
        return model_result.intent, model_result.confidence


# 테스트
if __name__ == "__main__":
    preprocessor = RuleBasedPreprocessor()
    
    test_cases = [
        "오늘 뭐 먹지?",
        "영업시간 알려줘",
        "싼 거",
        "배달 되나요?",
        "혼밥하기 좋은 곳",
        "분위기 좋은 곳",
        "강남역 근처 맛집",
        "지금 열어있어?",
        "텅장이라 돈 없어",
    ]
    
    print("규칙 기반 전처리 테스트")
    print("=" * 50)
    
    for text in test_cases:
        intent, confidence = preprocessor.preprocess(text)
        if intent:
            print(f"'{text}' -> {intent} ({confidence:.0%})")
        else:
            print(f"'{text}' -> 규칙 없음")