"""
메뉴 정보 헬퍼 유틸리티
Shop과 Menu 데이터를 연결하는 헬퍼 함수들
"""

import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class MenuHelper:
    """메뉴 정보 관리 헬퍼"""
    
    _instance = None
    _menu_cache = None  # shop_id -> menus 매핑 캐시
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_menu_data()
        return cls._instance
    
    def _load_menu_data(self):
        """메뉴 데이터를 로드하고 shop_id별로 인덱싱"""
        if self._menu_cache is not None:
            return  # 이미 로드됨
            
        self._menu_cache = {}
        
        try:
            # 데이터 파일 경로
            base_dir = Path(__file__).parent.parent
            data_path = base_dir / 'data' / 'restaurants_real.json'
            
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            menus = data.get('menus', [])
            
            # shop_id별로 메뉴 그룹화
            for menu in menus:
                shop_id = menu.get('shop_id')
                if shop_id:
                    if shop_id not in self._menu_cache:
                        self._menu_cache[shop_id] = []
                    self._menu_cache[shop_id].append(menu)
            
            logger.info(f"MenuHelper: {len(self._menu_cache)}개 가게의 메뉴 데이터 로드 완료")
            
        except Exception as e:
            logger.error(f"메뉴 데이터 로드 실패: {e}")
            self._menu_cache = {}
    
    def get_shop_menus(self, shop_id: int) -> List[Dict[str, Any]]:
        """특정 가게의 메뉴 목록 반환"""
        return self._menu_cache.get(shop_id, [])
    
    def get_shop_min_price(self, shop_id: int) -> Optional[int]:
        """가게의 최소 메뉴 가격 반환"""
        menus = self.get_shop_menus(shop_id)
        if not menus:
            return None
        
        prices = [m.get('price', 0) for m in menus if m.get('price', 0) > 0]
        return min(prices) if prices else None
    
    def get_shop_avg_price(self, shop_id: int) -> Optional[int]:
        """가게의 평균 메뉴 가격 반환"""
        menus = self.get_shop_menus(shop_id)
        if not menus:
            return None
        
        prices = [m.get('price', 0) for m in menus if m.get('price', 0) > 0]
        return int(sum(prices) / len(prices)) if prices else None
    
    def enrich_shop_with_menus(self, shop: Dict[str, Any]) -> Dict[str, Any]:
        """Shop 객체에 메뉴 정보 추가"""
        shop_id = shop.get('id') or shop.get('shop_id') or shop.get('shopId')
        
        if shop_id:
            shop['menus'] = self.get_shop_menus(shop_id)
            shop['min_price'] = self.get_shop_min_price(shop_id)
            shop['avg_price'] = self.get_shop_avg_price(shop_id)
        
        return shop
    
    def filter_shops_by_price(self, shops: List[Dict[str, Any]], max_price: int) -> List[Dict[str, Any]]:
        """가격 기준으로 가게 필터링"""
        filtered = []
        
        for shop in shops:
            shop_id = shop.get('id') or shop.get('shop_id') or shop.get('shopId')
            if shop_id:
                min_price = self.get_shop_min_price(shop_id)
                
                # 메뉴 정보가 없으면 포함 (나중에 검증)
                if min_price is None:
                    filtered.append(shop)
                # 최소 가격이 한도 이하면 포함
                elif min_price <= max_price:
                    filtered.append(shop)
                else:
                    logger.debug(f"가격 필터 제외: {shop.get('name')} (최소 {min_price}원 > {max_price}원)")
        
        return filtered


# 싱글톤 인스턴스 생성 함수
def get_menu_helper() -> MenuHelper:
    """MenuHelper 싱글톤 인스턴스 반환"""
    return MenuHelper()


# 편의 함수들
def get_shop_menus(shop_id: int) -> List[Dict[str, Any]]:
    """특정 가게의 메뉴 목록 반환"""
    return get_menu_helper().get_shop_menus(shop_id)


def get_shop_min_price(shop_id: int) -> Optional[int]:
    """가게의 최소 메뉴 가격 반환"""
    return get_menu_helper().get_shop_min_price(shop_id)


def enrich_shop_with_menus(shop: Dict[str, Any]) -> Dict[str, Any]:
    """Shop 객체에 메뉴 정보 추가"""
    return get_menu_helper().enrich_shop_with_menus(shop)