"""
카테고리 세분화 매퍼
양식으로 뭉뚱그려진 카테고리를 세분화
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class CategoryMapper:
    """카테고리 세분화 및 매핑"""
    
    # 세부 카테고리 매핑 (청소년 친화적)
    CATEGORY_MAPPING = {
        '샐러드': {
            'keywords': ['샐러드', 'salad', '샐러디', '슬로우캘리', '샐러드박스', '그린', 'green'],
            'parent': '양식',
            'teen_appeal': 0.3,  # 청소년 선호도 낮음
            'health_score': 0.9,  # 건강 점수 높음
            'typical_price': 8000,
            'meal_card_common': False
        },
        '건강식': {
            'keywords': ['건강', '다이어트', '저칼로리', '닭가슴살', '단백질', '탄단지'],
            'parent': '양식',
            'teen_appeal': 0.2,
            'health_score': 0.95,
            'typical_price': 10000,
            'meal_card_common': False
        },
        '브런치': {
            'keywords': ['브런치', 'brunch', '에그', '베네딕트', '팬케이크', '토스트'],
            'parent': '양식',
            'teen_appeal': 0.5,
            'health_score': 0.5,
            'typical_price': 12000,
            'meal_card_common': False
        },
        '파스타': {
            'keywords': ['파스타', 'pasta', '스파게티', '알리오올리오', '까르보나라', '볼로네제'],
            'parent': '양식',
            'teen_appeal': 0.7,
            'health_score': 0.4,
            'typical_price': 11000,
            'meal_card_common': True
        },
        '피자': {
            'keywords': ['피자', 'pizza', '도미노', '피자헛', '피자스쿨', '파파존스'],
            'parent': '양식',
            'teen_appeal': 0.95,
            'health_score': 0.3,
            'typical_price': 15000,
            'meal_card_common': True
        },
        '버거': {
            'keywords': ['버거', 'burger', '햄버거', '맥도날드', '버거킹', '롯데리아', '맘스터치'],
            'parent': '패스트푸드',
            'teen_appeal': 0.9,
            'health_score': 0.3,
            'typical_price': 7000,
            'meal_card_common': True
        },
        '치킨': {
            'keywords': ['치킨', 'chicken', '통닭', 'BBQ', 'BHC', '교촌', '굽네', '페리카나'],
            'parent': '치킨',
            'teen_appeal': 0.95,
            'health_score': 0.3,
            'typical_price': 18000,
            'meal_card_common': True
        },
        '분식': {
            'keywords': ['떡볶이', '김밥', '순대', '튀김', '라면', '우동', '어묵', '분식'],
            'parent': '분식',
            'teen_appeal': 0.9,
            'health_score': 0.4,
            'typical_price': 5000,
            'meal_card_common': True
        },
        '편의점': {
            'keywords': ['CU', 'GS25', 'GS', '세븐일레븐', '세븐', '이마트24', '미니스톱', '편의점'],
            'parent': '편의점',
            'teen_appeal': 0.8,
            'health_score': 0.3,
            'typical_price': 5000,
            'meal_card_common': True
        },
        '카페': {
            'keywords': ['카페', 'cafe', 'coffee', '커피', '스타벅스', '이디야', '메가커피', '빽다방'],
            'parent': '카페',
            'teen_appeal': 0.6,
            'health_score': 0.3,
            'typical_price': 5000,
            'meal_card_common': False
        },
        '디저트': {
            'keywords': ['디저트', 'dessert', '케이크', '마카롱', '빵', '베이커리', '도넛', '아이스크림'],
            'parent': '베이커리',
            'teen_appeal': 0.7,
            'health_score': 0.2,
            'typical_price': 6000,
            'meal_card_common': False
        }
    }
    
    # 청소년이 잘 안먹는 카테고리
    LOW_TEEN_CATEGORIES = ['샐러드', '건강식', '브런치']
    
    # 청소년이 좋아하는 카테고리
    HIGH_TEEN_CATEGORIES = ['치킨', '피자', '버거', '분식', '편의점']
    
    @classmethod
    def get_detailed_category(cls, shop_data: Dict[str, Any]) -> str:
        """
        가게 정보를 바탕으로 세부 카테고리 추출
        
        Args:
            shop_data: 가게 정보 (name, category, description 등)
        
        Returns:
            세부 카테고리명
        """
        name = shop_data.get('name', '').lower()
        current_category = shop_data.get('category', '')
        description = shop_data.get('description', '').lower()
        menu_items = shop_data.get('menu_items', [])
        
        # 텍스트 통합
        text_to_check = f"{name} {description} {' '.join(menu_items)}".lower()
        
        # 세부 카테고리 매칭
        for detailed_cat, info in cls.CATEGORY_MAPPING.items():
            for keyword in info['keywords']:
                if keyword.lower() in text_to_check:
                    logger.debug(f"카테고리 세분화: {current_category} -> {detailed_cat}")
                    return detailed_cat
        
        # 매칭 안되면 원래 카테고리 유지
        return current_category
    
    @classmethod
    def get_teen_appeal_score(cls, category: str) -> float:
        """
        카테고리별 청소년 선호도 점수
        
        Args:
            category: 카테고리명
        
        Returns:
            0.0 ~ 1.0 사이의 선호도 점수
        """
        # 세부 카테고리에서 찾기
        for cat, info in cls.CATEGORY_MAPPING.items():
            if cat.lower() == category.lower():
                return info['teen_appeal']
        
        # 기본 카테고리별 점수
        default_scores = {
            '한식': 0.6,
            '중식': 0.7,
            '일식': 0.5,
            '양식': 0.6,
            '분식': 0.9,
            '치킨': 0.95,
            '피자': 0.95,
            '패스트푸드': 0.9,
            '편의점': 0.8,
            '카페': 0.6,
            '베이커리': 0.7
        }
        
        return default_scores.get(category, 0.5)
    
    @classmethod
    def get_health_score(cls, category: str) -> float:
        """
        카테고리별 건강 점수 (영양 균형 고려)
        
        Args:
            category: 카테고리명
        
        Returns:
            0.0 ~ 1.0 사이의 건강 점수
        """
        # 세부 카테고리에서 찾기
        for cat, info in cls.CATEGORY_MAPPING.items():
            if cat.lower() == category.lower():
                return info['health_score']
        
        # 기본 카테고리별 점수
        default_scores = {
            '한식': 0.7,
            '중식': 0.4,
            '일식': 0.6,
            '양식': 0.4,
            '분식': 0.4,
            '치킨': 0.3,
            '피자': 0.3,
            '패스트푸드': 0.2,
            '편의점': 0.3,
            '카페': 0.3,
            '베이커리': 0.2
        }
        
        return default_scores.get(category, 0.5)
    
    @classmethod
    def adjust_score_for_teen(cls, 
                             base_score: float,
                             category: str,
                             user_age: int = 15) -> float:
        """
        청소년 특성에 맞게 점수 조정
        
        Args:
            base_score: 기본 점수
            category: 카테고리
            user_age: 사용자 나이
        
        Returns:
            조정된 점수
        """
        detailed_category = category
        
        # 청소년 선호도 반영
        teen_appeal = cls.get_teen_appeal_score(detailed_category)
        
        # 나이별 가중치
        if user_age <= 13:  # 초등학생
            # 더 단순한 음식 선호
            if detailed_category in ['치킨', '피자', '떡볶이', '햄버거']:
                teen_appeal *= 1.2
            elif detailed_category in ['샐러드', '건강식']:
                teen_appeal *= 0.5
        elif user_age <= 16:  # 중학생
            # 다양한 시도
            teen_appeal *= 1.0
        else:  # 고등학생
            # 가성비 중시
            if detailed_category in ['편의점', '분식']:
                teen_appeal *= 1.1
        
        # 최종 점수 = 기본점수 * (0.5 + 0.5 * 청소년선호도)
        # 선호도가 높으면 최대 100%, 낮으면 최소 50%
        adjusted_score = base_score * (0.5 + 0.5 * teen_appeal)
        
        logger.debug(f"청소년 점수 조정: {category} {base_score:.1f} -> {adjusted_score:.1f} (선호도: {teen_appeal:.1f})")
        
        return adjusted_score
    
    @classmethod
    def is_meal_card_friendly(cls, category: str) -> bool:
        """급식카드 사용 가능 여부 추정"""
        for cat, info in cls.CATEGORY_MAPPING.items():
            if cat.lower() == category.lower():
                return info['meal_card_common']
        
        # 일반적으로 급식카드 사용 가능한 카테고리
        meal_card_categories = ['한식', '중식', '분식', '치킨', '피자', '패스트푸드', '편의점']
        return category in meal_card_categories


# 테스트
if __name__ == "__main__":
    mapper = CategoryMapper()
    
    # 가게 테스트
    test_shops = [
        {'name': '샐러드박스 신사점', 'category': '양식'},
        {'name': '신전떡볶이', 'category': '분식'},
        {'name': 'BBQ치킨', 'category': '치킨'},
        {'name': 'GS25 편의점', 'category': '편의점'}
    ]
    
    print("=== 카테고리 세분화 테스트 ===")
    for shop in test_shops:
        detailed = mapper.get_detailed_category(shop)
        teen_score = mapper.get_teen_appeal_score(detailed)
        health_score = mapper.get_health_score(detailed)
        
        print(f"\n{shop['name']}:")
        print(f"  원래: {shop['category']} -> 세분화: {detailed}")
        print(f"  청소년 선호도: {teen_score:.1f}")
        print(f"  건강 점수: {health_score:.1f}")