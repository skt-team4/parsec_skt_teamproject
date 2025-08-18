"""
LLM 기반 쿼리 구조화 시스템

사용자의 자연어 질문을 의미 검색(semantic_query)과 
메타데이터 필터링(filters)으로 분리하는 QueryStructurizer
"""

import json
import logging
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SearchFilters(BaseModel):
    """검색 필터 조건"""
    category: Optional[str] = Field(None, description="음식 카테고리 (예: 치킨, 한식)")
    max_price: Optional[int] = Field(None, description="최대 예산 (숫자만)")
    min_price: Optional[int] = Field(None, description="최소 예산 (숫자만)")
    location: Optional[str] = Field(None, description="검색할 지역 (예: 강남역, 홍대)")
    is_popular: Optional[bool] = Field(None, description="인기 메뉴 여부")
    is_good_influence: Optional[bool] = Field(None, description="착한가게 여부")
    type: Optional[str] = Field(None, description="검색할 데이터 타입 (shop, menu, review)")


class StructuredQuery(BaseModel):
    """구조화된 검색 쿼리"""
    semantic_query: str = Field(..., description="Vector DB에서 유사도 검색에 사용할 핵심 검색어")
    filters: SearchFilters = Field(default_factory=SearchFilters, description="검색 결과를 필터링할 조건")


class QueryStructurizer:
    """자연어 질문을 구조화된 검색 쿼리로 변환하는 클래스"""
    
    PROMPT_TEMPLATE = """
당신은 사용자 질문을 분석하여 JSON 형식의 검색 쿼리로 변환하는 전문가입니다.
사용자 질문을 기반으로, 의미 검색에 사용할 'semantic_query'와 필터링에 사용할 'filters'를 추출해주세요.

사용 가능한 필터:
- category: 음식 카테고리 (치킨, 한식, 중식, 일식, 양식, 분식, 카페, 디저트 등)
- max_price: 최대 예산 (숫자만, 원 단위)
- min_price: 최소 예산 (숫자만, 원 단위)
- location: 지역 (강남역, 홍대, 명동 등)
- is_popular: 인기 메뉴 여부 (true/false)
- is_good_influence: 착한가게 여부 (true/false)
- type: 검색 데이터 타입 (shop, menu, review)

규칙:
1. 질문에 명시되지 않은 필터는 포함하지 마세요
2. semantic_query는 핵심 검색 의도만 포함하세요
3. 가격은 "만원", "천원" 등을 숫자로 변환하세요
4. JSON 형식으로만 응답하세요

사용자 질문: "{user_query}"

JSON 출력:
"""
    
    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: LLM 클라이언트 (예: KoAlpacaModel 인스턴스)
        """
        self.llm = llm_client
        logger.info("QueryStructurizer initialized")
    
    def parse_query(self, user_query: str) -> StructuredQuery:
        """사용자 질문을 구조화된 쿼리로 변환
        
        Args:
            user_query: 사용자의 자연어 질문
            
        Returns:
            StructuredQuery: 구조화된 검색 쿼리
        """
        if self.llm:
            # 실제 LLM을 사용한 파싱
            return self._parse_with_llm(user_query)
        else:
            # LLM이 없을 때 규칙 기반 파싱
            return self._parse_with_rules(user_query)
    
    def _parse_with_llm(self, user_query: str) -> StructuredQuery:
        """LLM을 사용한 쿼리 파싱"""
        try:
            prompt = self.PROMPT_TEMPLATE.format(user_query=user_query)
            
            # LLM 호출 (실제 구현에서는 self.llm.generate() 등 사용)
            # llm_output_json = self.llm.generate(prompt)
            
            # 임시로 규칙 기반 결과 반환 (LLM 연동 전까지)
            logger.warning("LLM 연동 전까지 규칙 기반 파싱 사용")
            return self._parse_with_rules(user_query)
            
        except Exception as e:
            logger.error(f"LLM 파싱 실패: {e}, 규칙 기반 파싱으로 대체")
            return self._parse_with_rules(user_query)
    
    def _parse_with_rules(self, user_query: str) -> StructuredQuery:
        """규칙 기반 쿼리 파싱 (LLM 백업용)"""
        query_lower = user_query.lower()
        
        # 기본 semantic_query
        semantic_query = user_query
        filters = SearchFilters()
        
        # 카테고리 감지
        category_keywords = {
            '치킨': ['치킨', '닭', '후라이드', '양념'],
            '한식': ['한식', '한국', '김치', '불고기', '비빔밥'],
            '중식': ['중식', '중국', '짜장', '짬뽕', '탕수육'],
            '일식': ['일식', '일본', '스시', '라멘', '돈카츠'],
            '양식': ['양식', '서양', '파스타', '피자', '스테이크'],
            '분식': ['분식', '떡볶이', '순대', '튀김', '김밥'],
            '카페': ['카페', '커피', '음료', '디저트'],
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                filters.category = category
                break
        
        # 가격 감지
        price_patterns = [
            ('만원', 10000), ('천원', 1000), ('원', 1)
        ]
        
        for pattern, multiplier in price_patterns:
            if pattern in query_lower:
                # "2만원 이하", "5천원 미만" 등 패턴 감지
                import re
                price_match = re.search(r'(\d+)\s*' + pattern + r'\s*(이하|미만|아래)', query_lower)
                if price_match:
                    price = int(price_match.group(1)) * multiplier
                    filters.max_price = price
                    break
                
                # "1만원 이상", "5천원 넘는" 등 패턴 감지
                price_match = re.search(r'(\d+)\s*' + pattern + r'\s*(이상|넘는|초과)', query_lower)
                if price_match:
                    price = int(price_match.group(1)) * multiplier
                    filters.min_price = price
                    break
        
        # 지역 감지
        location_keywords = ['강남', '홍대', '명동', '역삼', '신촌', '이태원', '가로수길']
        for location in location_keywords:
            if location in query_lower:
                filters.location = location
                break
        
        # 인기/착한가게 감지
        if any(keyword in query_lower for keyword in ['인기', '유명', '핫한', '인기있는']):
            filters.is_popular = True
        
        if any(keyword in query_lower for keyword in ['착한가게', '착한', '할인']):
            filters.is_good_influence = True
        
        # 검색 타입 감지
        if any(keyword in query_lower for keyword in ['메뉴', '음식', '요리']):
            filters.type = 'menu'
        elif any(keyword in query_lower for keyword in ['가게', '식당', '맛집']):
            filters.type = 'shop'
        elif any(keyword in query_lower for keyword in ['리뷰', '후기', '평가']):
            filters.type = 'review'
        
        # 핵심 검색 의도 추출 (의미 보존)
        intent_keywords = {
            "맛집": "맛집 추천",
            "음식": "음식 추천",
            "메뉴": "메뉴 정보",
            "가게": "식당 정보",
            "식당": "식당 정보",
            "추천": "추천",
            "먹": "음식 추천"
        }
        
        # 기본 semantic query 설정
        semantic_query = "맛집 추천"  # 기본값
        
        # 사용자 쿼리에서 핵심 의도 찾기
        for keyword, intent in intent_keywords.items():
            if keyword in query_lower:
                semantic_query = intent
                break
        
        # 특수한 경우 처리
        if "얼마" in query_lower or "가격" in query_lower:
            semantic_query = "가격 정보"
        elif "위치" in query_lower or "어디" in query_lower:
            semantic_query = "위치 정보"
        elif "뭐" in query_lower and "먹" in query_lower:
            semantic_query = "음식 추천"
        
        logger.info(f"규칙 기반 파싱 결과 - 쿼리: '{semantic_query}', 필터: {filters.model_dump(exclude_none=True)}")
        
        return StructuredQuery(
            semantic_query=semantic_query,
            filters=filters
        )


# 사용 예시를 위한 헬퍼 함수
def create_query_structurizer(llm_client=None) -> QueryStructurizer:
    """QueryStructurizer 팩토리 함수
    
    Args:
        llm_client: LLM 클라이언트 (선택사항)
        
    Returns:
        QueryStructurizer 인스턴스
    """
    return QueryStructurizer(llm_client)


# 테스트용 함수들
def test_query_parsing():
    """쿼리 파싱 테스트"""
    structurizer = create_query_structurizer()
    
    test_queries = [
        "강남역 근처에 2만원 이하 치킨 맛집 추천해줘",
        "홍대에서 인기 있는 한식 가게 찾아줘",
        "1만원 이상 파스타 메뉴 있는 착한가게",
        "명동 카페 추천"
    ]
    
    for query in test_queries:
        print(f"\n쿼리: {query}")
        result = structurizer.parse_query(query)
        print(f"Semantic: {result.semantic_query}")
        print(f"Filters: {result.filters.model_dump(exclude_none=True)}")


if __name__ == "__main__":
    test_query_parsing()