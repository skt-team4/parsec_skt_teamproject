"""
날씨별 메뉴 추천 매핑 (청소년 대상)
급식카드 사용 18세 미만 청소년 취향 반영
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class WeatherMenuMapper:
    """날씨별 메뉴 추천 매핑 (청소년 특화)"""
    
    # 날씨별 추천 메뉴 및 키워드 (청소년 선호 반영)
    WEATHER_MENU_MAP = {
        '비': {
            'boost_categories': ['분식', '한식', '중식', '치킨'],
            'boost_keywords': [
                # 청소년이 좋아하는 비오는 날 메뉴
                '떡볶이', '라볶이', '짜파구리', '라면', '컵라면',
                '치킨', '순살치킨', '양념치킨', '간장치킨',
                '파전', '김치전', '감자전',
                '어묵', '순대', '튀김', '김말이',
                '짬뽕', '짜장면', '탕수육',
                '부대찌개', '김치찌개', '라면사리'
            ],
            'avoid_keywords': ['샐러드', '다이어트', '저칼로리'],
            'score_boost': 2.0,
            'message': '비 오는 날엔 떡볶이랑 튀김! 아니면 치킨도 좋지~',
            'emoji': '🌧️'
        },
        '더움': {
            'boost_categories': ['카페', '디저트', '편의점', '패스트푸드'],
            'boost_keywords': [
                # 청소년이 좋아하는 여름 메뉴
                '빙수', '팥빙수', '눈꽃빙수', '망고빙수',
                '아이스크림', '하겐다즈', '베스킨라빈스',
                '아이스아메리카노', '아아', '프라페', '스무디',
                '냉면', '물냉', '비냉', '쫄면',
                '김밥', '삼각김밥', '편의점도시락',
                '샌드위치', '서브웨이', '샐러드',
                '콜라', '사이다', '에이드', '탄산'
            ],
            'avoid_keywords': ['뜨거운', '국물', '매운탕'],
            'score_boost': 1.8,
            'message': '더울 땐 시원한 아아랑 아이스크림! 편의점 ㄱㄱ?',
            'emoji': '☀️'
        },
        '추움': {
            'boost_categories': ['분식', '한식', '중식', '편의점'],
            'boost_keywords': [
                # 청소년이 좋아하는 겨울 메뉴
                '떡볶이', '라볶이', '로제떡볶이',
                '어묵', '오뎅', '붕어빵', '호떡', '호빵',
                '라면', '진라면', '신라면', '짜파게티',
                '김밥', '참치김밥', '김치김밥',
                '우동', '튀김우동', '어묵우동',
                '국밥', '순대국', '김치찌개',
                '핫초코', '따뜻한', '따끈한'
            ],
            'avoid_keywords': ['냉면', '아이스', '빙수'],
            'score_boost': 1.8,
            'message': '추울 땐 떡볶이에 어묵 국물! 편의점 컵라면도 굿~',
            'emoji': '❄️'
        },
        '맑음': {
            'boost_categories': ['치킨', '피자', '버거', '편의점'],
            'boost_keywords': [
                # 날씨 좋을 때 청소년 선호 메뉴
                '치킨', '피자', '버거', '햄버거',
                '도시락', '편도', '삼각김밥',
                '김밥', '떡볶이', '순대',
                '샌드위치', '토스트',
                '음료', '커피'
            ],
            'avoid_keywords': [],
            'score_boost': 1.2,
            'message': '날씨 좋은데 치킨 시켜먹을까? 피자도 좋고!',
            'emoji': '🌤️'
        },
        '흐림': {
            'boost_categories': ['분식', '패스트푸드', '치킨', '중식'],
            'boost_keywords': [
                # 우울한 날씨 청소년 컴포트 푸드
                '떡볶이', '순대', '튀김', '라면',
                '치킨', '피자', '버거',
                '짜장면', '짬뽕', '탕수육',
                '도넛', '마카롱', '케이크',
                '핫도그', '감자튀김'
            ],
            'avoid_keywords': [],
            'score_boost': 1.3,
            'message': '우중충한 날엔 치킨이나 떡볶이로 기분 UP!',
            'emoji': '☁️'
        },
        '눈': {
            'boost_categories': ['분식', '편의점', '한식'],
            'boost_keywords': [
                # 눈오는 날 청소년 메뉴
                '붕어빵', '호떡', '어묵', '오뎅',
                '떡볶이', '순대', '튀김',
                '컵라면', '핫식스', '핫초코',
                '우동', '라면', '김밥'
            ],
            'avoid_keywords': ['아이스크림', '빙수'],
            'score_boost': 1.7,
            'message': '눈 오는 날엔 붕어빵이지! 떡볶이도 좋고~',
            'emoji': '🌨️'
        }
    }
    
    # 청소년 선호 브랜드/체인점 (급식카드 사용 가능한 곳 위주)
    TEEN_PREFERRED_BRANDS = {
        '치킨': ['BBQ', 'BHC', '교촌', '굽네', '페리카나', '호식이두마리', '노랑통닭'],
        '피자': ['도미노', '피자헛', '피자스쿨', '미스터피자', '파파존스'],
        '버거': ['맥도날드', '버거킹', '롯데리아', 'KFC', '맘스터치', '노브랜드버거'],
        '분식': ['신전떡볶이', '죠스떡볶이', '엽기떡볶이', '김밥천국', '김가네'],
        '편의점': ['CU', 'GS25', '세븐일레븐', '이마트24', '미니스톱'],
        '카페': ['메가커피', '컴포즈', '빽다방', '이디야', '더벤티'],
        '중식': ['홍콩반점', '일품', '짬뽕지존', '역전우동']
    }
    
    @classmethod
    def get_weather_preferences(cls, weather_condition: str, age: int = 15) -> Dict[str, Any]:
        """
        날씨 조건과 나이에 맞는 선호도 정보 반환
        
        Args:
            weather_condition: 날씨 상태
            age: 사용자 나이 (기본 15세)
        
        Returns:
            날씨별 선호 정보
        """
        weather_normalized = cls._normalize_weather(weather_condition)
        
        prefs = cls.WEATHER_MENU_MAP.get(weather_normalized, {
            'boost_categories': ['분식', '치킨', '피자'],
            'boost_keywords': ['떡볶이', '치킨', '피자'],
            'avoid_keywords': [],
            'score_boost': 1.0,
            'message': '오늘 뭐 먹지? 떡볶이 어때?',
            'emoji': '🍽️'
        })
        
        # 나이별 조정 (초등학생 vs 중고등학생)
        if age <= 13:  # 초등학생
            # 더 단순하고 친숙한 메뉴 강조
            prefs['boost_keywords'] = [kw for kw in prefs['boost_keywords'] 
                                       if kw in ['떡볶이', '김밥', '치킨', '피자', '햄버거', '아이스크림']]
        
        return prefs
    
    @classmethod
    def _normalize_weather(cls, weather: str) -> str:
        """날씨 조건 정규화"""
        weather_lower = weather.lower()
        
        # 영어 -> 한글 매핑
        mappings = {
            'rain': '비',
            'rainy': '비',
            'hot': '더움',
            'heat': '더움',
            'cold': '추움',
            'cool': '추움',
            'clear': '맑음',
            'sunny': '맑음',
            'cloudy': '흐림',
            'overcast': '흐림',
            'snow': '눈',
            'snowy': '눈'
        }
        
        # 영어 키워드 체크
        for eng, kor in mappings.items():
            if eng in weather_lower:
                return kor
        
        # 한글 키워드 체크
        korean_weathers = ['비', '더움', '추움', '맑음', '흐림', '눈']
        for kw in korean_weathers:
            if kw in weather:
                return kw
        
        # 온도 기반 판단
        if '도' in weather:
            try:
                temp = int(''.join(filter(str.isdigit, weather.split('도')[0])))
                if temp >= 28:
                    return '더움'
                elif temp <= 10:
                    return '추움'
            except:
                pass
        
        return '맑음'  # 기본값
    
    @classmethod
    def calculate_weather_score(cls, 
                               shop_or_menu: Dict[str, Any],
                               weather_condition: str,
                               base_score: float = 1.0,
                               user_age: int = 15) -> float:
        """
        날씨 기반 점수 계산 (청소년 특화)
        
        Args:
            shop_or_menu: 가게 또는 메뉴 정보
            weather_condition: 날씨 상태
            base_score: 기본 점수
            user_age: 사용자 나이
        
        Returns:
            날씨 반영 점수
        """
        prefs = cls.get_weather_preferences(weather_condition, user_age)
        
        score = base_score
        name = shop_or_menu.get('name', '').lower()
        category = shop_or_menu.get('category', '').lower()
        description = shop_or_menu.get('description', '').lower()
        
        # 브랜드 체크 (청소년 선호 브랜드 가산점)
        for cat, brands in cls.TEEN_PREFERRED_BRANDS.items():
            for brand in brands:
                if brand.lower() in name:
                    score *= 1.2
                    logger.debug(f"청소년 선호 브랜드: {brand} x1.2")
                    break
        
        # 카테고리 매칭
        if category in [c.lower() for c in prefs['boost_categories']]:
            score *= 1.5
            logger.debug(f"날씨 카테고리 부스트: {category} x1.5")
        
        # 키워드 매칭
        text_to_check = f"{name} {description}".lower()
        
        # 부스트 키워드 체크
        boost_count = 0
        for keyword in prefs['boost_keywords']:
            if keyword.lower() in text_to_check:
                boost_count += 1
        
        if boost_count > 0:
            boost_factor = min(2.0, 1.0 + (boost_count * 0.3))
            score *= boost_factor
            logger.debug(f"날씨 키워드 부스트: {boost_count}개 매칭 x{boost_factor:.1f}")
        
        # 회피 키워드 체크
        avoid_count = 0
        for keyword in prefs['avoid_keywords']:
            if keyword.lower() in text_to_check:
                avoid_count += 1
        
        if avoid_count > 0:
            avoid_factor = max(0.3, 1.0 - (avoid_count * 0.2))
            score *= avoid_factor
            logger.debug(f"날씨 키워드 페널티: {avoid_count}개 매칭 x{avoid_factor:.1f}")
        
        # 급식카드 사용 가능 여부 체크
        if shop_or_menu.get('meal_card_available', False):
            score *= 1.3
            logger.debug("급식카드 사용 가능 x1.3")
        
        return score
    
    @classmethod
    def get_weather_message(cls, weather_condition: str, age: int = 15) -> str:
        """청소년 맞춤 날씨별 추천 메시지"""
        prefs = cls.get_weather_preferences(weather_condition, age)
        
        # 나이별 말투 조정
        if age <= 13:
            # 초등학생: 더 친근한 말투
            return f"{prefs['emoji']} {prefs['message'].replace('~', '!')}"
        else:
            # 중고등학생: 또래 말투
            return f"{prefs['emoji']} {prefs['message']}"
    
    @classmethod
    def is_weather_suitable(cls, 
                           menu_name: str,
                           weather_condition: str,
                           age: int = 15) -> bool:
        """
        특정 메뉴가 날씨와 연령에 적합한지 판단
        """
        prefs = cls.get_weather_preferences(weather_condition, age)
        menu_lower = menu_name.lower()
        
        # 부스트 키워드에 있으면 적합
        for keyword in prefs['boost_keywords']:
            if keyword.lower() in menu_lower:
                return True
        
        # 회피 키워드에 있으면 부적합
        for keyword in prefs['avoid_keywords']:
            if keyword.lower() in menu_lower:
                return False
        
        return True


# 테스트
if __name__ == "__main__":
    mapper = WeatherMenuMapper()
    
    # 날씨별 선호도 테스트
    print("=== 청소년 (15세) 날씨별 추천 ===")
    for weather in ['비', '더움', '추움']:
        prefs = mapper.get_weather_preferences(weather, age=15)
        print(f"\n{weather}: {prefs['message']}")
        print(f"  추천 카테고리: {prefs['boost_categories'][:3]}")
        print(f"  추천 메뉴: {prefs['boost_keywords'][:5]}")
    
    # 점수 계산 테스트
    test_shops = [
        {'name': '신전떡볶이', 'category': '분식', 'meal_card_available': True},
        {'name': 'BBQ치킨', 'category': '치킨', 'meal_card_available': True},
        {'name': '스타벅스', 'category': '카페', 'meal_card_available': False}
    ]
    
    for shop in test_shops:
        print(f"\n{shop['name']}:")
        for weather in ['비', '더움']:
            score = mapper.calculate_weather_score(shop, weather, 10.0, user_age=15)
            print(f"  {weather}: {score:.1f}점")