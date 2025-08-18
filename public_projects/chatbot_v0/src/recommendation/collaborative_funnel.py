"""
협업 필터링 Funnel (Funnel 1)
사용자 기반 협업 필터링 - 유사한 사용자 취향 기반 추천
현재는 규칙 기반 시뮬레이션, 추후 실제 데이터로 개선
"""

import json
import logging
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict, Counter
import random

logger = logging.getLogger(__name__)


class CollaborativeFunnel:
    """협업 필터링 기반 후보 생성 Funnel"""
    
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
        self._build_user_profiles()
    
    def _load_data(self):
        """매장 데이터 로드"""
        try:
            with open(self.restaurants_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.restaurants = data.get('shops', data.get('restaurants', []))
            
            logger.info(f"협業 Funnel: {len(self.restaurants)}개 매장 데이터 로드 완료")
            
        except Exception as e:
            logger.error(f"매장 데이터 로드 실패: {e}")
            self.restaurants = []
    
    def _build_user_profiles(self):
        """
        사용자 프로필 시뮬레이션 구축
        실제 서비스에서는 실제 사용자 행동 데이터 사용
        """
        # 사용자 타입별 선호도 정의
        self.user_type_preferences = {
            'healthy_eater': {
                'preferred_categories': ['한식', '샐러드', '베이커리'],
                'good_shop_preference': 0.8,  # 착한가게 선호도
                'price_sensitivity': 0.6,     # 가격 민감도 (높을수록 저렴한 것 선호)
                'variety_preference': 0.4      # 메뉴 다양성 선호도
            },
            'convenience_seeker': {
                'preferred_categories': ['분식', '치킨', '중식'],
                'good_shop_preference': 0.3,
                'price_sensitivity': 0.4,
                'variety_preference': 0.7
            },
            'gourmet': {
                'preferred_categories': ['일식', '양식', '중식'],
                'good_shop_preference': 0.5,
                'price_sensitivity': 0.2,
                'variety_preference': 0.8
            },
            'budget_conscious': {
                'preferred_categories': ['분식', '한식', '중식'],
                'good_shop_preference': 0.6,
                'price_sensitivity': 0.9,
                'variety_preference': 0.3
            },
            'default': {
                'preferred_categories': ['한식', '분식', '치킨'],
                'good_shop_preference': 0.5,
                'price_sensitivity': 0.5,
                'variety_preference': 0.5
            }
        }
        
        # 매장별 사용자 타입 선호도 점수 계산
        self.shop_type_scores = {}
        for restaurant in self.restaurants:
            shop_id = restaurant.get('id', restaurant.get('shopId', ''))
            self.shop_type_scores[shop_id] = self._calculate_type_scores(restaurant)
        
        logger.info(f"사용자 프로필 시뮬레이션 구축 완료")
    
    def _calculate_type_scores(self, restaurant: Dict[str, Any]) -> Dict[str, float]:
        """매장에 대한 사용자 타입별 점수 계산"""
        scores = {}
        category = restaurant.get('category', '').lower()
        is_good_shop = restaurant.get('attributes', {}).get('isGoodShop', False)
        menus = restaurant.get('menus', [])
        
        # 가격 정보
        prices = [menu.get('price', 0) for menu in menus if menu.get('price', 0) > 0]
        avg_price = sum(prices) / len(prices) if prices else 10000
        menu_count = len(menus)
        
        for user_type, preferences in self.user_type_preferences.items():
            score = 0.0
            
            # 1. 카테고리 선호도 (최대 40점)
            category_match = False
            for pref_category in preferences['preferred_categories']:
                if pref_category.lower() in category:
                    score += 40
                    category_match = True
                    break
            
            # 카테고리가 정확히 매칭되지 않으면 부분 점수
            if not category_match:
                for pref_category in preferences['preferred_categories']:
                    if any(word in category for word in pref_category.lower().split()):
                        score += 20
                        break
            
            # 2. 착한가게 선호도 (최대 20점)
            if is_good_shop:
                score += preferences['good_shop_preference'] * 20
            
            # 3. 가격 민감도 (최대 25점)
            # 가격이 낮을수록 price_sensitivity가 높은 사용자에게 높은 점수
            if avg_price <= 8000:
                score += preferences['price_sensitivity'] * 25
            elif avg_price <= 12000:
                score += preferences['price_sensitivity'] * 15
            elif avg_price <= 16000:
                score += preferences['price_sensitivity'] * 5
            
            # 4. 메뉴 다양성 선호도 (최대 15점)
            if menu_count >= 5:
                score += preferences['variety_preference'] * 15
            elif menu_count >= 3:
                score += preferences['variety_preference'] * 10
            elif menu_count >= 2:
                score += preferences['variety_preference'] * 5
            
            scores[user_type] = score
        
        return scores
    
    def get_candidates(self, 
                      user_id: Optional[str] = None,
                      user_type: Optional[str] = None,
                      filters: Optional[Dict[str, Any]] = None,
                      limit: int = 50,
                      recent_categories: Set[str] = None,
                      user_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        협업 필터링 기반 후보 매장 반환 (다양성 로직 추가)
        
        Args:
            user_id: 사용자 ID (현재는 미사용, 추후 실제 데이터로 확장)
            user_type: 사용자 타입 ('healthy_eater', 'convenience_seeker', 'gourmet', 'budget_conscious')
            filters: 추가 필터 조건
            limit: 반환할 후보 수
            recent_categories: 최근 추천된 카테고리 (제외용)
            user_context: 날씨, 영양 정보 등 컨텍스트
            
        Returns:
            협업 필터링 점수 순으로 정렬된 후보 매장 리스트
        """
        # 사용자 타입 결정
        if not user_type:
            user_type = self._infer_user_type(user_id, filters)
        
        if user_type not in self.user_type_preferences:
            user_type = 'default'
        
        if recent_categories is None:
            recent_categories = set()
        
        candidates = []
        
        for restaurant in self.restaurants:
            shop_id = restaurant.get('id', restaurant.get('shopId', ''))
            category = restaurant.get('category', '')
            
            # 최근 추천 카테고리 제외 (다양성 확보)
            if category.lower() in {cat.lower() for cat in recent_categories}:
                continue
            
            # 기본 필터 적용
            if not self._passes_basic_filters(restaurant, filters or {}):
                continue
            
            # 협업 필터링 점수 계산
            collaborative_score = self.shop_type_scores.get(shop_id, {}).get(user_type, 0)
            
            # Context 기반 점수 조정
            if user_context:
                # 날씨 기반
                if 'weather' in user_context:
                    weather = user_context['weather'].get('condition', '')
                    if weather in ['rain', 'Rain'] and any(w in category.lower() for w in ['국물', '전', '탕']):
                        collaborative_score += 15
                
                # 영양 기반
                if 'nutrition_status' in user_context:
                    issues = user_context['nutrition_status'].get('current_issues', [])
                    if 'vitamin_deficiency' in issues and any(w in category.lower() for w in ['샐러드', '채소']):
                        collaborative_score += 10
            
            # 점수가 너무 낮으면 제외
            if collaborative_score < 10:
                continue
            
            candidate = {
                'shop_id': shop_id,
                'shop_name': restaurant.get('name', restaurant.get('shopName', '')),
                'category': restaurant.get('category', ''),
                'funnel_source': 'collaborative',
                'collaborative_score': collaborative_score,
                'reason': self._get_collaborative_reason(restaurant, user_type)
            }
            candidates.append(candidate)
        
        # 협업 필터링 점수로 정렬
        candidates.sort(key=lambda x: x['collaborative_score'], reverse=True)
        
        logger.info(f"협업 Funnel: {len(candidates[:limit])}개 후보 생성 (사용자 타입: {user_type})")
        return candidates[:limit]
    
    def _infer_user_type(self, user_id: Optional[str], filters: Dict[str, Any]) -> str:
        """필터 조건으로부터 사용자 타입 추론"""
        # 현재는 간단한 규칙 기반, 추후 ML 모델로 개선 가능
        
        # 착한가게 필터가 있으면 건강 지향
        if filters.get('is_good_influence'):
            return 'healthy_eater'
        
        # 가격대별 추론
        if filters.get('max_price'):
            max_price = filters['max_price']
            if max_price <= 8000:
                return 'budget_conscious'
            elif max_price >= 20000:
                return 'gourmet'
        
        # 카테고리별 추론
        category = filters.get('category', '').lower()
        if category:
            if '일식' in category or '양식' in category:
                return 'gourmet'
            elif '분식' in category or '치킨' in category:
                return 'convenience_seeker'
            elif '한식' in category:
                return 'healthy_eater'
        
        return 'default'
    
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
        
        # 급식카드 필터
        if filters.get('accepts_meal_card'):
            if not restaurant.get('attributes', {}).get('acceptsMealCard', False):
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
                        return False
        
        return True
    
    def _get_collaborative_reason(self, restaurant: Dict[str, Any], user_type: str) -> str:
        """협업 필터링 추천 이유 생성"""
        preferences = self.user_type_preferences.get(user_type, {})
        reasons = []
        
        # 사용자 타입별 설명
        type_descriptions = {
            'healthy_eater': '건강 지향 사용자들이 선호',
            'convenience_seeker': '편의성 중시 사용자들이 선호',
            'gourmet': '미식가들이 선호',
            'budget_conscious': '가격 중시 사용자들이 선호'
        }
        
        if user_type in type_descriptions:
            reasons.append(type_descriptions[user_type])
        
        # 구체적인 이유 추가
        category = restaurant.get('category', '').lower()
        if any(pref_cat.lower() in category for pref_cat in preferences.get('preferred_categories', [])):
            reasons.append('취향 맞춤')
        
        if restaurant.get('attributes', {}).get('isGoodShop', False) and preferences.get('good_shop_preference', 0) > 0.6:
            reasons.append('착한가게')
        
        menus = restaurant.get('menus', [])
        if menus:
            prices = [menu.get('price', 0) for menu in menus if menu.get('price', 0) > 0]
            if prices:
                avg_price = sum(prices) / len(prices)
                if avg_price <= 10000 and preferences.get('price_sensitivity', 0) > 0.6:
                    reasons.append('합리적 가격')
        
        return ' · '.join(reasons) if reasons else '유사 취향 추천'
    
    def get_user_type_distribution(self) -> Dict[str, Dict[str, float]]:
        """사용자 타입별 매장 점수 분포"""
        distribution = {}
        
        for user_type in self.user_type_preferences.keys():
            scores = []
            for shop_scores in self.shop_type_scores.values():
                if user_type in shop_scores:
                    scores.append(shop_scores[user_type])
            
            if scores:
                distribution[user_type] = {
                    'avg_score': sum(scores) / len(scores),
                    'max_score': max(scores),
                    'min_score': min(scores),
                    'shop_count': len(scores)
                }
        
        return distribution


# 테스트 함수
def test_collaborative_funnel():
    """협업 필터링 Funnel 테스트"""
    funnel = CollaborativeFunnel()
    
    print("=== 협업 필터링 Funnel 테스트 ===")
    
    # 건강 지향 사용자 추천
    healthy_candidates = funnel.get_candidates(
        user_type="healthy_eater",
        limit=5
    )
    print(f"\n건강 지향 사용자 추천 Top 5:")
    for i, candidate in enumerate(healthy_candidates, 1):
        print(f"{i}. {candidate['shop_name']} ({candidate['category']}) - {candidate['collaborative_score']:.1f}점")
        print(f"   이유: {candidate['reason']}")
    
    # 편의성 중시 사용자 추천
    convenience_candidates = funnel.get_candidates(
        user_type="convenience_seeker",
        limit=3
    )
    print(f"\n편의성 중시 사용자 추천 Top 3:")
    for i, candidate in enumerate(convenience_candidates, 1):
        print(f"{i}. {candidate['shop_name']} ({candidate['category']}) - {candidate['collaborative_score']:.1f}점")
        print(f"   이유: {candidate['reason']}")
    
    # 미식가 추천
    gourmet_candidates = funnel.get_candidates(
        user_type="gourmet",
        limit=3
    )
    print(f"\n미식가 추천 Top 3:")
    for i, candidate in enumerate(gourmet_candidates, 1):
        print(f"{i}. {candidate['shop_name']} ({candidate['category']}) - {candidate['collaborative_score']:.1f}점")
        print(f"   이유: {candidate['reason']}")
    
    # 가격 중시 사용자 추천
    budget_candidates = funnel.get_candidates(
        user_type="budget_conscious",
        filters={'max_price': 10000},
        limit=3
    )
    print(f"\n가격 중시 사용자 추천 (1만원 이하) Top 3:")
    for i, candidate in enumerate(budget_candidates, 1):
        print(f"{i}. {candidate['shop_name']} ({candidate['category']}) - {candidate['collaborative_score']:.1f}점")
        print(f"   이유: {candidate['reason']}")
    
    # 사용자 타입별 분포
    distribution = funnel.get_user_type_distribution()
    print(f"\n=== 사용자 타입별 점수 분포 ===")
    for user_type, stats in distribution.items():
        print(f"{user_type}: 평균 {stats['avg_score']:.1f}점 (매장 {stats['shop_count']}개)")


if __name__ == "__main__":
    test_collaborative_funnel()