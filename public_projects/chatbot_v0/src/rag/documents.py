"""
RAG 시스템용 Document 추상화 레이어

모든 데이터 타입(shops, menus, reviews 등)을 일관된 방식으로 처리하기 위한
Document 인터페이스와 구현체들
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class Document(ABC):
    """RAG 시스템에서 검색 및 참조되는 모든 데이터의 추상 기본 클래스"""
    
    @property
    @abstractmethod
    def id(self) -> str:
        """데이터를 고유하게 식별하는 ID"""
        pass

    @abstractmethod
    def get_content(self) -> str:
        """Vector Embedding을 위해 사용될 텍스트 콘텐츠를 반환합니다.
        LLM이 의미를 잘 파악할 수 있도록 중요한 정보들을 자연어 문장으로 조합합니다.
        """
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """검색 시 필터링에 사용될 메타데이터를 반환합니다.
        'type' 필드를 포함하여 데이터 종류를 명시하는 것이 좋습니다.
        """
        pass


class ShopDocument(Document):
    """가게 정보 Document"""
    
    def __init__(self, shop_data: Dict[str, Any]):
        self._data = shop_data

    @property
    def id(self) -> str:
        return f"shop_{self._data['id']}"

    def get_content(self) -> str:
        """LLM이 가게 정보를 가장 잘 이해할 수 있는 형태로 가공"""
        content_parts = [
            f"가게 이름: {self._data['name']}",
            f"카테고리: {self._data['category']}",
            f"주소: {self._data['address']}"
        ]
        
        # 운영시간 정보
        if self._data.get('open_hour') and self._data.get('close_hour'):
            content_parts.append(f"운영시간: {self._data['open_hour']} - {self._data['close_hour']}")
        
        # 사장님 한마디
        if self._data.get('owner_message'):
            content_parts.append(f"사장님 한마디: {self._data['owner_message']}")
        
        # 착한가게 여부
        if self._data.get('is_good_influence_shop'):
            content_parts.append("착한가게 인증")
        
        return ". ".join(content_parts) + "."

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "type": "shop",
            "name": self._data['name'],
            "category": self._data['category'],
            "address": self._data['address'],
            "is_good_influence": self._data.get('is_good_influence_shop', False),
            "is_food_card_shop": self._data.get('is_food_card_shop') == "Y",
            "ordinary_discount": self._data.get('ordinary_discount', False)
        }


class MenuDocument(Document):
    """메뉴 정보 Document"""
    
    def __init__(self, menu_data: Dict[str, Any], shop_info: Dict[str, Any] = None):
        self._data = menu_data
        self._shop_info = shop_info or {}

    @property
    def id(self) -> str:
        return f"menu_{self._data['id']}"

    def get_content(self) -> str:
        """메뉴는 가게 정보와 함께 있어야 의미가 풍부해짐"""
        content_parts = []
        
        # 가게 정보가 있으면 포함
        if self._shop_info.get('name'):
            content_parts.append(f"{self._shop_info['name']}의 메뉴")
        
        content_parts.extend([
            f"메뉴명: {self._data['name']}",
            f"가격: {self._data['price']}원"
        ])
        
        # 메뉴 설명
        if self._data.get('description'):
            content_parts.append(f"설명: {self._data['description']}")
        
        # 카테고리 정보
        if self._data.get('category'):
            content_parts.append(f"카테고리: {self._data['category']}")
        
        # 인기 메뉴 여부
        if self._data.get('is_popular'):
            content_parts.append("인기 메뉴")
        
        return ". ".join(content_parts) + "."

    def get_metadata(self) -> Dict[str, Any]:
        metadata = {
            "type": "menu",
            "shop_id": self._data['shop_id'],
            "name": self._data['name'],
            "price": self._data['price'],
            "is_popular": self._data.get('is_popular', False)
        }
        
        # 메뉴 카테고리
        if self._data.get('category'):
            metadata['category'] = self._data['category']
        
        # 가게 정보가 있으면 추가
        if self._shop_info:
            metadata['shop_name'] = self._shop_info.get('name')
            metadata['shop_category'] = self._shop_info.get('category')
            metadata['shop_address'] = self._shop_info.get('address')
        
        return metadata


class ReviewDocument(Document):
    """리뷰 정보 Document (향후 확장용)"""
    
    def __init__(self, review_data: Dict[str, Any], shop_info: Dict[str, Any] = None):
        self._data = review_data
        self._shop_info = shop_info or {}

    @property
    def id(self) -> str:
        return f"review_{self._data['id']}"

    def get_content(self) -> str:
        content_parts = []
        
        if self._shop_info.get('name'):
            content_parts.append(f"{self._shop_info['name']} 리뷰")
        
        content_parts.extend([
            f"평점: {self._data.get('rating', 0)}점",
            f"리뷰 내용: {self._data.get('content', '')}"
        ])
        
        if self._data.get('reviewer'):
            content_parts.append(f"작성자: {self._data['reviewer']}")
        
        return ". ".join(content_parts) + "."

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "type": "review",
            "shop_id": self._data.get('shop_id'),
            "rating": self._data.get('rating', 0),
            "reviewer": self._data.get('reviewer'),
            "shop_name": self._shop_info.get('name')
        }


class CouponDocument(Document):
    """쿠폰 정보 Document (향후 확장용)"""
    
    def __init__(self, coupon_data: Dict[str, Any], shop_info: Dict[str, Any] = None):
        self._data = coupon_data
        self._shop_info = shop_info or {}

    @property
    def id(self) -> str:
        return f"coupon_{self._data['id']}"

    def get_content(self) -> str:
        content_parts = []
        
        if self._shop_info.get('name'):
            content_parts.append(f"{self._shop_info['name']} 쿠폰")
        
        content_parts.extend([
            f"쿠폰명: {self._data['name']}",
            f"할인 내용: {self._data.get('description', '')}"
        ])
        
        if self._data.get('discount_amount'):
            content_parts.append(f"할인 금액: {self._data['discount_amount']}원")
        
        if self._data.get('discount_rate'):
            content_parts.append(f"할인율: {self._data['discount_rate']}%")
        
        return ". ".join(content_parts) + "."

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "type": "coupon",
            "shop_id": self._data.get('shop_id'),
            "discount_amount": self._data.get('discount_amount'),
            "discount_rate": self._data.get('discount_rate'),
            "shop_name": self._shop_info.get('name')
        }