"""
인기도 기반 Funnel (Funnel 4)
가장 간단한 추천 로직 - 단순 집계 기반
"""

import json
import logging
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict, Counter
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PopularityFunnel:
    """인기도 기반 후보 생성 Funnel"""
    
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
        self.popularity_scores = {}
        self._load_data()
    
    def _load_data(self):
        """매장 데이터 로드"""
        try:
            with open(self.restaurants_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.restaurants = data.get('shops', data.get('restaurants', []))
            
            logger.info(f"인기도 Funnel: {len(self.restaurants)}개 매장 데이터 로드 완료")
            self._calculate_popularity_scores()
            
        except Exception as e:
            logger.error(f"매장 데이터 로드 실패: {e}")
            self.restaurants = []
    
    def _calculate_popularity_scores(self):
        """
        매장별 인기도 점수 계산
        현재는 간단한 규칙 기반으로 계산 (추후 실제 데이터로 대체)
        """
        for restaurant in self.restaurants:
            shop_id = restaurant.get('id', restaurant.get('shopId', ''))
            
            # 기본 점수 계산 요소들
            base_score = 0
            
            # 1. 착한가게 보너스
            if restaurant.get('attributes', {}).get('isGoodShop', False):
                base_score += 20
            
            # 2. 급식카드 사용 가능 보너스  
            if restaurant.get('attributes', {}).get('acceptsMealCard', False):
                base_score += 10
            
            # 3. 메뉴 다양성 점수 (메뉴 개수 기반)
            menu_count = len(restaurant.get('menus', []))
            base_score += min(menu_count * 5, 25)  # 최대 25점
            
            # 4. 가격 접근성 점수 (저렴한 메뉴가 있으면 보너스)
            menus = restaurant.get('menus', [])
            if menus:
                min_price = min(menu.get('price', float('inf')) for menu in menus)
                if min_price <= 8000:  # 8천원 이하 메뉴가 있으면
                    base_score += 15
                elif min_price <= 12000:  # 1만2천원 이하
                    base_score += 10
            
            # 5. 영업시간 점수 (긴 영업시간 = 접근성 좋음)
            hours = restaurant.get('hours', {})
            if hours.get('open') and hours.get('close'):
                try:
                    open_time = datetime.strptime(hours['open'], '%H:%M').time()
                    close_time = datetime.strptime(hours['close'], '%H:%M').time()
                    
                    # 영업시간이 10시간 이상이면 보너스
                    if close_time.hour - open_time.hour >= 10:
                        base_score += 10
                except:
                    pass
            
            self.popularity_scores[shop_id] = base_score
        
        logger.info(f"인기도 점수 계산 완료: 평균 {sum(self.popularity_scores.values()) / len(self.popularity_scores):.1f}점")
    
    def get_candidates(self, 
                      filters: Optional[Dict[str, Any]] = None, 
                      limit: int = 30,
                      recent_categories: Set[str] = None,
                      user_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        인기도 기반 후보 매장 반환 (다양성 로직 추가)
        
        Args:
            filters: 필터 조건 (location, category 등)
            limit: 반환할 후보 수
            recent_categories: 최근 추천된 카테고리 (제외용)
            user_context: 날씨, 영양 정보 등 컨텍스트
            
        Returns:
            인기도 순으로 정렬된 후보 매장 리스트
        """
        candidates = []
        if recent_categories is None:
            recent_categories = set()
        
        # 필터링된 매장들
        filtered_restaurants = self._apply_filters(self.restaurants, filters or {})
        
        # 1. 최근 추천 카테고리 제외 (다양성 확보)
        if recent_categories:
            filtered_restaurants = [
                r for r in filtered_restaurants
                if r.get('category', '').lower() not in {cat.lower() for cat in recent_categories}
            ]
            if filtered_restaurants:
                logger.debug(f"PopularityFunnel: {len(recent_categories)}개 카테고리 제외 후 {len(filtered_restaurants)}개 매장")
        
        # 2. Context 기반 점수 조정
        for restaurant in filtered_restaurants:
            shop_id = restaurant.get('id', restaurant.get('shopId', ''))
            base_score = self.popularity_scores.get(shop_id, 0)
            context_score = 0
            
            # 날씨 기반 가중치
            if user_context and 'weather' in user_context:
                weather = user_context['weather'].get('condition', '')
                category = restaurant.get('category', '').lower()
                
                if weather in ['rain', 'Rain', '비']:
                    if any(w in category for w in ['국물', '전', '탕', '찌개', '라면']):
                        context_score += 20
                        logger.debug(f"날씨 보너스: {restaurant.get('name')} +20 (비오는날)")
                elif weather in ['clear', 'Clear', '맑음'] and user_context['weather'].get('temp', 20) > 25:
                    if any(w in category for w in ['냉면', '샐러드', '빙수']):
                        context_score += 15
                        logger.debug(f"날씨 보너스: {restaurant.get('name')} +15 (더운날)")
            
            # 영양 균형 가중치
            if user_context and 'nutrition_status' in user_context:
                issues = user_context['nutrition_status'].get('current_issues', [])
                category = restaurant.get('category', '').lower()
                
                if 'vitamin_deficiency' in issues and any(w in category for w in ['샐러드', '과일', '채소']):
                    context_score += 15
                    logger.debug(f"영양 보너스: {restaurant.get('name')} +15 (비타민)")
            
            restaurant['_final_score'] = base_score + context_score
        
        # 인기도 점수로 정렬 (context 점수 포함)
        sorted_restaurants = sorted(
            filtered_restaurants,
            key=lambda x: x.get('_final_score', self.popularity_scores.get(x.get('shopId', ''), 0)),
            reverse=True
        )
        
        # 후보 생성
        for restaurant in sorted_restaurants[:limit]:
            shop_id = restaurant.get('id', restaurant.get('shopId', ''))
            candidate = {
                'shop_id': shop_id,
                'shop_name': restaurant.get('name', restaurant.get('shopName', '')),
                'category': restaurant.get('category', ''),
                'funnel_source': 'popularity',
                'base_score': self.popularity_scores.get(shop_id, 0),
                'reason': self._get_popularity_reason(restaurant)
            }
            candidates.append(candidate)
        
        logger.info(f"인기도 Funnel: {len(candidates)}개 후보 생성 (필터: {filters})")
        return candidates
    
    def _apply_filters(self, restaurants: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
        """필터 조건 적용"""
        filtered = restaurants
        
        # 카테고리 필터
        if filters.get('category'):
            category_filter = filters['category'].lower()
            filtered = [r for r in filtered 
                       if category_filter in r.get('category', '').lower()]
        
        # 카테고리 제외 필터 (MODIFY_REQUEST 처리)
        if filters.get('exclude_category'):
            exclude_categories = filters['exclude_category']
            # 리스트가 아니면 리스트로 변환
            if isinstance(exclude_categories, str):
                exclude_categories = [exclude_categories]
            
            # 모든 제외 카테고리에 대해 필터링
            for exclude_cat in exclude_categories:
                exclude_filter = exclude_cat.lower()
                filtered = [r for r in filtered 
                           if exclude_filter not in r.get('category', '').lower()]
            logger.debug(f"카테고리 제외 필터 적용: {exclude_categories} - 남은 매장 수: {len(filtered)}")
        
        # 위치 필터 (주소에 포함된 키워드로 검색)
        if filters.get('location'):
            location_filter = filters['location']
            filtered = [r for r in filtered 
                       if location_filter in r.get('location', {}).get('address', '')]
        
        # 착한가게 필터
        if filters.get('is_good_influence'):
            filtered = [r for r in filtered 
                       if r.get('attributes', {}).get('isGoodShop', False)]
        
        # 급식카드 필터
        if filters.get('accepts_meal_card'):
            filtered = [r for r in filtered 
                       if r.get('attributes', {}).get('acceptsMealCard', False)]
        
        # 최대 가격 필터
        if filters.get('max_price'):
            max_price = filters['max_price']
            filtered_by_price = []
            
            # MenuHelper 사용
            try:
                from src.utils.menu_helper import get_shop_min_price
                for r in filtered:
                    shop_id = r.get('id') or r.get('shop_id') or r.get('shopId')
                    if shop_id:
                        min_price = get_shop_min_price(shop_id)
                        if min_price is None or min_price <= max_price:
                            filtered_by_price.append(r)
                        else:
                            logger.debug(f"제외: {r.get('name')} - 최소가격 {min_price}원이 한도 {max_price}원 초과")
                    else:
                        filtered_by_price.append(r)  # shop_id가 없으면 포함
            except ImportError:
                # Fallback: 기존 방식
                for r in filtered:
                    menus = r.get('menus', [])
                    if menus:
                        min_price = min(menu.get('price', float('inf')) for menu in menus)
                        if min_price <= max_price:
                            filtered_by_price.append(r)
                        else:
                            logger.debug(f"제외: {r.get('name')} - 최소가격 {min_price}원이 한도 {max_price}원 초과")
                    else:
                        filtered_by_price.append(r)
            
            filtered = filtered_by_price
            logger.debug(f"가격 필터 적용 (한도: {max_price}원) - 남은 매장 수: {len(filtered)}")
        
        return filtered
    
    def _get_popularity_reason(self, restaurant: Dict[str, Any]) -> str:
        """인기 이유 생성"""
        reasons = []
        
        if restaurant.get('attributes', {}).get('isGoodShop', False):
            reasons.append('착한가게')
        
        if restaurant.get('attributes', {}).get('acceptsMealCard', False):
            reasons.append('급식카드 사용가능')
        
        menu_count = len(restaurant.get('menus', []))
        if menu_count >= 5:
            reasons.append('다양한 메뉴')
        
        menus = restaurant.get('menus', [])
        if menus:
            min_price = min(menu.get('price', float('inf')) for menu in menus)
            if min_price <= 8000:
                reasons.append('저렴한 가격')
        
        return ' · '.join(reasons) if reasons else '인기 매장'
    
    def get_popularity_stats(self) -> Dict[str, Any]:
        """인기도 통계 반환"""
        if not self.popularity_scores:
            return {}
        
        scores = list(self.popularity_scores.values())
        return {
            'total_shops': len(scores),
            'avg_score': sum(scores) / len(scores),
            'max_score': max(scores),
            'min_score': min(scores),
            'top_shops': sorted(
                [(shop_id, score) for shop_id, score in self.popularity_scores.items()],
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }


# 테스트 함수
def test_popularity_funnel():
    """인기도 Funnel 테스트"""
    funnel = PopularityFunnel()
    
    print("=== 인기도 Funnel 테스트 ===")
    
    # 전체 인기 매장
    candidates = funnel.get_candidates(limit=5)
    print(f"\n전체 인기 매장 Top 5:")
    for i, candidate in enumerate(candidates, 1):
        print(f"{i}. {candidate['shop_name']} ({candidate['category']}) - {candidate['base_score']}점")
        print(f"   이유: {candidate['reason']}")
    
    # 한식 카테고리 필터
    korean_candidates = funnel.get_candidates(
        filters={'category': '한식'}, 
        limit=3
    )
    print(f"\n한식 인기 매장 Top 3:")
    for i, candidate in enumerate(korean_candidates, 1):
        print(f"{i}. {candidate['shop_name']} - {candidate['base_score']}점")
    
    # 착한가게 필터
    good_shop_candidates = funnel.get_candidates(
        filters={'is_good_influence': True}, 
        limit=3
    )
    print(f"\n착한가게 Top 3:")
    for i, candidate in enumerate(good_shop_candidates, 1):
        print(f"{i}. {candidate['shop_name']} - {candidate['base_score']}점")
    
    # 통계 정보
    stats = funnel.get_popularity_stats()
    print(f"\n=== 인기도 통계 ===")
    print(f"총 매장 수: {stats['total_shops']}")
    print(f"평균 점수: {stats['avg_score']:.1f}")
    print(f"최고 점수: {stats['max_score']}")


if __name__ == "__main__":
    test_popularity_funnel()