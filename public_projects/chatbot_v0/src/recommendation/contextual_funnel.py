"""
상황/규칙 기반 Funnel (Funnel 3)
시간대, 위치, 영업시간 등 컨텍스트 기반 추천
"""

import json
import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, time
import math

logger = logging.getLogger(__name__)


class ContextualFunnel:
    """상황/규칙 기반 후보 생성 Funnel"""
    
    def __init__(self, restaurants_path: Optional[str] = None):
        """
        Args:
            restaurants_path: 매장 데이터 파일 경로
        """
        if restaurants_path is None:
            from pathlib import Path
            restaurants_path = Path(__file__).parent.parent / 'data' / 'restaurants_real.json'
        self.restaurants_path = restaurants_path
        self.restaurants = []
        self._load_data()
    
    def _load_data(self):
        """매장 데이터 로드"""
        try:
            with open(self.restaurants_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.restaurants = data.get('shops', data.get('restaurants', []))
            
            logger.info(f"상황 Funnel: {len(self.restaurants)}개 매장 데이터 로드 완료")
            
        except Exception as e:
            logger.error(f"매장 데이터 로드 실패: {e}")
            self.restaurants = []
    
    def get_candidates(self, 
                      user_location: Optional[str] = None,
                      current_time: Optional[datetime] = None,
                      time_of_day: Optional[str] = None,
                      filters: Optional[Dict[str, Any]] = None,
                      limit: int = 30,
                      recent_categories: Set[str] = None,
                      user_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        상황 기반 후보 매장 반환 (다양성 로직 추가)
        
        Args:
            user_location: 사용자 위치 (구 단위, 예: "관악구")
            current_time: 현재 시간 
            time_of_day: 시간대 ("breakfast", "lunch", "dinner", "snack")
            filters: 추가 필터 조건
            limit: 반환할 후보 수
            recent_categories: 최근 추천된 카테고리 (제외용)
            user_context: 날씨, 영양 정보 등 컨텍스트
            
        Returns:
            상황에 맞는 후보 매장 리스트
        """
        if current_time is None:
            current_time = datetime.now()
        
        if recent_categories is None:
            recent_categories = set()
        
        candidates = []
        
        for restaurant in self.restaurants:
            # 최근 추천 카테고리 제외 (다양성 확보)
            category = restaurant.get('category', '')
            if category.lower() in {cat.lower() for cat in recent_categories}:
                continue
            # 컨텍스트 점수 계산
            context_score = self._calculate_context_score(
                restaurant, user_location, current_time, time_of_day, user_context
            )
            
            # 기본 필터 적용
            if not self._passes_basic_filters(restaurant, filters or {}):
                continue
            
            shop_id = restaurant.get('id', restaurant.get('shopId', ''))
            candidate = {
                'shop_id': shop_id,
                'shop_name': restaurant.get('name', restaurant.get('shopName', '')),
                'category': restaurant.get('category', ''),
                'funnel_source': 'contextual',
                'context_score': context_score,
                'reason': self._get_context_reason(
                    restaurant, user_location, current_time, time_of_day
                )
            }
            candidates.append(candidate)
        
        # 컨텍스트 점수로 정렬
        candidates.sort(key=lambda x: x['context_score'], reverse=True)
        
        logger.info(f"상황 Funnel: {len(candidates[:limit])}개 후보 생성 (위치: {user_location}, 시간: {time_of_day})")
        return candidates[:limit]
    
    def _calculate_context_score(self, 
                                restaurant: Dict[str, Any],
                                user_location: Optional[str],
                                current_time: datetime,
                                time_of_day: Optional[str],
                                user_context: Optional[Dict[str, Any]] = None) -> float:
        """상황 기반 점수 계산 (Context Enrich 정보 활용)"""
        score = 0.0
        
        # 1. 위치 기반 점수 (최대 40점)
        if user_location:
            location_score = self._get_location_score(restaurant, user_location)
            score += location_score
        
        # 2. 영업시간 기반 점수 (최대 30점)
        operating_score = self._get_operating_score(restaurant, current_time)
        score += operating_score
        
        # 3. 시간대 기반 점수 (최대 30점)
        if time_of_day:
            time_score = self._get_time_of_day_score(restaurant, time_of_day)
            score += time_score
        
        # 4. Context Enrich 기반 추가 점수
        if user_context:
            category = restaurant.get('category', '').lower()
            
            # 날씨 기반 가중치 (청소년 특화)
            if 'weather' in user_context:
                try:
                    from src.utils.weather_menu_mapper import WeatherMenuMapper
                    weather = user_context['weather'].get('condition', '')
                    
                    # 청소년 연령 추정 (페르소나 기반)
                    user_age = user_context.get('age', 15)
                    
                    # 날씨 점수 계산
                    weather_score = WeatherMenuMapper.calculate_weather_score(
                        restaurant, 
                        weather, 
                        base_score=10.0,
                        user_age=user_age
                    )
                    score += (weather_score - 10.0)  # 기본점수 제외한 추가점수만
                    
                except ImportError:
                    # Fallback: 기존 로직
                    weather = user_context['weather'].get('condition', '')
                    temp = user_context['weather'].get('temp', 20)
                    
                    if weather in ['rain', 'Rain', '비']:
                        if any(w in category for w in ['떡볶이', '치킨', '라면']):
                            score += 20
                    elif weather in ['clear', 'Clear', '맑음'] and temp > 25:
                        if any(w in category for w in ['아이스', '빙수', '냉면']):
                            score += 15
            
            # 영양 기반 가중치
            if 'nutrition_status' in user_context:
                issues = user_context['nutrition_status'].get('current_issues', [])
                if 'vitamin_deficiency' in issues and any(w in category for w in ['샐러드', '과일', '채소']):
                    score += 15
                elif 'protein_deficiency' in issues and any(w in category for w in ['고기', '치킨', '육류']):
                    score += 15
        
        return score
    
    def _get_location_score(self, restaurant: Dict[str, Any], user_location: str) -> float:
        """위치 기반 점수 계산 (실제 거리 사용)"""
        try:
            from src.utils.location_utils import calculate_distance, get_coords_from_text
        except ImportError:
            # location_utils가 없으면 기존 로직 사용
            return self._get_location_score_fallback(restaurant, user_location)
        
        # 사용자 위치 좌표 얻기
        user_coords = get_coords_from_text(user_location) if user_location else None
        if not user_coords:
            return self._get_location_score_fallback(restaurant, user_location)
        
        user_lat, user_lng = user_coords
        
        # 가게 좌표 확인
        shop_lat = restaurant.get('latitude')
        shop_lng = restaurant.get('longitude')
        
        if not shop_lat or not shop_lng:
            # 좌표가 없으면 주소 기반 점수
            return self._get_location_score_fallback(restaurant, user_location)
        
        # 거리 계산
        distance_km = calculate_distance(user_lat, user_lng, shop_lat, shop_lng)
        
        # 거리 기반 점수 (최대 40점)
        if distance_km <= 0.5:
            return 40.0  # 500m 이내
        elif distance_km <= 1.0:
            return 35.0  # 1km 이내
        elif distance_km <= 2.0:
            return 30.0  # 2km 이내
        elif distance_km <= 3.0:
            return 25.0  # 3km 이내
        elif distance_km <= 5.0:
            return 15.0  # 5km 이내
        else:
            return max(5.0, 40.0 - distance_km * 5)  # 5km 초과
    
    def _get_location_score_fallback(self, restaurant: Dict[str, Any], user_location: str) -> float:
        """위치 기반 점수 계산 (fallback - 주소 텍스트 매칭)"""
        address = restaurant.get('address', '') or restaurant.get('location', {}).get('address', '')
        
        if not user_location:
            return 10.0  # 위치 정보 없으면 기본 점수
        
        # 같은 구/동에 있으면 높은 점수
        if user_location in address:
            return 30.0
        
        # 서울 지역이면 중간 점수
        if '서울' in address and '서울' in user_location:
            return 20.0
        
        # 경기도면 낮은 점수
        if '경기' in address and '경기' in user_location:
            return 15.0
        
        return 5.0  # 기본 점수
    
    def _get_operating_score(self, restaurant: Dict[str, Any], current_time: datetime) -> float:
        """영업시간 기반 점수 계산"""
        hours = restaurant.get('hours', {})
        open_time_str = hours.get('open')
        close_time_str = hours.get('close')
        
        if not (open_time_str and close_time_str):
            return 10.0  # 정보 없으면 기본 점수
        
        try:
            current_time_only = current_time.time()
            open_time = datetime.strptime(open_time_str, '%H:%M').time()
            close_time = datetime.strptime(close_time_str, '%H:%M').time()
            
            # 현재 영업 중이면 높은 점수
            if self._is_open_now(current_time_only, open_time, close_time):
                return 30.0
            
            # 곧 열 예정이면 중간 점수 (1시간 이내)
            if self._opens_soon(current_time_only, open_time):
                return 15.0
            
            return 5.0  # 영업시간 외
            
        except ValueError:
            return 10.0  # 시간 파싱 실패
    
    def _is_open_now(self, current_time: time, open_time: time, close_time: time) -> bool:
        """현재 영업 중인지 확인"""
        if close_time < open_time:  # 자정 넘어서 영업 (예: 22:00 - 02:00)
            return current_time >= open_time or current_time <= close_time
        else:  # 일반적인 경우
            return open_time <= current_time <= close_time
    
    def _opens_soon(self, current_time: time, open_time: time) -> bool:
        """1시간 이내에 열 예정인지 확인"""
        current_minutes = current_time.hour * 60 + current_time.minute
        open_minutes = open_time.hour * 60 + open_time.minute
        
        # 1시간(60분) 이내에 열 예정
        time_diff = (open_minutes - current_minutes) % (24 * 60)
        return 0 < time_diff <= 60
    
    def _get_time_of_day_score(self, restaurant: Dict[str, Any], time_of_day: str) -> float:
        """시간대 기반 점수 계산"""
        category = restaurant.get('category', '').lower()
        
        # 시간대별 카테고리 선호도
        time_category_preferences = {
            'breakfast': {
                '카페': 30, '기타/디저트': 25, '베이커리': 30,
                '한식': 15, '분식': 20
            },
            'lunch': {
                '한식': 30, '중식': 25, '일식': 25, '분식': 20,
                '양식': 20, '치킨': 15
            },
            'dinner': {
                '한식': 25, '중식': 25, '일식': 25, '양식': 30,
                '치킨': 30, '고기': 30, '분식': 15
            },
            'snack': {
                '카페': 30, '기타/디저트': 30, '치킨': 25,
                '분식': 25, '베이커리': 20
            }
        }
        
        preferences = time_category_preferences.get(time_of_day, {})
        
        # 카테고리 매칭으로 점수 계산
        for cat_keyword, score in preferences.items():
            if cat_keyword in category:
                return float(score)
        
        return 10.0  # 기본 점수
    
    def _passes_basic_filters(self, restaurant: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """기본 필터 조건 확인"""
        # 카테고리 필터
        if filters.get('category'):
            category_filter = filters['category'].lower()
            if category_filter not in restaurant.get('category', '').lower():
                return False
        
        # 카테고리 제외 필터 (MODIFY_REQUEST 처리)
        if filters.get('exclude_category'):
            exclude_categories = filters['exclude_category']
            # 리스트가 아니면 리스트로 변환
            if isinstance(exclude_categories, str):
                exclude_categories = [exclude_categories]
            
            # 모든 제외 카테고리 체크
            for exclude_cat in exclude_categories:
                exclude_filter = exclude_cat.lower()
                if exclude_filter in restaurant.get('category', '').lower():
                    logger.debug(f"제외: {restaurant.get('name')} - 카테고리 {restaurant.get('category')}가 {exclude_filter} 포함")
                    return False  # 해당 카테고리면 제외
        
        # 착한가게 필터
        if filters.get('is_good_influence'):
            if not restaurant.get('attributes', {}).get('isGoodShop', False):
                return False
        
        # 최대 가격 필터
        if filters.get('max_price'):
            # MenuHelper를 사용하여 실제 메뉴 가격 확인
            try:
                from src.utils.menu_helper import get_shop_min_price
                shop_id = restaurant.get('id') or restaurant.get('shop_id') or restaurant.get('shopId')
                if shop_id:
                    min_price = get_shop_min_price(shop_id)
                    if min_price and min_price > filters['max_price']:
                        logger.debug(f"제외: {restaurant.get('name')} - 최소가격 {min_price}원이 한도 {filters['max_price']}원 초과")
                        return False
            except ImportError:
                # Fallback: 기존 방식
                menus = restaurant.get('menus', [])
                if menus:
                    min_price = min(menu.get('price', float('inf')) for menu in menus)
                    if min_price > filters['max_price']:
                        logger.debug(f"제외: {restaurant.get('name')} - 최소가격 {min_price}원이 한도 {filters['max_price']}원 초과")
                        return False
        
        return True
    
    def _get_context_reason(self, 
                           restaurant: Dict[str, Any],
                           user_location: Optional[str],
                           current_time: datetime,
                           time_of_day: Optional[str]) -> str:
        """상황 기반 추천 이유 생성"""
        reasons = []
        
        # 위치 이유
        if user_location:
            address = restaurant.get('location', {}).get('address', '')
            if user_location in address:
                reasons.append(f'{user_location} 근처')
        
        # 영업시간 이유
        hours = restaurant.get('hours', {})
        if hours.get('open') and hours.get('close'):
            try:
                current_time_only = current_time.time()
                open_time = datetime.strptime(hours['open'], '%H:%M').time()
                close_time = datetime.strptime(hours['close'], '%H:%M').time()
                
                if self._is_open_now(current_time_only, open_time, close_time):
                    reasons.append('현재 영업중')
                elif self._opens_soon(current_time_only, open_time):
                    reasons.append('곧 영업 시작')
            except:
                pass
        
        # 시간대 이유
        if time_of_day:
            category = restaurant.get('category', '').lower()
            time_reasons = {
                'breakfast': '아침 추천',
                'lunch': '점심 추천', 
                'dinner': '저녁 추천',
                'snack': '간식 추천'
            }
            if time_of_day in time_reasons:
                reasons.append(time_reasons[time_of_day])
        
        return ' · '.join(reasons) if reasons else '상황 맞춤'


# 테스트 함수
def test_contextual_funnel():
    """상황 Funnel 테스트"""
    funnel = ContextualFunnel()
    
    print("=== 상황/규칙 기반 Funnel 테스트 ===")
    
    # 점심시간 관악구 근처 추천
    lunch_candidates = funnel.get_candidates(
        user_location="관악구",
        time_of_day="lunch",
        limit=5
    )
    print(f"\n점심시간 관악구 근처 추천 Top 5:")
    for i, candidate in enumerate(lunch_candidates, 1):
        print(f"{i}. {candidate['shop_name']} ({candidate['category']}) - {candidate['context_score']:.1f}점")
        print(f"   이유: {candidate['reason']}")
    
    # 저녁시간 전체 지역 추천
    dinner_candidates = funnel.get_candidates(
        time_of_day="dinner",
        limit=3
    )
    print(f"\n저녁시간 추천 Top 3:")
    for i, candidate in enumerate(dinner_candidates, 1):
        print(f"{i}. {candidate['shop_name']} ({candidate['category']}) - {candidate['context_score']:.1f}점")
        print(f"   이유: {candidate['reason']}")
    
    # 현재 시간 기준 영업중인 곳
    current_time = datetime.now().replace(hour=14, minute=30)  # 오후 2시 30분으로 가정
    open_candidates = funnel.get_candidates(
        current_time=current_time,
        limit=3
    )
    print(f"\n오후 2시 30분 영업중인 곳 Top 3:")
    for i, candidate in enumerate(open_candidates, 1):
        print(f"{i}. {candidate['shop_name']} - {candidate['context_score']:.1f}점")
        print(f"   이유: {candidate['reason']}")


if __name__ == "__main__":
    test_contextual_funnel()