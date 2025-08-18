"""
Layer 1+2 통합 추천 엔진 (conversation_summary_0730_v0.md 정확한 분석 반영)
- 실제 DB 31개 시트 기반 Feature 구조
- 데이터 편향 문제 해결 (착한가게 10%, 급식카드 90%, 인기메뉴 100%)
- 벡터 검색 우선 전략 ("필터링 → 점수"에서 "벡터 검색 → 개인화"로 전환)
- 챗봇 Output vs DB Features 명확한 분리
- Wide & Deep 아키텍처 (실제 Feature 기반)
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import numpy as np
import hashlib

try:
    from .candidate_generator import CandidateGenerator, CandidateGenerationConfig
    from .ranking_model import PersonalizedRanker, RankingModelConfig
    from .feature_engineering import FeatureEngineer, FeatureConfig
    from .model_trainer import ModelTrainer
except ImportError:
    from candidate_generator import CandidateGenerator, CandidateGenerationConfig
    from ranking_model import PersonalizedRanker, RankingModelConfig
    from feature_engineering import FeatureEngineer, FeatureConfig
    from model_trainer import ModelTrainer

# 급식카드 매니저 임포트
try:
    from ..inference.foodcard_manager import FoodcardManager
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from inference.foodcard_manager import FoodcardManager

logger = logging.getLogger(__name__)


class RealDataFeatureExtractor:
    """
    실제 DB 31개 시트 기반 특성 추출기
    conversation_summary Section 35 오류 정정 반영
    """
    
    def __init__(self):
        # 데이터 편향 보정 파라미터 (Section 28)
        self.bias_corrections = {
            'good_shop_weight': 0.3,        # 착한가게 10% → 가중치 축소
            'meal_card_ignore': True,       # 급식카드 90% → 변별력 없음, 무시
            'popular_menu_ignore': True,    # 인기메뉴 100% → 완전 무의미, 무시
            'rating_threshold': 3.5         # 평점 편향 고려한 임계값
        }
        
        logger.info("실제 DB 구조 기반 특성 추출기 초기화 (편향 보정 적용)")
    
    def extract_wide_features(self,
                             candidate: Dict[str, Any],
                             user_profile: Dict[str, Any],
                             chatbot_output: Dict[str, Any],
                             context: Dict[str, Any]) -> np.ndarray:
        """
        Wide Component 특성 추출 (Cross-Product Features)
        실제 DB 시트 기반: user, user_location, shop, brand, shop_menu
        """
        wide_features = []
        
        # 1. 사용자-매장 교차 특성 (실제 DB 컬럼 기반)
        
        # user.birthday(연령대) × shop.category
        user_age_group = self._calculate_age_group_from_birthday(user_profile.get('birthday', ''))
        shop_category = candidate.get('category', 'unknown')
        age_category_cross = self._hash_cross_feature(user_age_group, shop_category)
        wide_features.append(age_category_cross)
        
        # user_location.city × shop.address(지역구)
        user_city = user_profile.get('location', {}).get('city', 'unknown')
        shop_district = self._extract_district_from_address(candidate.get('address', ''))
        location_cross = self._hash_cross_feature(user_city, shop_district)
        wide_features.append(location_cross)
        
        # 시간대 × shop.category (챗봇 output + DB)
        time_of_day = context.get('time_of_day', 'unknown')
        time_category_cross = self._hash_cross_feature(time_of_day, shop_category)
        wide_features.append(time_category_cross)
        
        # user.id × shop.id (특정 사용자-매장 상호작용 암기)
        user_shop_cross = self._hash_cross_feature(
            str(user_profile.get('id', 0)), 
            str(candidate.get('id', 'unknown'))
        )
        wide_features.append(user_shop_cross)
        
        # 2. 챗봇 Output 기반 직접 특성
        
        # 예산 적합성 (챗봇 budget_filter vs shop_menu.price 평균)
        budget_compatibility = self._calculate_budget_compatibility(
            candidate.get('avg_menu_price', 0),
            chatbot_output.get('budget_filter', 0)
        )
        wide_features.append(budget_compatibility)
        
        # 위치 거리 (챗봇 location_filter vs shop.address)
        location_distance = self._calculate_location_distance(
            shop_district,
            chatbot_output.get('location_filter', {}).get('district', '')
        )
        wide_features.append(location_distance)
        
        # 식단 선호 매칭 (챗봇 dietary_preferences vs shop features)
        dietary_match = self._calculate_dietary_preference_match(
            candidate,
            chatbot_output.get('filters', {}).get('dietary_preferences', [])
        )
        wide_features.append(dietary_match)
        
        # 3. 데이터 편향 보정 적용 (Section 28 문제 해결)
        
        # 착한가게 특성 (10% 편향 → 가중치 축소)
        good_shop_feature = 0.0
        if candidate.get('isGoodShop', False):
            good_shop_feature = self.bias_corrections['good_shop_weight']
        wide_features.append(good_shop_feature)
        
        # 급식카드는 90% 편향으로 변별력 없음 → 무시 (feature 추가 안함)
        # 인기메뉴는 100% 편향으로 완전 무의미 → 무시 (feature 추가 안함)
        
        # 평점 특성 (편향 고려한 임계값 적용)
        rating_feature = 0.0
        rating = candidate.get('rating', 0)
        if rating > self.bias_corrections['rating_threshold']:
            rating_feature = (rating - self.bias_corrections['rating_threshold']) / (5.0 - self.bias_corrections['rating_threshold'])
        wide_features.append(rating_feature)
        
        # 4. Layer 1 Funnel 정보 활용
        
        # 어떤 Funnel에서 나왔는지 (funnel_source)
        funnel_sources = candidate.get('funnel_sources', [candidate.get('funnel_source', 'unknown')])
        if isinstance(funnel_sources, str):
            funnel_sources = funnel_sources.split(' + ')
        
        # 각 Funnel별 활성화 여부
        wide_features.append(1.0 if 'collaborative' in ' '.join(funnel_sources) else 0.0)
        wide_features.append(1.0 if 'content' in ' '.join(funnel_sources) else 0.0)
        wide_features.append(1.0 if 'contextual' in ' '.join(funnel_sources) else 0.0)
        wide_features.append(1.0 if 'popularity' in ' '.join(funnel_sources) else 0.0)
        
        # Layer 1 점수들 (각 Funnel의 신뢰도)
        wide_features.append(candidate.get('collaborative_score', 0) / 10.0)  # 정규화
        wide_features.append(candidate.get('content_score', 0) / 10.0)
        wide_features.append(candidate.get('context_score', 0) / 10.0)
        wide_features.append(candidate.get('base_score', 0) / 10.0)
        
        # 필요한 길이로 패딩 (Wide component 목표: 50차원)
        target_length = 50
        while len(wide_features) < target_length:
            wide_features.append(0.0)
        
        return np.array(wide_features[:target_length])
    
    def extract_deep_features(self,
                             candidate: Dict[str, Any],
                             user_profile: Dict[str, Any],
                             chatbot_output: Dict[str, Any],
                             context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep Component 특성 추출 (Embedding + Numerical Features)
        실제 DB 시트 기반
        """
        
        # 1. ID 기반 임베딩 특성들 (실제 DB 컬럼)
        features = {
            'user_id': user_profile.get('id', 0),                    # user.id
            'shop_id': candidate.get('id', 'unknown'),               # shop.id  
            'brand_id': candidate.get('brand_id', 'unknown'),        # brand.id
            'category': candidate.get('category', 'unknown'),        # shop.category
            'user_location_state': user_profile.get('location', {}).get('state', 'unknown'),  # user_location.state
            'user_location_city': user_profile.get('location', {}).get('city', 'unknown')     # user_location.city
        }
        
        # 2. 챗봇 semantic query (벡터 검색 우선 전략)
        features['semantic_query'] = chatbot_output.get('semantic_query', '')
        
        # 3. 수치형 특성들 (실제 DB 컬럼 기반)
        numerical_features = []
        
        # 사용자 수치형 특성
        user_age = self._calculate_age_from_birthday(user_profile.get('birthday', ''))
        numerical_features.append(user_age / 100.0)  # 정규화
        
        # 사용자 활동 기록 (집계 필요 - product_order, userfavorite, review 시트)
        numerical_features.append(user_profile.get('shop_favorite_count', 0) / 50.0)      # userfavorite 집계
        numerical_features.append(user_profile.get('total_orders', 0) / 100.0)           # product_order 집계
        numerical_features.append(user_profile.get('review_count', 0) / 50.0)            # review 집계
        
        # 매장 수치형 특성 (실제 DB 컬럼)
        numerical_features.append(candidate.get('avg_menu_price', 0) / 50000.0)          # shop_menu.price 평균
        numerical_features.append(candidate.get('menu_count', 0) / 30.0)                 # shop_menu 개수
        numerical_features.append(candidate.get('rating', 0) / 5.0)                      # review.rating 평균
        numerical_features.append(candidate.get('review_count', 0) / 1000.0)             # review 개수
        numerical_features.append(candidate.get('order_count', 0) / 1000.0)              # product_order 개수
        
        # 영업시간 정보 (shop.operating_hours에서 계산)
        operating_hours = self._calculate_operating_hours(candidate.get('operating_hours', ''))
        numerical_features.append(operating_hours / 24.0)  # 정규화
        
        # 10차원으로 맞춤
        while len(numerical_features) < 10:
            numerical_features.append(0.0)
        
        features['numerical_features'] = np.array(numerical_features[:10])
        
        return features
    
    def create_training_sample(self,
                              interaction_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        훈련용 샘플 생성 (product_order, userfavorite, review 시트 기반)
        """
        
        user_profile = interaction_record['user_profile']
        candidate = interaction_record['candidate'] 
        chatbot_output = interaction_record['chatbot_output']
        context = interaction_record['context']
        
        # 특성 추출
        wide_features = self.extract_wide_features(candidate, user_profile, chatbot_output, context)
        deep_features = self.extract_deep_features(candidate, user_profile, chatbot_output, context)
        
        # 레이블 생성 (실제 상호작용 기록 기반)
        label = 0.0
        if interaction_record.get('ordered', False):        # product_order 기록
            label = 1.0
        elif interaction_record.get('favorited', False):    # userfavorite 기록  
            label = 1.0
        elif interaction_record.get('rating', 0) >= 4.0:    # review.rating 높음
            label = 1.0
        
        return {
            'wide_features': wide_features,
            'deep_features': deep_features,
            'label': label,
            'metadata': {
                'user_id': user_profile.get('id'),
                'shop_id': candidate.get('id'),
                'interaction_type': interaction_record.get('interaction_type', 'unknown')
            }
        }
    
    # === 보조 메서드들 ===
    
    def _calculate_age_group_from_birthday(self, birthday: str) -> str:
        """생년월일에서 연령대 계산 (user.birthday → 연령대)"""
        if not birthday:
            return '30s'
        
        try:
            if len(birthday) >= 4:
                birth_year = int(birthday[:4])
                age = datetime.now().year - birth_year
                
                if age < 20: return 'teens'
                elif age < 30: return '20s'
                elif age < 40: return '30s'
                elif age < 50: return '40s'
                else: return '50s+'
        except:
            pass
        
        return '30s'  # 기본값
    
    def _calculate_age_from_birthday(self, birthday: str) -> float:
        """생년월일에서 수치 나이 계산"""
        if not birthday:
            return 30.0
        
        try:
            if len(birthday) >= 4:
                birth_year = int(birthday[:4])
                return float(datetime.now().year - birth_year)
        except:
            pass
        
        return 30.0
    
    def _extract_district_from_address(self, address: str) -> str:
        """주소에서 구/시 정보 추출 (shop.address → 지역구)"""
        if not address:
            return 'unknown'
        
        # 간단한 정규식으로 구/시 추출
        districts = ['강남구', '서초구', '관악구', '동작구', '영등포구', '마포구', '용산구', '중구', '종로구', '성동구']
        for district in districts:
            if district in address:
                return district
        
        return 'unknown'
    
    def _hash_cross_feature(self, feature1: str, feature2: str) -> float:
        """교차 특성 해싱 (Wide Component용)"""
        combined = f"{feature1}_{feature2}"
        # MD5 해싱 후 0~1 범위로 정규화
        hash_value = int(hashlib.md5(combined.encode()).hexdigest()[:8], 16)
        return (hash_value % 10000) / 10000.0
    
    def _calculate_budget_compatibility(self, avg_menu_price: float, budget_filter: float) -> float:
        """예산 적합성 계산"""
        if budget_filter <= 0 or avg_menu_price <= 0:
            return 0.5  # 중립
        
        if avg_menu_price <= budget_filter:
            return 1.0
        else:
            return max(0.0, budget_filter / avg_menu_price)
    
    def _calculate_location_distance(self, shop_district: str, user_district: str) -> float:
        """위치 거리 계산"""
        if not shop_district or not user_district:
            return 0.5  # 중립
        
        if shop_district == user_district:
            return 1.0  # 같은 구역
        else:
            return 0.3  # 다른 구역
    
    def _calculate_dietary_preference_match(self, candidate: Dict[str, Any], dietary_preferences: List[str]) -> float:
        """식단 선호도 매칭"""
        if not dietary_preferences:
            return 0.5  # 중립
        
        # 매장의 특성과 식단 선호도 매칭
        shop_features = [
            candidate.get('category', ''),
            candidate.get('description', ''),
            ' '.join(candidate.get('menu_names', []))
        ]
        shop_text = ' '.join(shop_features).lower()
        
        matches = 0
        for preference in dietary_preferences:
            if preference.lower() in shop_text:
                matches += 1
        
        return min(matches / len(dietary_preferences), 1.0)
    
    def _calculate_operating_hours(self, operating_hours: str) -> float:
        """영업시간 계산 (문자열 → 시간)"""
        if not operating_hours:
            return 12.0  # 기본값
        
        try:
            # 간단한 파싱 (실제로는 더 정교한 파싱 필요)
            # 예: "09:00-22:00" → 13시간
            if '-' in operating_hours:
                parts = operating_hours.split('-')
                if len(parts) == 2:
                    start_hour = int(parts[0].split(':')[0])
                    end_hour = int(parts[1].split(':')[0])
                    return float(end_hour - start_hour)
        except:
            pass
        
        return 12.0  # 기본값


class RecommendationEngine:
    """
    Layer 1+2 통합 추천 엔진 (conversation_summary 정확한 분석 반영)
    벡터 검색 우선 전략 + Wide & Deep 개인화
    """
    
    def __init__(self,
                 candidate_config: Optional[CandidateGenerationConfig] = None,
                 ranking_config: Optional[RankingModelConfig] = None,
                 model_path: Optional[str] = None,
                 foodcard_manager: Optional[FoodcardManager] = None):
        
        # Layer 1: 4-Funnel 후보 생성기 (기존 완성된 시스템)
        self.candidate_generator = CandidateGenerator(candidate_config)
        
        # Layer 2: Wide & Deep 개인화 랭커
        self.feature_extractor = RealDataFeatureExtractor()
        self.ranker = PersonalizedRanker(ranking_config)
        
        # 급식카드 관리자
        self.foodcard_manager = foodcard_manager or FoodcardManager()
        
        # 벡터 검색 우선 전략 활성화
        self.vector_search_weight = 0.6  # conversation_summary 권장 가중치
        self.rule_based_weight = 0.4
        
        # 딥러닝 모델 로드 (선택적)
        self.deep_learning_available = False
        if model_path and Path(model_path).exists():
            self._try_load_deep_model(model_path)
        
        # 성능 통계
        self.stats = {
            'total_requests': 0,
            'vector_search_usage': 0,
            'deep_learning_usage': 0,
            'data_bias_corrections': 0,
            'foodcard_payments': 0,
            'emergency_coupons_issued': 0,
            'avg_layer1_candidates': 0.0,
            'avg_response_time': 0.0
        }
        
        logger.info("Layer 1+2 통합 추천 엔진 초기화 완료")
        logger.info(f"벡터 검색 우선 전략: 가중치 {self.vector_search_weight}")
        logger.info(f"딥러닝 모델: {'활성화' if self.deep_learning_available else '비활성화'}")
        logger.info(f"급식카드 관리: {'활성화' if self.foodcard_manager else '비활성화'}")
    
    def get_recommendations(self,
                          user_id: str,
                          user_profile: Dict[str, Any],
                          chatbot_output: Dict[str, Any],
                          context: Dict[str, Any],
                          top_k: int = 10) -> Dict[str, Any]:
        """
        완전한 2-Layer 추천 (실제 데이터 구조 기반)
        
        Args:
            user_id: 사용자 ID (user.id)
            user_profile: 실제 DB 시트 구조 (user, user_location, 집계 정보)
            chatbot_output: 챗봇 분석 결과 (semantic_query, filters 등)
            context: 상황 정보 (시간, 위치 등)
            top_k: 반환할 추천 수
            
        Returns:
            추천 결과 딕셔너리
        """
        start_time = datetime.now()
        
        # Layer 1: 4-Funnel 후보 생성 (벡터 검색 우선 전략)
        candidates = self._generate_candidates_with_vector_priority(
            user_id, user_profile, chatbot_output, context
        )
        
        if not candidates:
            logger.warning(f"Layer 1에서 후보를 찾지 못했습니다: {user_id}")
            return self._empty_recommendation_result(user_id, chatbot_output)
        
        logger.info(f"Layer 1 완료: {len(candidates)}개 후보 생성")
        
        # Layer 2: Wide & Deep 개인화 랭킹
        if self.deep_learning_available:
            # 딥러닝 모델 기반 랭킹
            ranked_candidates = self._deep_learning_ranking(
                candidates, user_profile, chatbot_output, context
            )
            ranking_method = 'wide_deep_model'
            self.stats['deep_learning_usage'] += 1
        else:
            # 실제 데이터 기반 규칙 랭킹 (Wide Component 규칙 구현)
            ranked_candidates = self._wide_component_ranking(
                candidates, user_profile, chatbot_output, context
            )
            ranking_method = 'wide_component_rules'
        
        # 상위 K개 선택
        top_recommendations = ranked_candidates[:top_k]
        
        # 추천 설명 생성
        explanations = self._generate_explanations(
            top_recommendations, user_profile, chatbot_output, ranking_method
        )
        
        # 결과 구성
        total_time = (datetime.now() - start_time).total_seconds()
        
        result = {
            'user_id': user_id,
            'original_query': chatbot_output.get('original_query', ''),
            'semantic_query': chatbot_output.get('semantic_query', ''),
            'recommendations': top_recommendations,
            'explanations': explanations,
            'metadata': {
                'total_candidates': len(candidates),
                'final_recommendations': len(top_recommendations),
                'ranking_method': ranking_method,
                'vector_search_priority': True,
                'data_bias_corrections_applied': self.feature_extractor.bias_corrections,
                'deep_learning_available': self.deep_learning_available,
                'layer1_funnel_breakdown': self._analyze_funnel_breakdown(candidates),
                'total_time': total_time,
                'filters_applied': chatbot_output.get('filters', {}),
                'context': context
            }
        }
        
        # 통계 업데이트
        self._update_stats(len(candidates), total_time)
        
        logger.info(f"Layer 2 완료: {len(top_recommendations)}개 추천 반환 ({ranking_method}, {total_time:.3f}초)")
        return result
    
    def _generate_candidates_with_vector_priority(self,
                                                user_id: str,
                                                user_profile: Dict[str, Any],
                                                chatbot_output: Dict[str, Any],
                                                context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        벡터 검색 우선 전략으로 후보 생성
        conversation_summary: "필터링 → 점수"에서 "벡터 검색 → 개인화"로 전환
        """
        
        # semantic_query를 핵심으로 하는 Content-Based Funnel 우선
        query = chatbot_output.get('semantic_query', '')
        filters = chatbot_output.get('filters', {})
        
        candidates = self.candidate_generator.generate_candidates(
            user_id=user_id,
            user_location=context.get('user_location'),
            query=query,  # 벡터 검색의 핵심
            time_of_day=context.get('time_of_day'),
            user_type=self._infer_user_type_from_real_data(user_profile),
            filters=filters,
            current_time=context.get('current_time', datetime.now())
        )
        
        # 벡터 검색 우선 가중치 적용
        for candidate in candidates:
            # Content Funnel (벡터 검색) 점수 가중치 증가
            if 'content' in candidate.get('funnel_source', ''):
                original_score = candidate.get('content_score', 0)
                candidate['content_score'] = original_score * (1 + self.vector_search_weight)
                candidate['vector_search_boosted'] = True
            
            # 기타 Funnel 점수는 상대적으로 가중치 감소
            for score_key in ['collaborative_score', 'context_score', 'base_score']:
                if score_key in candidate:
                    candidate[score_key] = candidate[score_key] * self.rule_based_weight
        
        self.stats['vector_search_usage'] += 1
        return candidates
    
    def _wide_component_ranking(self,
                               candidates: List[Dict[str, Any]],
                               user_profile: Dict[str, Any],
                               chatbot_output: Dict[str, Any],
                               context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Wide Component 규칙 기반 랭킹 (딥러닝 모델 없을 때)
        실제 DB 특성 기반 Cross-Product Features 활용
        """
        
        for candidate in candidates:
            # 실제 데이터 기반 특성 추출
            wide_features = self.feature_extractor.extract_wide_features(
                candidate, user_profile, chatbot_output, context
            )
            deep_features = self.feature_extractor.extract_deep_features(
                candidate, user_profile, chatbot_output, context
            )
            
            # Layer 1 기본 점수 (벡터 검색 우선 반영)
            layer1_score = max([
                candidate.get('collaborative_score', 0),
                candidate.get('content_score', 0),      # 벡터 검색 부스트 반영
                candidate.get('context_score', 0),
                candidate.get('base_score', 0)
            ])
            
            # Wide Component Cross-Product 점수 계산
            cross_product_score = 0.0
            bonus_reasons = []
            
            # 연령대-카테고리 교차 특성 (wide_features[0])
            age_category_match = wide_features[0]
            if age_category_match > 0.7:
                cross_product_score += 3.0
                bonus_reasons.append("연령-카테고리 매칭")
            
            # 위치-지역 교차 특성 (wide_features[1])
            location_match = wide_features[1]
            if location_match > 0.7:
                cross_product_score += 2.0
                bonus_reasons.append("위치 매칭")
            
            # 시간-카테고리 교차 특성 (wide_features[2])
            time_category_match = wide_features[2]
            if time_category_match > 0.7:
                cross_product_score += 2.0
                bonus_reasons.append("시간-카테고리 매칭")
            
            # 사용자-매장 특별 교차 특성 (wide_features[3])
            user_shop_special = wide_features[3]
            if user_shop_special > 0.8:
                cross_product_score += 5.0
                bonus_reasons.append("개인화 특별 매칭")
            
            # 챗봇 Output 기반 직접 특성들
            budget_compat = wide_features[4]  # 예산 적합성
            location_dist = wide_features[5]  # 위치 거리
            dietary_match = wide_features[6]  # 식단 선호
            
            if budget_compat > 0.8:
                cross_product_score += 2.0
                bonus_reasons.append("예산 적합")
            
            if location_dist > 0.8:
                cross_product_score += 1.5
                bonus_reasons.append("위치 편의")
            
            if dietary_match > 0.6:
                cross_product_score += 2.5
                bonus_reasons.append("식단 선호")
            
            # 데이터 편향 보정된 특성들
            good_shop_corrected = wide_features[7]  # 착한가게 (보정됨)
            rating_corrected = wide_features[9]     # 평점 (임계값 적용)
            
            if good_shop_corrected > 0:
                cross_product_score += good_shop_corrected * 10  # 원래 3점이었으나 보정으로 0.9점
                bonus_reasons.append("착한가게(편향보정)")
                self.stats['data_bias_corrections'] += 1
            
            if rating_corrected > 0.5:
                cross_product_score += rating_corrected * 2.0
                bonus_reasons.append("고평점(임계값적용)")
            
            # Layer 1 Funnel 정보 활용 (Funnel별 신뢰도)
            funnel_boost = 0.0
            if wide_features[10] > 0:  # collaborative
                funnel_boost += wide_features[14] * 2.0  # collaborative_score
            if wide_features[11] > 0:  # content (벡터 검색)
                funnel_boost += wide_features[15] * 3.0  # content_score (가중치 증가)
            if wide_features[12] > 0:  # contextual
                funnel_boost += wide_features[16] * 2.0  # context_score
            if wide_features[13] > 0:  # popularity
                funnel_boost += wide_features[17] * 1.5  # base_score
            
            if funnel_boost > 1.0:
                cross_product_score += funnel_boost
                bonus_reasons.append("다중Funnel")
            
            # Deep Component 수치형 특성 간단 활용
            numerical_features = deep_features['numerical_features']
            
            # 사용자 활동성 점수 (numerical_features[1:4])
            user_activity = np.mean(numerical_features[1:4])  # 즐겨찾기, 주문, 리뷰
            if user_activity > 0.3:
                cross_product_score += user_activity * 2.0
                bonus_reasons.append("활발한사용자")
            
            # 매장 인기도 점수 (numerical_features[5:8])
            shop_popularity = np.mean(numerical_features[5:8])  # 메뉴수, 평점, 리뷰수
            if shop_popularity > 0.5:
                cross_product_score += shop_popularity * 1.5
                bonus_reasons.append("인기매장")
            
            # 급식카드 사용 가능 여부 체크
            foodcard_usable = False
            if user_profile.get('user_id') and self.foodcard_manager:
                balance = self.foodcard_manager.check_balance(user_profile.get('user_id'))
                if balance is not None:
                    avg_price = candidate.get('avg_menu_price', 0)
                    if balance >= avg_price and candidate.get('is_food_card_shop', 'N') == 'Y':
                        foodcard_usable = True
                        cross_product_score += 3.0
                        bonus_reasons.append("급식카드사용가능")
            
            # 최종 점수 계산
            final_score = layer1_score + cross_product_score
            
            # 결과 저장
            candidate['personalized_score'] = final_score
            candidate['layer1_base_score'] = layer1_score
            candidate['wide_component_score'] = cross_product_score
            candidate['bonus_reasons'] = bonus_reasons
            candidate['ranking_method'] = 'wide_component_cross_product'
            candidate['vector_search_boosted'] = candidate.get('vector_search_boosted', False)
            candidate['data_bias_corrected'] = '편향보정' in ' '.join(bonus_reasons)
            candidate['foodcard_usable'] = foodcard_usable
        
        # 점수 기준 정렬
        ranked_candidates = sorted(candidates,
                                 key=lambda x: x['personalized_score'],
                                 reverse=True)
        
        logger.info(f"Wide Component 랭킹 완료: {len(ranked_candidates)}개 후보")
        return ranked_candidates
    
    def _generate_explanations(self,
                              recommendations: List[Dict[str, Any]],
                              user_profile: Dict[str, Any],
                              chatbot_output: Dict[str, Any],
                              ranking_method: str) -> List[str]:
        """추천 설명 생성 (실제 데이터 기반)"""
        explanations = []
        
        for i, rec in enumerate(recommendations[:3], 1):
            shop_name = rec['shop_name']
            score = rec.get('personalized_score', 0)
            reasons = rec.get('bonus_reasons', [])
            vector_boosted = rec.get('vector_search_boosted', False)
            bias_corrected = rec.get('data_bias_corrected', False)
            
            explanation = f"{i}. {shop_name} (점수: {score:.1f})"
            
            # 주요 이유 2-3개만 표시
            if reasons:
                explanation += f" - {', '.join(reasons[:3])}"
            
            # 특별 표시
            tags = []
            if vector_boosted:
                tags.append("벡터검색")
            if bias_corrected:
                tags.append("편향보정")
            if ranking_method == 'wide_deep_model':
                tags.append("딥러닝")
            
            if tags:
                explanation += f" [{'/'.join(tags)}]"
            
            explanations.append(explanation)
        
        return explanations
    
    def _analyze_funnel_breakdown(self, candidates: List[Dict[str, Any]]) -> Dict[str, int]:
        """Layer 1 Funnel별 후보 분석"""
        breakdown = {
            'collaborative': 0,
            'content': 0,
            'contextual': 0,
            'popularity': 0,
            'multi_funnel': 0
        }
        
        for candidate in candidates:
            funnel_sources = candidate.get('funnel_sources', [candidate.get('funnel_source', '')])
            if isinstance(funnel_sources, str):
                funnel_sources = funnel_sources.split(' + ')
            
            if len(funnel_sources) > 1:
                breakdown['multi_funnel'] += 1
            
            for source in funnel_sources:
                if 'collaborative' in source:
                    breakdown['collaborative'] += 1
                elif 'content' in source:
                    breakdown['content'] += 1
                elif 'contextual' in source:
                    breakdown['contextual'] += 1
                elif 'popularity' in source:
                    breakdown['popularity'] += 1
        
        return breakdown
    
    def _infer_user_type_from_real_data(self, user_profile: Dict[str, Any]) -> str:
        """실제 DB 데이터 기반 사용자 타입 추론"""
        
        # 실제 DB 컬럼 활용
        age = self.feature_extractor._calculate_age_from_birthday(user_profile.get('birthday', ''))
        order_count = user_profile.get('total_orders', 0)
        favorite_count = user_profile.get('shop_favorite_count', 0)
        
        # 활동 패턴 기반 분류
        if order_count > 20:
            return 'frequent_eater'
        elif favorite_count > 10:
            return 'selective_eater'
        elif age < 25:
            return 'young_eater'
        elif age > 45:
            return 'mature_eater'
        else:
            return 'general_eater'
    
    def _try_load_deep_model(self, model_path: str):
        """딥러닝 모델 로드 시도"""
        try:
            trainer = ModelTrainer()
            if trainer.load_model(model_path):
                self.ranker.model = trainer.model
                self.ranker.id_mappings = trainer.id_mappings
                self.ranker.feature_engineer = trainer.feature_engineer
                self.deep_learning_available = True
                logger.info(f"Wide & Deep 모델 로드 성공: {model_path}")
            else:
                logger.warning(f"모델 로드 실패, Wide Component 규칙 사용: {model_path}")
        except Exception as e:
            logger.warning(f"모델 로드 중 오류, Wide Component 규칙 사용: {e}")
    
    def _empty_recommendation_result(self, user_id: str, chatbot_output: Dict[str, Any]) -> Dict[str, Any]:
        """빈 추천 결과 반환"""
        return {
            'user_id': user_id,
            'original_query': chatbot_output.get('original_query', ''),
            'recommendations': [],
            'explanations': [],
            'metadata': {
                'total_candidates': 0,
                'final_recommendations': 0,
                'ranking_method': 'none',
                'error_occurred': True,
                'total_time': 0.0
            }
        }
    
    def _update_stats(self, candidates_count: int, response_time: float):
        """성능 통계 업데이트"""
        self.stats['total_requests'] += 1
        
        # 이동 평균 계산
        alpha = 0.1
        self.stats['avg_layer1_candidates'] = (
            alpha * candidates_count + (1 - alpha) * self.stats['avg_layer1_candidates']
        )
        self.stats['avg_response_time'] = (
            alpha * response_time + (1 - alpha) * self.stats['avg_response_time']
        )
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 반환"""
        return {
            'engine_stats': self.stats.copy(),
            'layer1_stats': self.candidate_generator.get_funnel_stats(),
            'feature_extractor_config': {
                'data_bias_corrections': self.feature_extractor.bias_corrections,
                'vector_search_weight': self.vector_search_weight,
                'rule_based_weight': self.rule_based_weight
            },
            'system_status': {
                'deep_learning_available': self.deep_learning_available,
                'vector_search_priority': True,
                'wide_component_active': True,
                'foodcard_management_active': self.foodcard_manager is not None
            }
        }
    
    def check_budget_compatibility(self, user_id: int, amount: int) -> Dict[str, Any]:
        """예산 내 구매 가능성 확인 (추천용)"""
        if not self.foodcard_manager:
            return {
                'affordable': False,
                'message': '급식카드 시스템이 비활성화되어 있습니다.'
            }
        
        # 잔액 확인
        balance = self.foodcard_manager.check_balance(user_id)
        affordable = self.foodcard_manager.can_afford(user_id, amount)
        is_low_balance = self.foodcard_manager.is_low_balance(user_id)
        
        return {
            'affordable': affordable,
            'current_balance': balance,
            'required_amount': amount,
            'is_low_balance': is_low_balance,
            'message': f"현재 잔액: {balance:,}원, 필요 금액: {amount:,}원" if balance else "급식카드가 등록되지 않았습니다."
        }


# 테스트 함수
def test_conversation_summary_based_engine():
    """conversation_summary 분석 반영한 추천 엔진 테스트"""
    print("=== conversation_summary 기반 Layer 1+2 통합 엔진 테스트 ===")
    
    # 엔진 초기화
    engine = RecommendationEngine()
    
    # 실제 DB 시트 구조 반영한 테스트 데이터
    test_user_profile = {
        'id': 863,                              # user.id
        'birthday': '1985-03-20',               # user.birthday
        'location': {                           # user_location 시트
            'state': '서울특별시',
            'city': '서울특별시'
        },
        'shop_favorite_count': 8,               # userfavorite 시트 집계
        'total_orders': 25,                     # product_order 시트 집계
        'review_count': 12                      # review 시트 집계
    }
    
    # 챗봇 Output (실제 챗봇 분석 결과)
    test_chatbot_output = {
        'original_query': '아이랑 갈만한 건강한 저녁 식당 추천해줘',
        'semantic_query': '가족 건강식 저녁 식당',      # 벡터 검색 핵심
        'filters': {
            'dietary_preferences': ['건강식', '가족식'],
            'time_of_day': 'dinner',
            'companion': 'family',
            'is_good_influence': True
        },
        'budget_filter': 30000,
        'location_filter': {
            'district': '관악구'
        }
    }
    
    # 상황 정보
    test_context = {
        'user_location': '관악구',
        'time_of_day': 'dinner',
        'current_time': datetime.now(),
        'weather': 'clear'
    }
    
    # 추천 실행
    result = engine.get_recommendations(
        user_id='user_863',
        user_profile=test_user_profile,
        chatbot_output=test_chatbot_output,
        context=test_context,
        top_k=5
    )
    
    print(f"\n=== 추천 결과 ===")
    print(f"원본 쿼리: {result['original_query']}")
    print(f"의미 쿼리: {result['semantic_query']}")
    print(f"추천 수: {len(result['recommendations'])}")
    print(f"랭킹 방법: {result['metadata']['ranking_method']}")
    print(f"벡터 검색 우선: {'예' if result['metadata']['vector_search_priority'] else '아니오'}")
    print(f"처리 시간: {result['metadata']['total_time']:.3f}초")
    
    print(f"\n=== Layer 1 Funnel 분석 ===")
    funnel_breakdown = result['metadata']['layer1_funnel_breakdown']
    for funnel, count in funnel_breakdown.items():
        print(f"  {funnel}: {count}개")
    
    print(f"\n=== 상위 추천 상세 ===")
    for i, rec in enumerate(result['recommendations'], 1):
        score = rec.get('personalized_score', 0)
        layer1_score = rec.get('layer1_base_score', 0)
        wide_score = rec.get('wide_component_score', 0)
        reasons = rec.get('bonus_reasons', [])
        vector_boosted = rec.get('vector_search_boosted', False)
        bias_corrected = rec.get('data_bias_corrected', False)
        
        print(f"{i}. {rec['shop_name']} ({rec.get('category', 'Unknown')})")
        print(f"   최종점수: {score:.1f} = Layer1({layer1_score:.1f}) + Wide({wide_score:.1f})")
        print(f"   이유: {', '.join(reasons[:4])}")
        
        tags = []
        if vector_boosted: tags.append("벡터검색부스트")
        if bias_corrected: tags.append("데이터편향보정")
        if tags:
            print(f"   특징: {', '.join(tags)}")
        print()
    
    print(f"=== 추천 설명 ===")
    for explanation in result['explanations']:
        print(f"  {explanation}")
    
    # 성능 통계
    print(f"\n=== 성능 통계 ===")
    stats = engine.get_performance_stats()
    print(f"총 요청: {stats['engine_stats']['total_requests']}")
    print(f"벡터 검색 사용: {stats['engine_stats']['vector_search_usage']}")
    print(f"딥러닝 사용: {stats['engine_stats']['deep_learning_usage']}")
    print(f"편향 보정 적용: {stats['engine_stats']['data_bias_corrections']}")
    print(f"평균 Layer1 후보: {stats['engine_stats']['avg_layer1_candidates']:.1f}개")
    print(f"평균 응답시간: {stats['engine_stats']['avg_response_time']:.3f}초")
    
    print(f"\n=== 시스템 설정 ===")
    print(f"데이터 편향 보정: {stats['feature_extractor_config']['data_bias_corrections']}")
    print(f"벡터 검색 가중치: {stats['feature_extractor_config']['vector_search_weight']}")
    print(f"딥러닝 모델: {'활성화' if stats['system_status']['deep_learning_available'] else '비활성화'}")
    print(f"Wide Component: {'활성화' if stats['system_status']['wide_component_active'] else '비활성화'}")


if __name__ == "__main__":
    test_conversation_summary_based_engine()