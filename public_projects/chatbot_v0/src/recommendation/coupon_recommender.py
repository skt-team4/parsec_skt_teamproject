"""
쿠폰 기반 추천 시스템 확장
"""

from typing import List, Dict, Optional, Tuple
import logging
from datetime import datetime

from src.data.data_structure import NaviyamKnowledge, NaviyamShop, NaviyamMenu, FoodcardUser

logger = logging.getLogger(__name__)


class CouponRecommender:
    """쿠폰을 고려한 추천 시스템"""
    
    def __init__(self, knowledge: NaviyamKnowledge):
        self.knowledge = knowledge
        
    def enhance_recommendations_with_coupons(self, recommendations: List[Dict], 
                                           user_id: Optional[int] = None) -> List[Dict]:
        """기존 추천 결과에 쿠폰 정보 추가"""
        enhanced_recommendations = []
        
        # 급식카드 사용자 확인
        foodcard_user = None
        if user_id:
            foodcard_user = self.knowledge.foodcard_users.get(str(user_id))
        
        for rec in recommendations:
            shop_id = rec.get('shop_id')
            shop = self.knowledge.shops.get(shop_id)
            if not shop:
                enhanced_recommendations.append(rec)
                continue
                
            # 가게의 메뉴들 확인
            shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop_id]
            if not shop_menus:
                enhanced_recommendations.append(rec)
                continue
                
            # 대표 메뉴 선택 (인기 메뉴 또는 가장 저렴한 메뉴)
            popular_menus = [m for m in shop_menus if m.is_popular]
            if popular_menus:
                selected_menu = min(popular_menus, key=lambda m: m.price)
            else:
                selected_menu = min(shop_menus, key=lambda m: m.price)
            
            # 적용 가능한 쿠폰 찾기
            applicable_coupons = self.knowledge.get_applicable_coupons(
                user_id=user_id,
                shop_id=shop_id,
                category=shop.category,
                price=selected_menu.price
            )
            
            # 추천 결과 개선
            enhanced_rec = rec.copy()
            enhanced_rec['menu_price'] = selected_menu.price
            enhanced_rec['menu_name'] = selected_menu.name
            
            if applicable_coupons:
                best_coupon = applicable_coupons[0]
                discount = best_coupon.calculate_discount(selected_menu.price)
                final_price = selected_menu.price - discount
                
                enhanced_rec['coupon_available'] = True
                enhanced_rec['coupon_id'] = best_coupon.id
                enhanced_rec['coupon_name'] = best_coupon.name
                enhanced_rec['discount_amount'] = discount
                enhanced_rec['final_price'] = final_price
                
                # 급식카드 잔액 체크
                if foodcard_user:
                    if foodcard_user.balance >= final_price:
                        enhanced_rec['affordable_with_coupon'] = True
                    else:
                        enhanced_rec['affordable_with_coupon'] = False
                        
                # 점수 조정 (쿠폰 사용 가능한 경우 가산점)
                if 'score' in enhanced_rec:
                    enhanced_rec['score'] *= 1.2  # 20% 가산점
                    
            enhanced_recommendations.append(enhanced_rec)
            
        # 쿠폰 적용 시 구매 가능한 것 우선 정렬
        if foodcard_user:
            enhanced_recommendations.sort(
                key=lambda x: (
                    x.get('affordable_with_coupon', False),
                    x.get('score', 0)
                ),
                reverse=True
            )
            
        return enhanced_recommendations
    
    def find_affordable_options_with_coupons(self, user_id: int, 
                                           max_results: int = 5) -> List[Dict]:
        """잔액 부족 시 쿠폰으로 구매 가능한 옵션 찾기"""
        foodcard_user = self.knowledge.foodcard_users.get(str(user_id))
        if not foodcard_user:
            return []
            
        balance = foodcard_user.balance
        affordable_options = []
        
        # 모든 급식카드 사용 가능 가게 확인
        for shop in self.knowledge.shops.values():
            if shop.is_food_card_shop != 'Y':
                continue
                
            # 가게의 메뉴들 확인
            shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
            
            for menu in shop_menus:
                # 원래 가격으로는 살 수 없는 메뉴
                if menu.price <= balance:
                    continue
                    
                # 쿠폰 적용 확인
                applicable_coupons = self.knowledge.get_applicable_coupons(
                    user_id=user_id,
                    shop_id=shop.id,
                    category=shop.category,
                    price=menu.price
                )
                
                for coupon in applicable_coupons:
                    discount = coupon.calculate_discount(menu.price)
                    final_price = menu.price - discount
                    
                    # 쿠폰 적용 시 구매 가능
                    if final_price <= balance:
                        option = {
                            'shop_id': shop.id,
                            'shop_name': shop.name,
                            'shop_category': shop.category,
                            'menu_id': menu.id,
                            'menu_name': menu.name,
                            'original_price': menu.price,
                            'coupon_id': coupon.id,
                            'coupon_name': coupon.name,
                            'discount_amount': discount,
                            'final_price': final_price,
                            'savings_rate': discount / menu.price,
                            'is_good_influence': shop.is_good_influence_shop
                        }
                        affordable_options.append(option)
                        break  # 한 메뉴당 하나의 쿠폰만
                        
        # 정렬: 할인율 높은 순 > 착한가게 우선
        affordable_options.sort(
            key=lambda x: (x['savings_rate'], x['is_good_influence']),
            reverse=True
        )
        
        return affordable_options[:max_results]
    
    def get_expiring_coupon_recommendations(self, user_id: Optional[int] = None,
                                          days: int = 3) -> List[Dict]:
        """만료 임박 쿠폰 활용 추천"""
        from utils.coupon_manager import CouponManager
        coupon_manager = CouponManager(self.knowledge)
        
        expiring_coupons = coupon_manager.get_expiring_coupons(days=days)
        recommendations = []
        
        for coupon in expiring_coupons:
            # 쿠폰 사용 가능한 가게/메뉴 찾기
            if coupon.usage_type == "CATEGORY":
                # 카테고리별 쿠폰
                shops = self.knowledge.get_shops_by_category(coupon.target[0])
                for shop in shops[:2]:  # 각 쿠폰당 최대 2개 가게
                    shop_menus = [m for m in self.knowledge.menus.values() 
                                 if m.shop_id == shop.id and m.price >= (coupon.min_amount or 0)]
                    if shop_menus:
                        menu = min(shop_menus, key=lambda m: m.price)
                        discount = coupon.calculate_discount(menu.price)
                        
                        recommendations.append({
                            'urgency': 'EXPIRING_SOON',
                            'days_until_expiry': (datetime.fromisoformat(coupon.valid_until.replace('Z', '+00:00')) 
                                                - datetime.now()).days,
                            'coupon_id': coupon.id,
                            'coupon_name': coupon.name,
                            'shop_id': shop.id,
                            'shop_name': shop.name,
                            'menu_name': menu.name,
                            'original_price': menu.price,
                            'discount_amount': discount,
                            'final_price': menu.price - discount
                        })
                        
        # 만료일 가까운 순으로 정렬
        recommendations.sort(key=lambda x: x['days_until_expiry'])
        return recommendations