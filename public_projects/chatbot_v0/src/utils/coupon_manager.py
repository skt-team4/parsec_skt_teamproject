"""
쿠폰 관리 및 매칭 시스템
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

from src.data.data_structure import NaviyamCoupon, NaviyamShop, NaviyamMenu, FoodcardUser, NaviyamKnowledge

logger = logging.getLogger(__name__)


@dataclass
class CouponRecommendation:
    """쿠폰 추천 결과"""
    coupon: NaviyamCoupon
    discount_amount: int
    final_price: int
    reason: str
    priority: float  # 우선순위 점수


class CouponManager:
    """쿠폰 매칭 및 관리 시스템"""
    
    def __init__(self, knowledge: NaviyamKnowledge):
        self.knowledge = knowledge
        
    def get_best_coupons_for_menu(self, menu: NaviyamMenu, user_id: Optional[int] = None, 
                                  max_results: int = 3) -> List[CouponRecommendation]:
        """메뉴에 적용 가능한 최적 쿠폰 추천"""
        shop = self.knowledge.shops.get(menu.shop_id)
        if not shop:
            return []
            
        # 적용 가능한 쿠폰 찾기
        applicable_coupons = self.knowledge.get_applicable_coupons(
            user_id=user_id,
            shop_id=shop.id,
            category=shop.category,
            price=menu.price
        )
        
        recommendations = []
        for coupon in applicable_coupons[:max_results]:
            discount = coupon.calculate_discount(menu.price)
            final_price = menu.price - discount
            
            # 추천 이유 생성
            reason = self._generate_recommendation_reason(coupon, shop, menu, user_id)
            
            # 우선순위 계산
            priority = self._calculate_priority(coupon, discount, menu.price, user_id)
            
            recommendations.append(CouponRecommendation(
                coupon=coupon,
                discount_amount=discount,
                final_price=final_price,
                reason=reason,
                priority=priority
            ))
            
        # 우선순위 기준 정렬
        recommendations.sort(key=lambda x: x.priority, reverse=True)
        return recommendations
    
    def find_emergency_coupons(self, user_id: int, target_price: int) -> List[CouponRecommendation]:
        """잔액 부족 시 긴급 쿠폰 찾기"""
        foodcard_user = self.knowledge.foodcard_users.get(str(user_id))
        if not foodcard_user:
            return []
            
        balance = foodcard_user.balance
        recommendations = []
        
        # 잔액으로 살 수 있는 메뉴 + 쿠폰 조합 찾기
        for menu in self.knowledge.menus.values():
            if menu.price <= balance:
                continue  # 이미 살 수 있는 메뉴는 제외
                
            shop = self.knowledge.shops.get(menu.shop_id)
            if not shop or shop.is_food_card_shop != 'Y':
                continue
                
            # 쿠폰 적용 시 구매 가능한지 확인
            coupons = self.get_best_coupons_for_menu(menu, user_id, max_results=1)
            for coupon_rec in coupons:
                if coupon_rec.final_price <= balance:
                    recommendations.append(coupon_rec)
                    break
                    
        # 할인 후 가격이 목표 가격에 가까운 순으로 정렬
        recommendations.sort(key=lambda x: abs(x.final_price - target_price))
        return recommendations[:5]
    
    def get_expiring_coupons(self, days: int = 3) -> List[NaviyamCoupon]:
        """만료 임박 쿠폰 찾기"""
        expiring_coupons = []
        now = datetime.now()
        
        for coupon in self.knowledge.coupons.values():
            if not coupon.valid_until:
                continue
                
            expiry_date = datetime.fromisoformat(coupon.valid_until.replace('Z', '+00:00'))
            days_until_expiry = (expiry_date - now).days
            
            if 0 <= days_until_expiry <= days:
                expiring_coupons.append(coupon)
                
        # 만료일 가까운 순으로 정렬
        expiring_coupons.sort(key=lambda c: c.valid_until)
        return expiring_coupons
    
    def _generate_recommendation_reason(self, coupon: NaviyamCoupon, shop: NaviyamShop, 
                                      menu: NaviyamMenu, user_id: Optional[int]) -> str:
        """쿠폰 추천 이유 생성"""
        reasons = []
        
        if coupon.usage_type == "FOODCARD":
            reasons.append("급식카드 전용 혜택")
        elif coupon.usage_type == "GOOD_SHOP":
            reasons.append("착한가게 특별 할인")
        elif coupon.usage_type == "EMERGENCY":
            reasons.append("월말 긴급 지원")
        elif coupon.usage_type == "CATEGORY":
            reasons.append(f"{shop.category} 카테고리 할인")
            
        if user_id:
            foodcard_user = self.knowledge.foodcard_users.get(str(user_id))
            if foodcard_user and foodcard_user.is_low_balance():
                reasons.append("잔액 부족 지원")
                
        if shop.is_good_influence_shop:
            reasons.append("착한가게")
            
        if menu.is_popular:
            reasons.append("인기메뉴")
            
        return " + ".join(reasons) if reasons else "특별 할인"
    
    def _calculate_priority(self, coupon: NaviyamCoupon, discount: int, 
                          original_price: int, user_id: Optional[int]) -> float:
        """쿠폰 우선순위 점수 계산"""
        priority = 0.0
        
        # 할인율 기준 (최대 40점)
        discount_rate = discount / original_price if original_price > 0 else 0
        priority += discount_rate * 40
        
        # 할인 금액 기준 (최대 30점)
        priority += min(discount / 100, 30)  # 100원당 1점, 최대 30점
        
        # 쿠폰 타입별 가산점
        if coupon.usage_type == "EMERGENCY":
            priority += 20  # 긴급 지원 우선
        elif coupon.usage_type == "GOOD_SHOP":
            priority += 15  # 착한가게 우선
        elif coupon.usage_type == "FOODCARD":
            priority += 10  # 급식카드 전용
            
        # 만료 임박 가산점
        if coupon.valid_until:
            days_until_expiry = (datetime.fromisoformat(coupon.valid_until.replace('Z', '+00:00')) - datetime.now()).days
            if days_until_expiry <= 3:
                priority += 15
            elif days_until_expiry <= 7:
                priority += 10
                
        # 사용자 상황별 가산점
        if user_id:
            foodcard_user = self.knowledge.foodcard_users.get(str(user_id))
            if foodcard_user and foodcard_user.is_low_balance():
                priority += 20
                
        return priority


class UserCouponWallet:
    """사용자별 쿠폰 지갑 관리"""
    
    def __init__(self):
        # 실제로는 DB에 저장되어야 하지만, 여기서는 메모리에 저장
        self.user_coupons: Dict[int, List[Dict]] = {}
        
    def issue_coupon(self, user_id: int, coupon_id: str, issued_at: Optional[str] = None) -> bool:
        """사용자에게 쿠폰 발급"""
        if user_id not in self.user_coupons:
            self.user_coupons[user_id] = []
            
        # 중복 발급 확인
        for uc in self.user_coupons[user_id]:
            if uc['coupon_id'] == coupon_id and uc['status'] == 'ACTIVE':
                return False
                
        self.user_coupons[user_id].append({
            'coupon_id': coupon_id,
            'issued_at': issued_at or datetime.now().isoformat(),
            'used_at': None,
            'status': 'ACTIVE'
        })
        
        logger.info(f"쿠폰 발급: user_id={user_id}, coupon_id={coupon_id}")
        return True
        
    def use_coupon(self, user_id: int, coupon_id: str) -> bool:
        """쿠폰 사용 처리"""
        if user_id not in self.user_coupons:
            return False
            
        for uc in self.user_coupons[user_id]:
            if uc['coupon_id'] == coupon_id and uc['status'] == 'ACTIVE':
                uc['used_at'] = datetime.now().isoformat()
                uc['status'] = 'USED'
                logger.info(f"쿠폰 사용: user_id={user_id}, coupon_id={coupon_id}")
                return True
                
        return False
        
    def get_user_coupons(self, user_id: int, status: str = 'ACTIVE') -> List[str]:
        """사용자의 쿠폰 목록 조회"""
        if user_id not in self.user_coupons:
            return []
            
        return [
            uc['coupon_id'] 
            for uc in self.user_coupons[user_id] 
            if uc['status'] == status
        ]