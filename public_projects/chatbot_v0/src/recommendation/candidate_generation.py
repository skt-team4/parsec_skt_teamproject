"""
Layer 1: 4-Funnel 후보 생성 모델
대량의 식당 데이터에서 초기 후보군을 생성하는 시스템
"""

import numpy as np
import pandas as pd
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json
import random
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CandidateGenerationConfig:
    """4-Funnel 후보 생성 설정"""
    
    # 각 채널별 후보 수
    popularity_candidates: int = 30      # 인기도 기반
    distance_candidates: int = 25        # 거리 기반  
    category_candidates: int = 20        # 카테고리 기반
    personalized_candidates: int = 25    # 개인화 기반
    
    # 최종 후보 수 (중복 제거 후)
    max_final_candidates: int = 50
    
    # 필터링 조건
    min_rating: float = 3.0             # 최소 평점
    max_distance_km: float = 10.0       # 최대 거리 (km)


class RestaurantDatabase:
    """식당 데이터베이스 (급식카드 가맹점 포함)"""
    
    def __init__(self, data_path: Optional[str] = None):
        self.restaurants = []
        self.load_restaurants(data_path)
    
    def load_restaurants(self, data_path: Optional[str] = None):
        """식당 데이터 로드"""
        if data_path and Path(data_path).exists():
            # 실제 데이터 파일이 있으면 로드
            with open(data_path, 'r', encoding='utf-8') as f:
                self.restaurants = json.load(f)
        else:
            # 없으면 테스트용 데이터 생성
            self.restaurants = self._generate_test_restaurants()
        
        logger.info(f"식당 데이터 로드 완료: {len(self.restaurants)}개")
    
    def _generate_test_restaurants(self, count: int = 300) -> List[Dict[str, Any]]:
        """테스트용 급식카드 가맹점 데이터 생성"""
        categories = ['korean', 'chinese', 'chicken', 'pizza', 'snack', 'cafe', 'japanese', 'western']
        meal_card_categories = ['korean', 'chinese', 'chicken', 'pizza', 'snack']  # 급식카드 사용 가능
        locations = ['학교앞', '아파트단지', '주택가', '시장', '상가', '버스정류장']
        
        restaurants = []
        for i in range(count):
            category = random.choice(categories)
            is_meal_card = category in meal_card_categories
            
            # 급식카드 가맹점은 학교 근처에 많이 위치
            if is_meal_card:
                location = random.choices(locations, weights=[0.4, 0.2, 0.2, 0.1, 0.05, 0.05])[0]
                base_popularity = random.uniform(0.6, 0.9)  # 높은 인기도
            else:
                location = random.choice(locations)
                base_popularity = random.uniform(0.3, 0.7)
            
            # 가격 설정
            if category == 'snack':
                avg_price = random.randint(3000, 8000)
            elif category in ['korean', 'chinese']:
                avg_price = random.randint(6000, 12000)
            elif category in ['chicken', 'pizza']:
                avg_price = random.randint(8000, 18000)
            else:
                avg_price = random.randint(10000, 25000)
            
            restaurant = {
                'shop_id': f'shop_{i:03d}',
                'shop_name': f'{category.capitalize()}_{location}_{i}',
                'category': category,
                'location': location,
                'coordinates': {
                    'lat': 37.5 + random.uniform(-0.1, 0.1),
                    'lng': 126.9 + random.uniform(-0.1, 0.1)
                },
                'rating': round(random.uniform(3.0, 4.8), 1),
                'review_count': random.randint(10, 500),
                'avg_price': avg_price,
                'price_range': self._get_price_range(avg_price),
                'base_popularity': base_popularity,
                'meal_card_available': is_meal_card,
                'student_discount': random.random() > 0.7 if is_meal_card else False,
                'near_school': random.random() > 0.4 if is_meal_card else random.random() > 0.8,
                'quick_service': random.random() > 0.3,
                'is_good_influence': random.random() > 0.8,
                'has_delivery': random.random() > 0.4,
                'has_parking': random.random() > 0.6,
                'open_hours': '09:00-22:00'
            }
            restaurants.append(restaurant)
        
        return restaurants
    
    def _get_price_range(self, price: int) -> str:
        """가격대 분류"""
        if price < 8000:
            return 'low'
        elif price < 15000:
            return 'medium'
        elif price < 25000:
            return 'high'
        else:
            return 'very_high'
    
    def get_all_restaurants(self) -> List[Dict[str, Any]]:
        """모든 식당 반환"""
        return self.restaurants
    
    def get_restaurants_by_category(self, category: str) -> List[Dict[str, Any]]:
        """카테고리별 식당 조회"""
        return [r for r in self.restaurants if r['category'] == category]
    
    def get_meal_card_restaurants(self) -> List[Dict[str, Any]]:
        """급식카드 사용 가능 식당만 조회"""
        return [r for r in self.restaurants if r.get('meal_card_available', False)]


class FourFunnelCandidateGenerator:
    """4-Funnel 후보 생성기"""
    
    def __init__(self, config: Optional[CandidateGenerationConfig] = None):
        self.config = config or CandidateGenerationConfig()
        self.restaurant_db = RestaurantDatabase()
        
        logger.info("4-Funnel 후보 생성기 초기화 완료")
    
    def generate_candidates(self, 
                          user_profile: Dict[str, Any],
                          context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        4개 채널로 후보 생성
        
        Args:
            user_profile: 사용자 프로필
            context: 상황 정보 (위치, 시간 등)
        
        Returns:
            후보 식당 리스트
        """
        
        logger.info("4-Funnel 후보 생성 시작")
        
        all_restaurants = self.restaurant_db.get_all_restaurants()
        
        # 급식카드 사용자인지 확인
        is_meal_card_user = self._is_meal_card_user(user_profile)
        if is_meal_card_user:
            # 급식카드 사용자는 가맹점만 대상
            all_restaurants = self.restaurant_db.get_meal_card_restaurants()
            logger.info(f"급식카드 사용자 - 가맹점만 대상: {len(all_restaurants)}개")
        
        # 기본 필터링
        filtered_restaurants = self._apply_basic_filters(all_restaurants, user_profile, context)
        
        candidates = {}  # shop_id를 키로 사용해서 중복 제거
        
        # Funnel 1: 인기도 기반
        popularity_candidates = self._popularity_funnel(filtered_restaurants, user_profile, context)
        for candidate in popularity_candidates[:self.config.popularity_candidates]:
            candidates[candidate['shop_id']] = candidate
        
        # Funnel 2: 거리 기반  
        distance_candidates = self._distance_funnel(filtered_restaurants, user_profile, context)
        for candidate in distance_candidates[:self.config.distance_candidates]:
            candidates[candidate['shop_id']] = candidate
        
        # Funnel 3: 카테고리 기반
        category_candidates = self._category_funnel(filtered_restaurants, user_profile, context)
        for candidate in category_candidates[:self.config.category_candidates]:
            candidates[candidate['shop_id']] = candidate
        
        # Funnel 4: 개인화 기반
        personalized_candidates = self._personalized_funnel(filtered_restaurants, user_profile, context)
        for candidate in personalized_candidates[:self.config.personalized_candidates]:
            candidates[candidate['shop_id']] = candidate
        
        # 최종 후보 리스트
        final_candidates = list(candidates.values())[:self.config.max_final_candidates]
        
        logger.info(f"4-Funnel 후보 생성 완료: {len(final_candidates)}개")
        
        return final_candidates
    
    def _is_meal_card_user(self, user_profile: Dict[str, Any]) -> bool:
        """급식카드 사용자인지 판단"""
        age_range = user_profile.get('age_range', '')
        is_student = 'student' in user_profile.get('persona', '').lower()
        has_meal_card = user_profile.get('meal_card', False)
        
        return '10s' in age_range or is_student or has_meal_card
    
    def _apply_basic_filters(self, 
                           restaurants: List[Dict[str, Any]], 
                           user_profile: Dict[str, Any],
                           context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """기본 필터링 (평점, 거리 등)"""
        filtered = []
        
        user_budget = user_profile.get('daily_budget', 50000)
        
        for restaurant in restaurants:
            # 평점 필터
            if restaurant['rating'] < self.config.min_rating:
                continue
            
            # 예산 필터 (급식카드 사용자용)
            if user_budget <= 10000:  # 급식카드 한도
                if restaurant['avg_price'] > user_budget:
                    continue
            
            # 운영시간 필터 (단순화)
            # 실제로는 현재 시간과 비교해야 함
            
            filtered.append(restaurant)
        
        logger.info(f"기본 필터링 후: {len(filtered)}개")
        return filtered
    
    def _popularity_funnel(self, 
                         restaurants: List[Dict[str, Any]], 
                         user_profile: Dict[str, Any],
                         context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Funnel 1: 인기도 기반 후보"""
        
        scored_restaurants = []
        for restaurant in restaurants:
            # 인기도 점수 계산
            popularity_score = (
                restaurant['base_popularity'] * 0.4 +
                (restaurant['rating'] / 5.0) * 0.3 +
                min(restaurant['review_count'] / 100, 1.0) * 0.3
            ) * 10  # 10점 만점으로 스케일링
            
            restaurant_copy = restaurant.copy()
            restaurant_copy['collaborative_score'] = popularity_score
            restaurant_copy['content_score'] = 0
            restaurant_copy['context_score'] = 0  
            restaurant_copy['base_score'] = popularity_score
            
            scored_restaurants.append(restaurant_copy)
        
        # 점수 순으로 정렬
        scored_restaurants.sort(key=lambda x: x['collaborative_score'], reverse=True)
        
        logger.info(f"인기도 기반 후보: {len(scored_restaurants)}개")
        return scored_restaurants
    
    def _distance_funnel(self,
                        restaurants: List[Dict[str, Any]], 
                        user_profile: Dict[str, Any],
                        context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Funnel 2: 거리 기반 후보 (실제 위경도 사용)"""
        try:
            from src.utils.location_utils import calculate_distance, get_coords_from_text
        except ImportError:
            # location_utils가 없으면 기존 로직 사용
            logger.warning("location_utils 임포트 실패, 기본 거리 로직 사용")
            return self._distance_funnel_fallback(restaurants, user_profile, context)
        
        # 사용자 위치 좌표 얻기
        user_lat = context.get('user_latitude')
        user_lng = context.get('user_longitude')
        
        # 좌표가 없으면 텍스트 위치에서 변환
        if not user_lat or not user_lng:
            user_location_text = context.get('user_location', user_profile.get('location', ''))
            if user_location_text:
                coords = get_coords_from_text(user_location_text)
                if coords:
                    user_lat, user_lng = coords
                    logger.info(f"사용자 위치 좌표 변환: {user_location_text} -> ({user_lat}, {user_lng})")
        
        # 그래도 없으면 기본값 사용 (페르소나 위치 또는 서울역)
        if not user_lat or not user_lng:
            # 페르소나 기본 위치 사용
            if 'default_location' in user_profile:
                user_lat = user_profile['default_location'].get('latitude', 37.5663)
                user_lng = user_profile['default_location'].get('longitude', 126.9779)
            else:
                # 서울역 기본값
                user_lat, user_lng = 37.5663, 126.9779
            logger.warning(f"사용자 위치 없음, 기본값 사용: ({user_lat}, {user_lng})")
        
        scored_restaurants = []
        for restaurant in restaurants:
            # 가게 좌표 확인
            shop_lat = restaurant.get('latitude')
            shop_lng = restaurant.get('longitude')
            
            # 좌표가 없으면 coordinates 필드 확인
            if not shop_lat or not shop_lng:
                coords = restaurant.get('coordinates', {})
                shop_lat = coords.get('lat')
                shop_lng = coords.get('lng')
            
            # 거리 계산
            if shop_lat and shop_lng:
                distance_km = calculate_distance(user_lat, user_lng, shop_lat, shop_lng)
                
                # 거리 기반 점수 계산 (가까울수록 높은 점수)
                if distance_km <= 0.5:
                    distance_score = 10.0  # 500m 이내
                elif distance_km <= 1.0:
                    distance_score = 9.0   # 1km 이내
                elif distance_km <= 2.0:
                    distance_score = 8.0   # 2km 이내
                elif distance_km <= 3.0:
                    distance_score = 7.0   # 3km 이내
                elif distance_km <= 5.0:
                    distance_score = 5.0   # 5km 이내
                else:
                    distance_score = max(1.0, 10.0 - distance_km)  # 5km 초과
                
                restaurant_copy = restaurant.copy()
                restaurant_copy['distance_km'] = round(distance_km, 2)
                restaurant_copy['distance_score'] = distance_score
            else:
                # 좌표가 없는 경우 낮은 점수
                distance_score = 3.0
                restaurant_copy = restaurant.copy()
                restaurant_copy['distance_km'] = None
                restaurant_copy['distance_score'] = distance_score
            
            restaurant_copy['collaborative_score'] = 0
            restaurant_copy['content_score'] = distance_score
            restaurant_copy['context_score'] = 0
            restaurant_copy['base_score'] = distance_score
            
            scored_restaurants.append(restaurant_copy)
        
        # 거리 점수 순으로 정렬
        scored_restaurants.sort(key=lambda x: x.get('distance_score', 0), reverse=True)
        
        logger.info(f"거리 기반 후보: {len(scored_restaurants)}개 (사용자 위치: {user_lat:.4f}, {user_lng:.4f})")
        return scored_restaurants
    
    def _distance_funnel_fallback(self,
                        restaurants: List[Dict[str, Any]], 
                        user_profile: Dict[str, Any],
                        context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Funnel 2: 거리 기반 후보 (fallback)"""
        
        user_location = context.get('user_location', '학교앞')  # 기본값
        
        scored_restaurants = []
        for restaurant in restaurants:
            # 거리 점수 계산 (단순화: 같은 지역이면 높은 점수)
            if restaurant.get('location') == user_location:
                distance_score = 9.0
            elif restaurant.get('near_school', False):
                distance_score = 7.0
            else:
                distance_score = random.uniform(3.0, 6.0)  # 랜덤 거리
            
            restaurant_copy = restaurant.copy()
            restaurant_copy['collaborative_score'] = 0
            restaurant_copy['content_score'] = distance_score
            restaurant_copy['context_score'] = 0
            restaurant_copy['base_score'] = distance_score
            
            scored_restaurants.append(restaurant_copy)
        
        # 거리 점수 순으로 정렬
        scored_restaurants.sort(key=lambda x: x['content_score'], reverse=True)
        
        logger.info(f"거리 기반 후보 (fallback): {len(scored_restaurants)}개")
        return scored_restaurants
    
    def _category_funnel(self,
                        restaurants: List[Dict[str, Any]], 
                        user_profile: Dict[str, Any],
                        context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Funnel 3: 카테고리 기반 후보"""
        
        preferred_categories = user_profile.get('preferred_categories', ['korean'])
        
        scored_restaurants = []
        for restaurant in restaurants:
            # 카테고리 매칭 점수
            if restaurant['category'] in preferred_categories:
                category_score = 8.5
            else:
                category_score = random.uniform(2.0, 5.0)
            
            restaurant_copy = restaurant.copy()
            restaurant_copy['collaborative_score'] = 0
            restaurant_copy['content_score'] = 0
            restaurant_copy['context_score'] = category_score
            restaurant_copy['base_score'] = category_score
            
            scored_restaurants.append(restaurant_copy)
        
        # 카테고리 점수 순으로 정렬
        scored_restaurants.sort(key=lambda x: x['context_score'], reverse=True)
        
        logger.info(f"카테고리 기반 후보: {len(scored_restaurants)}개")
        return scored_restaurants
    
    def _personalized_funnel(self,
                           restaurants: List[Dict[str, Any]], 
                           user_profile: Dict[str, Any],
                           context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Funnel 4: 개인화 기반 후보"""
        
        scored_restaurants = []
        for restaurant in restaurants:
            # 개인화 점수 계산
            personalized_score = 0
            
            # 선호 카테고리 보너스
            preferred_categories = user_profile.get('preferred_categories', [])
            if restaurant['category'] in preferred_categories:
                personalized_score += 3
            
            # 예산 적합성
            user_budget = user_profile.get('daily_budget', 20000)
            price_diff = abs(restaurant['avg_price'] - user_budget) / user_budget
            if price_diff < 0.5:  # 예산 50% 범위 내
                personalized_score += 2
            
            # 급식카드 사용자 특화
            if self._is_meal_card_user(user_profile):
                if restaurant.get('meal_card_available', False):
                    personalized_score += 4
                if restaurant.get('student_discount', False):
                    personalized_score += 1
                if restaurant.get('near_school', False):
                    personalized_score += 1
            
            # 착한가게 보너스
            if restaurant.get('is_good_influence', False):
                personalized_score += 1
            
            # 기본 점수 (3-8점 범위)
            base_score = 3 + personalized_score
            
            restaurant_copy = restaurant.copy()
            restaurant_copy['collaborative_score'] = 0
            restaurant_copy['content_score'] = 0
            restaurant_copy['context_score'] = 0
            restaurant_copy['base_score'] = base_score
            restaurant_copy['personalized_score'] = base_score
            
            scored_restaurants.append(restaurant_copy)
        
        # 개인화 점수 순으로 정렬
        scored_restaurants.sort(key=lambda x: x['base_score'], reverse=True)
        
        logger.info(f"개인화 기반 후보: {len(scored_restaurants)}개")
        return scored_restaurants
    
    def get_funnel_statistics(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """후보 생성 통계"""
        total = len(candidates)
        
        category_counts = {}
        price_range_counts = {}
        meal_card_count = 0
        
        for candidate in candidates:
            # 카테고리별 통계
            category = candidate.get('category', 'unknown')
            category_counts[category] = category_counts.get(category, 0) + 1
            
            # 가격대별 통계
            price_range = candidate.get('price_range', 'unknown')
            price_range_counts[price_range] = price_range_counts.get(price_range, 0) + 1
            
            # 급식카드 가맹점 수
            if candidate.get('meal_card_available', False):
                meal_card_count += 1
        
        return {
            'total_candidates': total,
            'category_distribution': category_counts,
            'price_range_distribution': price_range_counts,
            'meal_card_available': meal_card_count,
            'meal_card_ratio': meal_card_count / total if total > 0 else 0
        }


# 테스트 함수
def test_candidate_generation():
    """후보 생성 테스트"""
    print("=== Layer 1: 4-Funnel 후보 생성 테스트 ===")
    
    # 후보 생성기 초기화
    config = CandidateGenerationConfig()
    generator = FourFunnelCandidateGenerator(config)
    
    # 급식카드 사용자 프로필
    test_user_profile = {
        'user_id': 'meal_card_student',
        'age_range': '10s',
        'persona': 'middle_school_student',
        'preferred_categories': ['chicken', 'korean', 'pizza'],
        'daily_budget': 9000,
        'meal_card': True
    }
    
    # 테스트 상황
    test_context = {
        'user_location': '학교앞',
        'time_of_day': 'lunch',
        'day_of_week': 'weekday'
    }
    
    # 후보 생성
    candidates = generator.generate_candidates(test_user_profile, test_context)
    
    print(f"\n=== 생성된 후보 수: {len(candidates)}개 ===")
    
    # 통계 출력
    stats = generator.get_funnel_statistics(candidates)
    
    print(f"\n=== 4-Funnel 생성 통계 ===")
    print(f"총 후보 수: {stats['total_candidates']}개")
    print(f"급식카드 가맹점: {stats['meal_card_available']}개 ({stats['meal_card_ratio']:.1%})")
    
    print(f"\n카테고리별 분포:")
    for category, count in stats['category_distribution'].items():
        print(f"  {category}: {count}개")
    
    print(f"\n가격대별 분포:")
    for price_range, count in stats['price_range_distribution'].items():
        print(f"  {price_range}: {count}개")
    
    # 상위 10개 후보 출력
    print(f"\n=== 상위 10개 후보 ===")
    for i, candidate in enumerate(candidates[:10], 1):
        name = candidate['shop_name']
        category = candidate['category']
        score = candidate.get('base_score', 0)
        meal_card = "⭐" if candidate.get('meal_card_available', False) else ""
        
        print(f"{i}. {name} [{category}] - 점수: {score:.1f} {meal_card}")


if __name__ == "__main__":
    test_candidate_generation()