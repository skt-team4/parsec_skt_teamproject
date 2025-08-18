#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
카테고리 헬퍼 유틸리티
유사 카테고리 추천 및 매핑
"""

# 유사 카테고리 매핑
SIMILAR_CATEGORIES = {
    "한식": ["분식", "일식", "중식"],
    "중식": ["일식", "양식", "한식"],
    "일식": ["한식", "중식", "양식"],
    "양식": ["이탈리안", "패스트푸드", "일식"],
    "치킨": ["피자", "햄버거", "분식"],
    "피자": ["치킨", "햄버거", "양식"],
    "햄버거": ["피자", "치킨", "패스트푸드"],
    "분식": ["한식", "카페", "치킨"],
    "카페": ["베이커리", "분식", "디저트"],
    "베이커리": ["카페", "디저트", "분식"],
    "패스트푸드": ["햄버거", "피자", "치킨"],
    "이탈리안": ["양식", "피자", "카페"],
}

# 인근 지역 매핑
NEARBY_AREAS = {
    "강남": ["서초", "송파", "강동", "역삼"],
    "서초": ["강남", "동작", "관악"],
    "송파": ["강남", "강동", "성남"],
    "부평": ["부천", "계양", "서구"],
    "인천": ["부평", "남동", "연수"],
    "부천": ["부평", "광명", "시흥"],
}

def get_similar_categories(original_category: str, max_suggestions: int = 3) -> list:
    """
    주어진 카테고리와 유사한 카테고리 목록을 반환
    
    Args:
        original_category: 원본 카테고리
        max_suggestions: 최대 제안 수
    
    Returns:
        유사 카테고리 리스트
    """
    suggestions = SIMILAR_CATEGORIES.get(original_category, [])
    return suggestions[:max_suggestions]

def get_nearby_areas(area: str, max_suggestions: int = 3) -> list:
    """
    주어진 지역과 가까운 지역 목록을 반환
    
    Args:
        area: 원본 지역명
        max_suggestions: 최대 제안 수
    
    Returns:
        인근 지역 리스트
    """
    # 지역명 정규화 (구 제거)
    normalized = area.replace('구', '').strip()
    
    # 인근 지역 찾기
    for key in NEARBY_AREAS:
        if key in normalized or normalized in key:
            return NEARBY_AREAS[key][:max_suggestions]
    
    return []

def generate_fallback_message(location: str = None, food_type: str = None) -> str:
    """
    검색 실패 시 적절한 fallback 메시지 생성
    
    Args:
        location: 검색한 위치
        food_type: 검색한 음식 종류
    
    Returns:
        사용자 친화적인 fallback 메시지
    """
    message = "앗, 미안! "
    
    if location and food_type:
        message += f"{location}에서 {food_type} 가게를 못 찾았어... "
        
        # 유사 카테고리 제안
        similar_cats = get_similar_categories(food_type, 2)
        if similar_cats:
            message += f"대신 {', '.join(similar_cats)} 어때? "
        
        # 인근 지역 제안
        nearby = get_nearby_areas(location, 2)
        if nearby:
            message += f"아니면 {', '.join(nearby)} 지역도 한번 찾아볼까?"
    
    elif food_type:
        message += f"{food_type} 가게를 못 찾았어... "
        similar_cats = get_similar_categories(food_type, 2)
        if similar_cats:
            message += f"대신 {', '.join(similar_cats)}는 어때?"
    
    elif location:
        message += f"{location}에서 원하는 가게를 못 찾았어... 다른 음식 종류로 검색해볼까?"
    
    else:
        message += "원하는 가게를 못 찾았어... 좀 더 구체적으로 말해줄래?"
    
    return message