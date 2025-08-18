"""
RAG 시스템의 핵심 Retriever

QueryStructurizer, VectorStore, Documents를 통합하여
사용자 질문에 대한 관련 문서를 검색하는 메인 컴포넌트
"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from .documents import Document, ShopDocument, MenuDocument
from .vector_stores import VectorStore, create_vector_store
from .query_parser import QueryStructurizer, StructuredQuery
from src.utils.cache import get_query_cache, cached_result

logger = logging.getLogger(__name__)


class NaviyamRetriever:
    """나비얌 RAG 시스템의 메인 Retriever 클래스"""
    
    def __init__(self, 
                 vector_store: VectorStore,
                 query_structurizer: QueryStructurizer,
                 top_k: int = 5):
        """
        Args:
            vector_store: Vector DB 구현체
            query_structurizer: 쿼리 구조화기
            top_k: 검색할 문서 수
        """
        self.vector_store = vector_store
        self.query_structurizer = query_structurizer
        self.top_k = top_k
        self.cache = get_query_cache()
        logger.info(f"NaviyamRetriever initialized (top_k={top_k}, cache enabled)")
    
    def add_knowledge_base(self, knowledge_data: Dict[str, Any]):
        """지식 베이스 데이터를 Vector Store에 추가
        
        Args:
            knowledge_data: naviyam_knowledge.json 형태의 데이터
        """
        documents = []
        
        # 가게 정보 처리
        shops_data = knowledge_data.get('shops', {})
        menus_data = knowledge_data.get('menus', {})
        
        # ShopDocument 생성
        for shop_id, shop_info in shops_data.items():
            doc = ShopDocument(shop_info)
            documents.append(doc)
        
        # MenuDocument 생성 (가게 정보와 함께)
        for menu_id, menu_info in menus_data.items():
            shop_id = str(menu_info.get('shop_id'))
            shop_info = shops_data.get(shop_id, {})
            doc = MenuDocument(menu_info, shop_info)
            documents.append(doc)
        
        # Vector Store에 추가
        self.vector_store.add_documents(documents)
        logger.info(f"지식 베이스 추가 완료: {len(documents)}개 문서")
    
    async def search_async(self, user_query: str) -> List[Document]:
        """비동기 문서 검색 (I/O 작업 최적화)"""
        loop = asyncio.get_event_loop()
        
        # CPU 바운드 작업은 스레드풀에서 실행
        with ThreadPoolExecutor(max_workers=2) as executor:
            # 1. 쿼리 구조화와 임베딩을 병렬로 실행
            structured_query_future = loop.run_in_executor(
                executor, self.query_structurizer.parse_query, user_query
            )
            
            structured_query = await structured_query_future
            
            # 2. 임베딩 생성 (있는 경우)
            if hasattr(self.vector_store, 'encode_query'):
                query_embedding_future = loop.run_in_executor(
                    executor, self.vector_store.encode_query, structured_query.semantic_query
                )
                query_embedding = await query_embedding_future
            else:
                query_embedding = [0.1] * 384
            
            # 3. Vector Store 검색
            filters = structured_query.filters.model_dump(exclude_none=True)
            doc_ids_future = loop.run_in_executor(
                executor, self.vector_store.search,
                query_embedding, self.top_k, filters
            )
            doc_ids = await doc_ids_future
            
            # 4. Document 객체 반환
            documents_future = loop.run_in_executor(
                executor, self.vector_store.get_documents_by_ids, doc_ids
            )
            documents = await documents_future
            
            logger.info(f"비동기 검색 완료: {len(documents)}개 문서 반환")
            return documents
    
    def search(self, user_query: str) -> List[Document]:
        """사용자 질문에 대한 관련 문서 검색 (개선된 버전)
        
        1. 전체 쿼리로 의미 검색 우선
        2. 후처리로 필터 적용
        
        Args:
            user_query: 사용자의 자연어 질문
            
        Returns:
            관련도 높은 Document 리스트
        """
        logger.info(f"개선된 RAG 검색 시작: '{user_query}'")
        
        # 1. 자연어 질문을 구조화된 쿼리로 변환 (필터 추출용)
        structured_query = self.query_structurizer.parse_query(user_query)
        filters = structured_query.filters.model_dump(exclude_none=True)
        logger.info(f"추출된 필터: {filters}")
        
        # 2. FAISS 벡터 검색 (필터 없이 전체 쿼리로)
        if hasattr(self.vector_store, 'encode_query'):
            # 중요: 전체 쿼리를 사용하여 의미 검색 
            query_embedding = self.vector_store.encode_query(user_query)  # user_query 사용!
        else:
            query_embedding = [0.1] * 384
        
        # 필터 없이 의미 검색으로 충분한 후보 확보
        initial_top_k = min(self.top_k * 5, 50)  # 최대 50개 후보
        doc_ids = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=initial_top_k,
            filters={}  # 필터 비활성화 - 순수 의미 검색
        )
        
        initial_documents = self.vector_store.get_documents_by_ids(doc_ids)
        logger.info(f"1차 의미 검색: {len(initial_documents)}개 후보 확보")
        
        if not initial_documents:
            return []
        
        # 3. 후처리 필터링 (메모리에서)
        final_results = []
        location_filter = filters.get('location')
        category_filter = filters.get('category')
        
        logger.info(f"후처리 필터 - location: '{location_filter}', category: '{category_filter}'")
        
        # 디버깅: 첫 문서 타입 확인
        if initial_documents:
            logger.info(f"문서 타입: {type(initial_documents[0])}, hasattr(get_metadata): {hasattr(initial_documents[0], 'get_metadata')}")
        
        for doc in initial_documents:
            metadata = doc.get_metadata() if hasattr(doc, 'get_metadata') else {}
            is_match = True
            
            # 디버깅: 메타데이터 내용 확인 (첫 5개만)
            if len(final_results) < 5:
                logger.debug(f"Doc metadata: {metadata}")
            
            # 위치 필터
            if location_filter:
                doc_location = metadata.get('address', '') or metadata.get('shop_address', '')
                # 디버깅: 위치 필터링 상세 로그
                if len(final_results) < 3:
                    logger.info(f"위치 필터: '{location_filter}' in '{doc_location[:50]}...' = {location_filter in doc_location}")
                if location_filter not in doc_location:
                    is_match = False
            
            # 카테고리 필터
            if category_filter and is_match:
                doc_category = metadata.get('category', '')
                if category_filter.lower() not in doc_category.lower():
                    # 유사 카테고리도 허용
                    similar_cats = {
                        '피자': ['양식', '이탈리안'],
                        '햄버거': ['패스트푸드', '버거'],
                        '치킨': ['닭', '통닭']
                    }
                    if category_filter in similar_cats:
                        if not any(cat in doc_category for cat in similar_cats[category_filter]):
                            is_match = False
                    else:
                        is_match = False
            
            if is_match:
                final_results.append(doc)
                if location_filter and len(final_results) <= 3:
                    logger.info(f"✓ 통과: {metadata.get('name', 'unknown')} - {metadata.get('address', 'no address')[:50]}")
        
        logger.info(f"후처리 필터링: {len(initial_documents)}개 → {len(final_results)}개")
        return final_results[:self.top_k]
    
    def search_with_filters(self, semantic_query: str, filters: Dict) -> List[Document]:
        """구조화된 필터를 사용한 직접 검색
        
        Args:
            semantic_query: 순수한 의미 검색어 (예: "맛집 추천")
            filters: NLU에서 추출한 필터 (예: {'location': '강남', 'category': 'chicken'})
            
        Returns:
            필터링된 Document 리스트
        """
        # 실제 임베딩 생성 또는 더미 벡터
        if hasattr(self.vector_store, 'encode_query'):
            query_embedding = self.vector_store.encode_query(semantic_query)
        else:
            query_embedding = [0.1] * 384  # 임시 embedding
        
        # 직접 필터 전달하여 검색
        doc_ids = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=self.top_k,
            filters=filters
        )
        
        documents = self.vector_store.get_documents_by_ids(doc_ids)
        logger.info(f"구조화 검색 완료: semantic_query='{semantic_query}', filters={filters}, 결과={len(documents)}개")
        
        return documents
    
    def get_context_for_llm(self, user_query: str) -> str:
        """LLM에게 전달할 컨텍스트 생성
        
        Args:
            user_query: 사용자 질문
            
        Returns:
            LLM용 컨텍스트 문자열
        """
        documents = self.search(user_query)
        
        if not documents:
            return "관련된 가게나 메뉴 정보를 찾을 수 없습니다."
        
        context_parts = ["다음은 관련된 가게 및 메뉴 정보입니다:"]
        
        for i, doc in enumerate(documents, 1):
            context_parts.append(f"\n{i}. {doc.get_content()}")
        
        return "\n".join(context_parts)


def load_knowledge_from_file(file_path: str) -> Dict[str, Any]:
    """파일에서 지식 베이스 로드
    
    Args:
        file_path: naviyam_knowledge.json 파일 경로
        
    Returns:
        지식 베이스 데이터
        
    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
        json.JSONDecodeError: JSON 형식이 잘못되었을 때
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.info(f"지식 베이스 로드 성공: {file_path}")
            return data
    except FileNotFoundError:
        logger.error(f"지식 베이스 파일을 찾을 수 없습니다: {file_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"지식 베이스 파일의 JSON 형식이 잘못되었습니다: {e}")
        logger.error(f"파일 위치: {file_path}, 라인: {e.lineno}, 컬럼: {e.colno}")
        raise
    except PermissionError:
        logger.error(f"지식 베이스 파일 읽기 권한이 없습니다: {file_path}")
        raise
    except Exception as e:
        logger.error(f"지식 베이스 로드 중 예상치 못한 오류: {type(e).__name__}: {e}")
        raise


def create_naviyam_retriever(knowledge_file_path: str,
                           vector_store_type: str = "mock",
                           llm_client=None,
                           config=None) -> NaviyamRetriever:
    """NaviyamRetriever 팩토리 함수
    
    Args:
        knowledge_file_path: 지식 베이스 파일 경로
        vector_store_type: Vector Store 타입 ("mock", "faiss", etc.)
        llm_client: LLM 클라이언트 (선택사항)
        config: AppConfig 객체 (선택사항)
        
    Returns:
        설정된 NaviyamRetriever 인스턴스
    """
    # PathConfig 가져오기
    from utils.config import PathConfig
    path_config = config.paths if config and hasattr(config, 'paths') else PathConfig()
    
    # Vector Store 생성
    if vector_store_type == "prebuilt_faiss":
        vector_store = create_vector_store(
            store_type=vector_store_type,
            index_path=str(path_config.PREBUILT_FAISS_INDEX),
            metadata_path=str(path_config.PREBUILT_FAISS_METADATA)
        )
    else:
        vector_store = create_vector_store(
            store_type=vector_store_type,
            storage_path=str(path_config.OUTPUT_DIR / "rag_debug.json")
        )
    
    # Query Structurizer 생성
    query_structurizer = QueryStructurizer(llm_client)
    
    # Retriever 생성
    retriever = NaviyamRetriever(vector_store, query_structurizer)
    
    # 지식 베이스 로드 및 추가 (PrebuiltFAISS는 이미 로드됨)
    if vector_store_type != "prebuilt_faiss":
        knowledge_data = load_knowledge_from_file(knowledge_file_path)
        if knowledge_data:
            retriever.add_knowledge_base(knowledge_data)
    else:
        logger.info("PrebuiltFAISS 사용: 지식 베이스 이미 로드됨")
    
    return retriever


# 테스트용 함수
def test_retriever():
    """Retriever 테스트"""
    from utils.config import PathConfig
    path_config = PathConfig()
    knowledge_file = str(path_config.RAG_DATA_FILE)
    
    # Retriever 생성
    retriever = create_naviyam_retriever(knowledge_file, "mock")
    
    # 테스트 질문들
    test_queries = [
        "치킨 맛집 추천해줘",
        "2만원 이하 가게 찾아줘",
        "강남에 있는 착한가게",
        "인기 메뉴 있는 곳"
    ]
    
    for query in test_queries:
        print(f"\n=== 질문: {query} ===")
        
        # 검색 결과
        documents = retriever.search(query)
        print(f"검색된 문서 수: {len(documents)}")
        
        for i, doc in enumerate(documents, 1):
            print(f"{i}. [{doc.get_metadata()['type']}] {doc.get_content()[:100]}...")
        
        # LLM용 컨텍스트
        context = retriever.get_context_for_llm(query)
        print(f"\nLLM 컨텍스트 길이: {len(context)} 문자")


if __name__ == "__main__":
    test_retriever()