"""
Layer 2: 특성 엔지니어링
Layer 1 후보와 사용자 정보를 Wide & Deep 모델용 특성으로 변환
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, time
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FeatureConfig:
    """특성 엔지니어링 설정"""
    
    # Wide 파트 특성 수
    wide_feature_size: int = 50
    
    # Deep 파트 수치형 특성 수
    numerical_feature_size: int = 10
    
    # 정규화 파라미터
    max_budget: float = 100000.0
    max_distance: float = 20.0  # km
    max_score: float = 10.0
    
    # 시간 구간 설정
    time_slots: List[str] = None
    
    def __post_init__(self):
        if self.time_slots is None:
            self.time_slots = ['dawn', 'morning', 'lunch', 'afternoon', 'dinner', 'night']


class FeatureEngineer:
    """Layer 1 후보를 Layer 2 특성으로 변환"""
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()
        
        # 특성 인덱스 매핑
        self._init_feature_mappings()
        
        logger.info("FeatureEngineer 초기화 완료")
    
    def _init_feature_mappings(self):
        """Wide 파트 특성 인덱스 매핑 초기화"""
        self.wide_feature_map = {
            # Layer 1 점수들 (0~9)
            'collaborative_score': 0,
            'content_score': 1, 
            'context_score': 2,
            'base_score': 3,
            'max_layer1_score': 4,
            'avg_layer1_score': 5,
            'layer1_score_std': 6,
            'num_funnel_sources': 7,
            
            # 매장 특성 (10~19)
            'is_good_price': 10,
            'is_open_now': 11,
            'has_discount': 12,
            'is_new_shop': 13,
            'shop_rating': 14,
            'shop_review_count': 15,
            
            # 사용자-매장 매칭 (20~29)
            'category_preference_match': 20,
            'budget_compatibility': 21,
            'distance_penalty': 22,
            'time_preference_match': 23,
            'visited_before': 24,
            'similar_user_liked': 25,
            
            # 상황 특성 (30~39)
            'time_slot_match': 30,
            'weather_suitable': 31,
            'companion_suitable': 32,
            'location_convenience': 33,
            
            # 교차 특성 (40~49)
            'user_category_interaction': 40,
            'budget_time_interaction': 41,
            'location_category_interaction': 42,
            'preference_popularity_interaction': 43
        }
    
    def extract_wide_features(self, 
                             candidate: Dict[str, Any],
                             user_profile: Dict[str, Any], 
                             context: Dict[str, Any]) -> np.ndarray:
        """
        Wide 파트용 특성 추출
        
        Args:
            candidate: Layer 1 후보 정보
            user_profile: 사용자 프로필
            context: 상황 정보
            
        Returns:
            Wide 특성 벡터 [wide_feature_size]
        """
        features = np.zeros(self.config.wide_feature_size)
        
        # Layer 1 점수 특성들
        scores = self._extract_layer1_scores(candidate)
        features[0:4] = scores[:4]  # 각 Funnel 점수
        features[4] = np.max(scores)  # 최대 점수
        features[5] = np.mean(scores)  # 평균 점수
        features[6] = np.std(scores)  # 점수 표준편차
        funnel_sources = candidate.get('funnel_sources', candidate.get('funnel_source', ''))
        if isinstance(funnel_sources, list):
            features[7] = len(funnel_sources)
        elif isinstance(funnel_sources, str):
            features[7] = len(funnel_sources.split(' + '))
        else:
            features[7] = 1
        
        # 매장 특성들
        features[10] = 1.0 if candidate.get('is_good_price', False) else 0.0
        features[11] = self._is_shop_open_now(candidate, context)
        features[12] = 1.0 if candidate.get('has_discount', False) else 0.0
        features[13] = self._is_new_shop(candidate)
        features[14] = self._normalize_rating(candidate.get('rating', 0))
        features[15] = self._normalize_review_count(candidate.get('review_count', 0))
        
        # 사용자-매장 매칭 특성들
        features[20] = self._category_preference_match(candidate, user_profile)
        features[21] = self._budget_compatibility(candidate, user_profile)
        features[22] = self._distance_penalty(candidate, context)
        features[23] = self._time_preference_match(candidate, user_profile, context)
        features[24] = self._visited_before(candidate, user_profile)
        features[25] = self._similar_user_liked(candidate, user_profile)
        
        # 상황 특성들
        features[30] = self._time_slot_match(candidate, context)
        features[31] = self._weather_suitable(candidate, context)
        features[32] = self._companion_suitable(candidate, context)
        features[33] = self._location_convenience(candidate, context)
        
        # 교차 특성들 (중요한 특성 조합)
        features[40] = features[20] * features[14]  # 선호도 * 평점
        features[41] = features[21] * features[30]  # 예산 적합성 * 시간 적합성
        features[42] = features[33] * features[20]  # 위치 편의 * 카테고리 선호
        features[43] = features[20] * features[3]   # 선호도 * 인기도
        
        return features
    
    def extract_numerical_features(self,
                                  candidate: Dict[str, Any],
                                  user_profile: Dict[str, Any],
                                  context: Dict[str, Any]) -> np.ndarray:
        """
        Deep 파트용 수치형 특성 추출
        
        Returns:
            수치형 특성 벡터 [numerical_feature_size]
        """
        features = np.zeros(self.config.numerical_feature_size)
        
        # 사용자 특성 (정규화된)
        features[0] = user_profile.get('average_budget', 0) / self.config.max_budget
        features[1] = len(user_profile.get('favorite_shops', [])) / 10.0  # 최대 10개로 가정
        features[2] = len(user_profile.get('preferred_categories', [])) / 5.0  # 최대 5개로 가정
        
        # 매장 특성 (정규화된)
        features[3] = candidate.get('rating', 0) / 5.0  # 0~5점 -> 0~1
        features[4] = min(candidate.get('review_count', 0) / 1000.0, 1.0)  # 1000개 이상은 1.0
        features[5] = self._get_price_level_numeric(candidate.get('price_range', 'medium'))
        
        # 거리/위치 특성
        features[6] = self._calculate_distance(candidate, context) / self.config.max_distance
        
        # 시간 특성
        features[7] = self._get_time_numeric(context.get('current_time'))
        
        # Layer 1 점수 통계
        scores = self._extract_layer1_scores(candidate)  
        features[8] = np.mean(scores) / self.config.max_score
        features[9] = np.std(scores) / self.config.max_score
        
        return features
    
    def create_training_features(self,
                               candidates: List[Dict[str, Any]],
                               user_profile: Dict[str, Any],
                               context: Dict[str, Any],
                               labels: Optional[List[float]] = None) -> Dict[str, np.ndarray]:
        """
        배치 단위 특성 추출 (모델 훈련용)
        
        Args:
            candidates: 후보 리스트
            user_profile: 사용자 프로필
            context: 상황 정보
            labels: 레이블 (클릭=1, 미클릭=0)
            
        Returns:
            배치 특성 딕셔너리
        """
        batch_size = len(candidates)
        
        # Wide 특성
        wide_features = np.zeros((batch_size, self.config.wide_feature_size))
        
        # 수치형 특성
        numerical_features = np.zeros((batch_size, self.config.numerical_feature_size))
        
        # ID 특성들
        user_ids = []
        shop_ids = []
        category_ids = []
        
        for i, candidate in enumerate(candidates):
            wide_features[i] = self.extract_wide_features(candidate, user_profile, context)
            numerical_features[i] = self.extract_numerical_features(candidate, user_profile, context)
            
            user_ids.append(user_profile.get('user_id', 'unknown'))
            shop_ids.append(candidate['shop_id'])
            category_ids.append(candidate.get('category', 'unknown'))
        
        result = {
            'wide_features': wide_features,
            'numerical_features': numerical_features,
            'user_ids': user_ids,
            'shop_ids': shop_ids, 
            'category_ids': category_ids
        }
        
        if labels is not None:
            result['labels'] = np.array(labels)
        
        return result
    
    # === 보조 메서드들 ===
    
    def _extract_layer1_scores(self, candidate: Dict[str, Any]) -> np.ndarray:
        """Layer 1 점수들 추출"""
        return np.array([
            candidate.get('collaborative_score', 0),
            candidate.get('content_score', 0),
            candidate.get('context_score', 0), 
            candidate.get('base_score', 0)
        ])
    
    def _is_shop_open_now(self, candidate: Dict[str, Any], context: Dict[str, Any]) -> float:
        """현재 시간에 매장이 열려있는지"""
        # 실제로는 영업시간 데이터 필요
        current_hour = context.get('current_time', datetime.now()).hour
        if 9 <= current_hour <= 22:  # 기본 영업시간
            return 1.0
        return 0.0
    
    def _is_new_shop(self, candidate: Dict[str, Any]) -> float:
        """신규 매장인지 (임시 구현)"""
        return 1.0 if candidate.get('is_new', False) else 0.0
    
    def _normalize_rating(self, rating: float) -> float:
        """평점 정규화 (0~5 -> 0~1)"""
        return max(0, min(rating / 5.0, 1.0))
    
    def _normalize_review_count(self, count: int) -> float:
        """리뷰 수 정규화"""
        return min(count / 1000.0, 1.0)
    
    def _category_preference_match(self, candidate: Dict[str, Any], user_profile: Dict[str, Any]) -> float:
        """카테고리 선호도 매칭"""
        preferred_categories = user_profile.get('preferred_categories', [])
        candidate_category = candidate.get('category', '')
        
        if candidate_category in preferred_categories:
            # 순위에 따른 가중치 (첫 번째 선호가 높은 점수)
            try:
                rank = preferred_categories.index(candidate_category)
                return 1.0 - (rank * 0.1)  # 1.0, 0.9, 0.8, ...
            except ValueError:
                return 0.0
        return 0.0
    
    def _budget_compatibility(self, candidate: Dict[str, Any], user_profile: Dict[str, Any]) -> float:
        """예산 적합성"""
        user_budget = user_profile.get('average_budget', 0)
        if user_budget == 0:
            return 0.5  # 중립
            
        price_range = candidate.get('price_range', 'medium')
        price_map = {'low': 10000, 'medium': 20000, 'high': 40000}
        shop_price = price_map.get(price_range, 20000)
        
        # 예산 범위 내면 1.0, 초과할수록 감소
        if shop_price <= user_budget:
            return 1.0
        else:
            ratio = user_budget / shop_price
            return max(0.0, ratio)
    
    def _distance_penalty(self, candidate: Dict[str, Any], context: Dict[str, Any]) -> float:
        """거리 페널티 (가까울수록 높은 점수)"""
        distance = self._calculate_distance(candidate, context)
        if distance == 0:
            return 1.0
        return max(0.0, 1.0 - distance / self.config.max_distance)
    
    def _time_preference_match(self, candidate: Dict[str, Any], user_profile: Dict[str, Any], context: Dict[str, Any]) -> float:
        """시간대 선호도 매칭"""
        # 실제로는 사용자의 시간대별 선호도 이력 필요
        current_time = context.get('current_time', datetime.now())
        hour = current_time.hour
        
        # 기본적인 시간대 선호도 (점심/저녁 시간에 높은 점수)
        if 11 <= hour <= 14 or 17 <= hour <= 21:
            return 1.0
        elif 9 <= hour <= 11 or 14 <= hour <= 17:
            return 0.7
        else:
            return 0.3
    
    def _visited_before(self, candidate: Dict[str, Any], user_profile: Dict[str, Any]) -> float:
        """이전 방문 이력"""
        favorite_shops = user_profile.get('favorite_shops', [])
        return 1.0 if candidate['shop_id'] in favorite_shops else 0.0
    
    def _similar_user_liked(self, candidate: Dict[str, Any], user_profile: Dict[str, Any]) -> float:
        """유사 사용자 선호도 (임시 구현)"""
        # 실제로는 협업 필터링 결과 활용
        return candidate.get('collaborative_score', 0) / self.config.max_score
    
    def _time_slot_match(self, candidate: Dict[str, Any], context: Dict[str, Any]) -> float:
        """시간대 적합성"""
        time_of_day = context.get('time_of_day', 'lunch')
        candidate_suitable_times = candidate.get('suitable_times', ['lunch', 'dinner'])
        
        return 1.0 if time_of_day in candidate_suitable_times else 0.0
    
    def _weather_suitable(self, candidate: Dict[str, Any], context: Dict[str, Any]) -> float:
        """날씨 적합성 (임시 구현)"""
        weather = context.get('weather', 'clear')
        # 비오는 날은 실내 매장 선호
        if weather == 'rain':
            return 1.0 if candidate.get('indoor', True) else 0.5
        return 1.0
    
    def _companion_suitable(self, candidate: Dict[str, Any], context: Dict[str, Any]) -> float:
        """동반자 적합성"""
        companion = context.get('companion', 'alone')
        # 가족/친구와 함께면 큰 매장 선호
        if companion in ['family', 'friends']:
            return 1.0 if candidate.get('group_friendly', True) else 0.7
        return 1.0
    
    def _location_convenience(self, candidate: Dict[str, Any], context: Dict[str, Any]) -> float:
        """위치 편의성"""
        user_location = context.get('user_location', '')
        candidate_district = candidate.get('district', '')
        
        if user_location == candidate_district:
            return 1.0
        elif user_location and candidate_district:
            return 0.5  # 다른 구역이지만 정보 있음
        return 0.7  # 정보 없음
    
    def _calculate_distance(self, candidate: Dict[str, Any], context: Dict[str, Any]) -> float:
        """거리 계산 (임시 구현)"""
        # 실제로는 GPS 좌표 기반 계산 필요
        user_location = context.get('user_location', '')
        candidate_district = candidate.get('district', '')
        
        if user_location == candidate_district:
            return 1.0  # 같은 구역 내 평균 거리
        return 5.0  # 다른 구역 평균 거리
    
    def _get_price_level_numeric(self, price_range: str) -> float:
        """가격대를 수치로 변환"""
        price_map = {'low': 0.2, 'medium': 0.5, 'high': 0.8}
        return price_map.get(price_range, 0.5)
    
    def _get_time_numeric(self, current_time: Optional[datetime]) -> float:
        """시간을 수치로 변환 (0~1)"""
        if current_time is None:
            return 0.5
        return current_time.hour / 24.0


# 테스트 함수
def test_feature_engineering():
    """특성 엔지니어링 테스트"""
    print("=== Layer 2: 특성 엔지니어링 테스트 ===")
    
    feature_engineer = FeatureEngineer()
    
    # 테스트 데이터
    test_candidate = {
        'shop_id': 'shop_1',
        'shop_name': '건강한집',
        'category': '한식',
        'collaborative_score': 8.5,
        'content_score': 7.2,
        'context_score': 6.8, 
        'base_score': 7.5,
        'is_good_price': True,
        'rating': 4.2,
        'review_count': 156,
        'price_range': 'medium',
        'district': '관악구'
    }
    
    test_user_profile = {
        'user_id': 'test_user',
        'preferred_categories': ['한식', '치킨'],
        'average_budget': 15000,
        'favorite_shops': ['shop_1']
    }
    
    test_context = {
        'user_location': '관악구',
        'time_of_day': 'lunch',
        'current_time': datetime.now(),
        'weather': 'clear'
    }
    
    # Wide 특성 추출
    wide_features = feature_engineer.extract_wide_features(
        test_candidate, test_user_profile, test_context
    )
    
    print(f"\n=== Wide 특성 (크기: {len(wide_features)}) ===")
    print(f"Layer 1 점수들: {wide_features[0:8]}")
    print(f"매장 특성들: {wide_features[10:16]}")
    print(f"매칭 특성들: {wide_features[20:26]}")
    print(f"상황 특성들: {wide_features[30:34]}")
    print(f"교차 특성들: {wide_features[40:44]}")
    
    # 수치형 특성 추출
    numerical_features = feature_engineer.extract_numerical_features(
        test_candidate, test_user_profile, test_context
    )
    
    print(f"\n=== 수치형 특성 (크기: {len(numerical_features)}) ===")
    feature_names = [
        '사용자_예산', '즐겨찾기_수', '선호카테고리_수',
        '매장_평점', '리뷰_수', '가격대',
        '거리', '시간', 'Layer1_평균점수', 'Layer1_점수편차'
    ]
    
    for name, value in zip(feature_names, numerical_features):
        print(f"{name}: {value:.3f}")
    
    # 배치 특성 추출 테스트
    candidates = [test_candidate] * 3  # 동일 후보 3개
    batch_features = feature_engineer.create_training_features(
        candidates, test_user_profile, test_context
    )
    
    print(f"\n=== 배치 특성 ===")
    print(f"Wide 특성 shape: {batch_features['wide_features'].shape}")
    print(f"수치형 특성 shape: {batch_features['numerical_features'].shape}")
    print(f"사용자 ID 수: {len(batch_features['user_ids'])}")


if __name__ == "__main__":
    test_feature_engineering()