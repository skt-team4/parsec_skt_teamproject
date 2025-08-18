"""
Vector DB 추상화 레이어

FAISS, ChromaDB, Pinecone 등 어떤 Vector DB를 사용하더라도 
동일한 인터페이스로 제어할 수 있도록 추상화
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json
import logging
import numpy as np
from pathlib import Path

from .documents import Document

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """Vector DB를 위한 추상 인터페이스"""

    @abstractmethod
    def add_documents(self, documents: List[Document]):
        """Document 목록을 받아 embedding하고 vector db에 추가합니다"""
        pass

    @abstractmethod
    def search(self, query_embedding: List[float], top_k: int = 10, 
               filters: Optional[Dict[str, Any]] = None) -> List[str]:
        """쿼리 embedding과 필터를 사용하여 유사도 높은 document ID 목록을 반환합니다"""
        pass

    @abstractmethod
    def get_documents_by_ids(self, doc_ids: List[str]) -> List[Document]:
        """Document ID 목록으로 실제 Document 객체들을 반환합니다"""
        pass

    @abstractmethod
    def clear(self):
        """모든 데이터를 삭제합니다"""
        pass


class MockVectorStore(VectorStore):
    """개발 및 테스트용 Mock Vector Store
    
    실제 Vector DB 없이 기본적인 키워드 매칭으로 동작하여
    RAG 시스템의 전체 흐름을 테스트할 수 있습니다.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.documents: Dict[str, Document] = {}
        self.storage_path = storage_path
        logger.info("MockVectorStore initialized")
    
    def add_documents(self, documents: List[Document]):
        """Document들을 메모리에 저장"""
        for doc in documents:
            self.documents[doc.id] = doc
        
        logger.info(f"{len(documents)}개의 문서를 MockVectorStore에 추가했습니다")
        
        # 파일에 저장 (선택사항)
        if self.storage_path:
            self._save_to_file()
    
    def search(self, query_embedding: List[float], top_k: int = 10, 
               filters: Optional[Dict[str, Any]] = None) -> List[str]:
        """간단한 키워드 매칭으로 검색 시뮬레이션"""
        # 실제로는 query_embedding을 사용하지만, 
        # Mock에서는 filters만 사용하여 검색
        
        matching_docs = []
        
        for doc_id, doc in self.documents.items():
            metadata = doc.get_metadata()
            
            # 필터 조건 확인
            if filters:
                match = True
                for key, value in filters.items():
                    if key == 'type' and metadata.get('type') != value:
                        match = False
                        break
                    elif key == 'category' and metadata.get('category') != value:
                        match = False
                        break
                    elif key == 'max_price' and metadata.get('price', 0) > value:
                        match = False
                        break
                    elif key == 'is_popular' and metadata.get('is_popular') != value:
                        match = False
                        break
                
                if match:
                    matching_docs.append(doc_id)
            else:
                matching_docs.append(doc_id)
        
        # top_k 제한
        result = matching_docs[:top_k]
        logger.info(f"MockVectorStore 검색 결과: {len(result)}개 문서 (필터: {filters})")
        
        return result
    
    def get_documents_by_ids(self, doc_ids: List[str]) -> List[Document]:
        """ID로 Document 객체들 반환"""
        documents = []
        for doc_id in doc_ids:
            if doc_id in self.documents:
                documents.append(self.documents[doc_id])
        
        return documents
    
    def clear(self):
        """모든 데이터 삭제"""
        self.documents.clear()
        logger.info("MockVectorStore 데이터를 모두 삭제했습니다")
    
    def _save_to_file(self):
        """Document 메타데이터를 파일에 저장 (디버깅용)"""
        if not self.storage_path:
            return
        
        data = {}
        for doc_id, doc in self.documents.items():
            data[doc_id] = {
                'content': doc.get_content(),
                'metadata': doc.get_metadata()
            }
        
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class PrebuiltFAISSVectorStore(VectorStore):
    """사전 빌드된 FAISS 인덱스를 로드하는 최적화된 Vector Store
    
    초기화 시간을 대폭 단축하기 위해 미리 생성된 FAISS 인덱스와 
    메타데이터를 로드합니다. 임베딩 모델은 쿼리 처리 시에만 사용됩니다.
    """
    
    def __init__(self, index_path: str, metadata_path: str = None, embedding_model=None):
        """
        Args:
            index_path: 사전 빌드된 FAISS 인덱스 파일 경로 (.faiss)
            metadata_path: 메타데이터 파일 경로 (.json). None이면 자동 추론
            embedding_model: 쿼리 임베딩용 모델. None이면 필요시 로드
        """
        try:
            # FAISS GPU 버전 시도
            try:
                import faiss
                if hasattr(faiss, 'get_num_gpus') and faiss.get_num_gpus() > 0:
                    logger.info(f"FAISS GPU 버전 감지됨. GPU 개수: {faiss.get_num_gpus()}")
                    self.use_gpu = True
                else:
                    logger.info("FAISS CPU 버전 사용")
                    self.use_gpu = False
            except ImportError:
                # faiss-gpu가 없으면 faiss-cpu 시도
                logger.info("FAISS GPU 버전이 없습니다. CPU 버전을 사용합니다.")
                import faiss
                self.use_gpu = False
            
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            logger.error(f"FAISS 또는 sentence-transformers 라이브러리가 필요합니다: {e}")
            raise ImportError("pip install faiss-cpu sentence-transformers")
        
        self.index_path = index_path
        self.metadata_path = metadata_path or index_path.replace('.faiss', '_metadata.json')
        self.embedding_model = embedding_model
        
        # 데이터 저장소 초기화
        self.index = None
        self.metadata_info = {}
        self.embedding_dim = 384  # 기본값
        self.embedding_model_name = "all-MiniLM-L6-v2"  # 기본값
        
        # 빠른 초기화 - 인덱스와 메타데이터만 로드
        self._load_prebuilt_index()
        
        logger.info(f"PrebuiltFAISSVectorStore 초기화 완료: {self.index.ntotal}개 문서")
    
    def _load_prebuilt_index(self):
        """사전 빌드된 FAISS 인덱스와 메타데이터 로드"""
        import faiss
        
        # 1. FAISS 인덱스 로드
        if not Path(self.index_path).exists():
            raise FileNotFoundError(f"FAISS 인덱스 파일을 찾을 수 없습니다: {self.index_path}")
        
        logger.info(f"FAISS 인덱스 로드: {self.index_path}")
        
        # Windows에서 한글 경로 문제 해결을 위해 임시 파일로 복사
        try:
            self.index = faiss.read_index(str(self.index_path))
        except Exception as e:
            logger.warning(f"FAISS 로드 실패 ({e}), 임시 파일로 시도...")
            import tempfile
            import shutil
            
            # 임시 파일로 복사
            with tempfile.NamedTemporaryFile(delete=False, suffix='.faiss') as tmp:
                tmp_path = tmp.name
            
            shutil.copy2(str(self.index_path), tmp_path)
            
            try:
                self.index = faiss.read_index(tmp_path)
                logger.info("임시 파일로 FAISS 로드 성공")
            finally:
                # 임시 파일 삭제
                import os
                try:
                    os.unlink(tmp_path)
                except:
                    pass
        
        # 2. 메타데이터 로드
        if not Path(self.metadata_path).exists():
            raise FileNotFoundError(f"메타데이터 파일을 찾을 수 없습니다: {self.metadata_path}")
        
        logger.info(f"메타데이터 로드: {self.metadata_path}")
        with open(self.metadata_path, 'r', encoding='utf-8') as f:
            self.metadata_info = json.load(f)
        
        # 3. 설정 정보 업데이트
        index_info = self.metadata_info.get('index_info', {})
        self.embedding_dim = index_info.get('embedding_dimension', 384)
        self.embedding_model_name = index_info.get('embedding_model', 'all-MiniLM-L6-v2')
        
        logger.info(f"로드 완료: {self.index.ntotal}개 문서, {self.embedding_dim}차원")
    
    def _ensure_embedding_model(self):
        """필요시 임베딩 모델 로드 (Lazy Loading)"""
        if self.embedding_model is None:
            logger.info(f"임베딩 모델 로드: {self.embedding_model_name}")
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
        return self.embedding_model
    
    def add_documents(self, documents: List[Document]):
        """사전 빌드된 인덱스는 추가 불가"""
        raise NotImplementedError("PrebuiltFAISSVectorStore는 문서 추가를 지원하지 않습니다. build_faiss_index.py를 사용하여 인덱스를 재빌드하세요.")
    
    def search(self, query_embedding: List[float], top_k: int = 10, 
               filters: Optional[Dict[str, Any]] = None) -> List[str]:
        """빠른 유사도 검색"""
        if self.index.ntotal == 0:
            logger.warning("인덱스가 비어있습니다")
            return []
        
        try:
            # 1. 쿼리 임베딩 준비
            if isinstance(query_embedding, list):
                query_vector = np.array(query_embedding, dtype='float32').reshape(1, -1)
            else:
                query_vector = query_embedding.astype('float32').reshape(1, -1)
            
            # 2. FAISS 검색
            search_k = min(top_k * 3, self.index.ntotal)
            distances, indices = self.index.search(query_vector, search_k)
            
            # 3. 결과 처리 및 필터링
            results = []
            # 실제 메타데이터 구조에 맞게 수정
            faiss_idx_to_doc_id = self.metadata_info.get('faiss_idx_to_doc_id', {})
            metadata_store = self.metadata_info.get('metadata_store', {})
            
            for distance, idx in zip(distances[0], indices[0]):
                if idx == -1:
                    continue
                
                # Document ID 찾기 (실제 구조에 맞게 수정)
                doc_id = faiss_idx_to_doc_id.get(str(idx))
                if not doc_id:
                    continue
                
                # 메타데이터 필터링 (실제 구조에 맞게 수정)
                if filters and str(idx) in metadata_store:
                    metadata = metadata_store[str(idx)]
                    if not self._match_filters(metadata, filters):
                        continue
                
                results.append(doc_id)
                
                if len(results) >= top_k:
                    break
            
            logger.debug(f"검색 완료: {len(results)}개 문서 반환")
            return results
            
        except Exception as e:
            logger.error(f"검색 실패: {e}")
            return []
    
    def _match_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """메타데이터 필터링"""
        for key, value in filters.items():
            if key == 'type' and metadata.get('type') != value:
                return False
            elif key == 'category' and metadata.get('category') != value:
                return False
            elif key == 'max_price' and metadata.get('price', 0) > value:
                return False
            elif key == 'min_price' and metadata.get('price', float('inf')) < value:
                return False
            elif key == 'is_popular' and metadata.get('is_popular') != value:
                return False
            elif key == 'is_good_influence' and metadata.get('is_good_influence') != value:
                return False
        return True
    
    def get_documents_by_ids(self, doc_ids: List[str]) -> List[Document]:
        """ID로 문서 내용 반환 (재구성)"""
        documents = []
        # 실제 메타데이터 구조에 맞게 수정
        metadata_store = self.metadata_info.get('metadata_store', {})
        doc_id_to_faiss_idx = self.metadata_info.get('doc_id_to_faiss_idx', {})
        
        from .documents import ShopDocument, MenuDocument
        
        for doc_id in doc_ids:
            # doc_id로 FAISS 인덱스 찾기
            faiss_idx = doc_id_to_faiss_idx.get(doc_id)
            if faiss_idx is None:
                continue
            
            # FAISS 인덱스로 메타데이터 찾기
            metadata = metadata_store.get(str(faiss_idx))
            if not metadata:
                continue
                
            doc_type = metadata.get('type', 'unknown')
            
            # 원본 Document 타입에 맞게 재구성
            try:
                if doc_type == 'shop' and doc_id.startswith('shop_'):
                    # ShopDocument 재구성 (메타데이터에서)
                    shop_info = {
                        'id': int(doc_id.replace('shop_', '')),
                        'name': metadata.get('name', ''),
                        'category': metadata.get('category', ''),
                        'address': metadata.get('address', ''),
                        'is_good_influence_shop': metadata.get('is_good_influence', False),
                        'is_food_card_shop': metadata.get('is_food_card_shop', 'N'),
                        'ordinary_discount': metadata.get('ordinary_discount', False),
                        'owner_message': metadata.get('owner_message', '')
                    }
                    doc = ShopDocument(shop_info)
                    documents.append(doc)
                    
                elif doc_type == 'menu' and doc_id.startswith('menu_'):
                    # MenuDocument 재구성 (메타데이터에서)
                    menu_info = {
                        'id': int(doc_id.replace('menu_', '').split('_')[0]) if '_' in doc_id else int(doc_id.replace('menu_', '')),
                        'shop_id': metadata.get('shop_id', 0),
                        'name': metadata.get('menu_name', metadata.get('name', '')),
                        'price': metadata.get('price', 0),
                        'description': metadata.get('description', ''),
                        'is_popular': metadata.get('is_popular', False)
                    }
                    shop_info = {
                        'name': metadata.get('shop_name', ''),
                        'category': metadata.get('category', '')
                    }
                    doc = MenuDocument(menu_info, shop_info)
                    documents.append(doc)
                    
                else:
                    # 알 수 없는 타입은 SimpleDocument로 처리
                    class SimpleDocument:
                        def __init__(self, doc_id, content, metadata):
                            self._id = doc_id
                            self._content = content
                            self._metadata = metadata
                        
                        @property
                        def id(self):
                            return self._id
                        
                        def get_content(self):
                            return self._content
                        
                        def get_metadata(self):
                            return self._metadata
                    
                    documents.append(SimpleDocument(doc_id, content, metadata))
                    
            except Exception as e:
                logger.warning(f"문서 재구성 실패 {doc_id}: {e}")
                # 실패 시 SimpleDocument로 대체
                class SimpleDocument:
                    def __init__(self, doc_id, content, metadata):
                        self._id = doc_id
                        self._content = content
                        self._metadata = metadata
                    
                    @property
                    def id(self):
                        return self._id
                    
                    def get_content(self):
                        return self._content
                    
                    def get_metadata(self):
                        return self._metadata
                
                documents.append(SimpleDocument(doc_id, content, metadata))
        
        return documents
    
    def clear(self):
        """사전 빌드된 인덱스는 삭제 불가"""
        raise NotImplementedError("PrebuiltFAISSVectorStore는 데이터 삭제를 지원하지 않습니다.")
    
    def encode_query(self, query_text: str) -> List[float]:
        """쿼리 텍스트를 임베딩으로 변환 (Lazy Loading)"""
        try:
            model = self._ensure_embedding_model()
            embedding = model.encode([query_text])
            return embedding[0].tolist()
        except Exception as e:
            logger.error(f"쿼리 임베딩 실패: {e}")
            return [0.0] * self.embedding_dim


class FAISSVectorStore(VectorStore):
    """FAISS 기반 Vector Store"""
    
    def __init__(self, embedding_model=None, index_path: Optional[str] = None, embedding_dim: int = 384):
        """
        Args:
            embedding_model: SentenceTransformer 모델 또는 None (기본값 사용)
            index_path: FAISS 인덱스 저장 경로
            embedding_dim: 임베딩 벡터 차원
        """
        try:
            # FAISS GPU 버전 시도
            try:
                import faiss
                if hasattr(faiss, 'get_num_gpus') and faiss.get_num_gpus() > 0:
                    logger.info(f"FAISS GPU 버전 감지됨. GPU 개수: {faiss.get_num_gpus()}")
                    self.use_gpu = True
                else:
                    logger.info("FAISS CPU 버전 사용")
                    self.use_gpu = False
            except ImportError:
                # faiss-gpu가 없으면 faiss-cpu 시도
                logger.info("FAISS GPU 버전이 없습니다. CPU 버전을 사용합니다.")
                import faiss
                self.use_gpu = False
            
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            logger.error(f"FAISS 또는 sentence-transformers 라이브러리가 필요합니다: {e}")
            raise ImportError("pip install faiss-cpu sentence-transformers")
        
        # 임베딩 모델 초기화
        if embedding_model is None:
            logger.info("기본 임베딩 모델 로드: all-MiniLM-L6-v2")
            try:
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
            except Exception as e:
                logger.warning(f"임베딩 모델 로드 실패: {e}, 다중 언어 모델 시도")
                self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        else:
            self.embedding_model = embedding_model
            self.embedding_dim = embedding_dim
        
        # FAISS 인덱스 초기화
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        
        # GPU 사용 시 GPU 인덱스로 변환
        if self.use_gpu:
            self._convert_to_gpu_index()
        
        self.index_path = index_path
        
        # 메타데이터 및 문서 저장소
        self.metadata_store: Dict[int, Dict] = {}  # {faiss_idx: metadata}
        self.documents: Dict[str, Document] = {}  # {doc_id: Document}
        self.doc_id_to_faiss_idx: Dict[str, int] = {}  # {doc_id: faiss_idx}
        self.faiss_idx_to_doc_id: Dict[int, str] = {}  # {faiss_idx: doc_id}
        
        # 인덱스 로드 시도
        if index_path and Path(index_path).exists():
            self._load_index()
        
        logger.info(f"FAISSVectorStore 초기화 완료 (차원: {self.embedding_dim})")
    
    def add_documents(self, documents: List[Document], replace: bool = False):
        """문서들을 임베딩하여 FAISS 인덱스에 추가
        
        Args:
            documents: 추가할 Document 리스트
            replace: True면 기존 데이터를 모두 삭제하고 새로 추가
        """
        if not documents:
            return
        
        # replace 모드일 때 기존 데이터 삭제
        if replace:
            logger.info("Replace 모드: 기존 데이터 삭제")
            self.clear()
        
        logger.info(f"{len(documents)}개의 문서를 FAISS에 추가 시작...")
        
        # 메모리 제한 체크 (최대 200,000개 문서로 증가)
        max_documents = 200000
        current_total = self.index.ntotal + len(documents)
        if current_total > max_documents:
            logger.warning(f"문서 수 제한 초과: {current_total} > {max_documents}")
            # 오래된 문서부터 제거 (FIFO)
            remove_count = current_total - max_documents
            logger.info(f"{remove_count}개의 오래된 문서를 제거합니다")
            # TODO: FAISS는 개별 벡터 제거를 지원하지 않으므로 재구축 필요
            # 임시로 경고만 출력
        
        try:
            # 1. 문서 텍스트 추출 및 임베딩 생성
            texts = [doc.get_content() for doc in documents]
            embeddings = self.embedding_model.encode(texts, convert_to_numpy=True)
            
            # 2. FAISS 인덱스에 추가
            start_idx = self.index.ntotal
            self.index.add(embeddings.astype('float32'))
            
            # 3. 메타데이터 저장
            for i, doc in enumerate(documents):
                faiss_idx = start_idx + i
                doc_id = doc.id
                
                # 매핑 정보 저장
                self.doc_id_to_faiss_idx[doc_id] = faiss_idx
                self.faiss_idx_to_doc_id[faiss_idx] = doc_id
                self.metadata_store[faiss_idx] = doc.get_metadata()
                self.documents[doc_id] = doc
            
            logger.info(f"{len(documents)}개 문서 추가 완료. 총 {self.index.ntotal}개 문서")
            
            # 4. 인덱스 저장 (옵션)
            if self.index_path:
                self._save_index()
                
        except Exception as e:
            logger.error(f"문서 추가 실패: {e}")
            raise
    
    def search(self, query_embedding: List[float], top_k: int = 10, 
               filters: Optional[Dict[str, Any]] = None) -> List[str]:
        """FAISS에서 유사도 검색 수행"""
        if self.index.ntotal == 0:
            logger.warning("인덱스가 비어있습니다")
            return []
        
        try:
            # 1. 쿼리 임베딩 준비
            if isinstance(query_embedding, list):
                query_vector = np.array(query_embedding, dtype='float32').reshape(1, -1)
            else:
                query_vector = query_embedding.astype('float32').reshape(1, -1)
            
            # 2. FAISS 검색 (더 많이 검색해서 필터링)
            search_k = min(top_k * 3, self.index.ntotal)  # 필터링 고려하여 더 많이 검색
            distances, indices = self.index.search(query_vector, search_k)
            
            # 3. 결과 처리
            results = []
            for distance, idx in zip(distances[0], indices[0]):
                if idx == -1:  # 유효하지 않은 인덱스
                    continue
                
                # 메타데이터 필터링
                if filters and not self._match_filters(idx, filters):
                    continue
                
                # Document ID 반환
                doc_id = self.faiss_idx_to_doc_id.get(idx)
                if doc_id:
                    results.append(doc_id)
                
                # top_k 제한
                if len(results) >= top_k:
                    break
            
            logger.info(f"FAISS 검색 완료: {len(results)}개 문서 반환 (필터: {filters})")
            return results
            
        except Exception as e:
            logger.error(f"FAISS 검색 실패: {e}")
            return []
    
    def _match_filters(self, faiss_idx: int, filters: Dict[str, Any]) -> bool:
        """메타데이터 필터링 확인"""
        metadata = self.metadata_store.get(faiss_idx, {})
        
        for key, value in filters.items():
            if key == 'type' and metadata.get('type') != value:
                return False
            elif key == 'category' and metadata.get('category') != value:
                return False
            elif key == 'max_price' and metadata.get('price', 0) > value:
                return False
            elif key == 'min_price' and metadata.get('price', float('inf')) < value:
                return False
            elif key == 'is_popular' and metadata.get('is_popular') != value:
                return False
            elif key == 'is_good_influence' and metadata.get('is_good_influence') != value:
                return False
            elif key == 'location' and metadata.get('location') != value:
                return False
        
        return True
    
    def get_documents_by_ids(self, doc_ids: List[str]) -> List[Document]:
        """Document ID로 문서 객체들 반환"""
        documents = []
        for doc_id in doc_ids:
            if doc_id in self.documents:
                documents.append(self.documents[doc_id])
        return documents
    
    def clear(self):
        """모든 데이터 삭제"""
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        self.metadata_store.clear()
        self.documents.clear()
        self.doc_id_to_faiss_idx.clear()
        self.faiss_idx_to_doc_id.clear()
        
        logger.info("FAISS 데이터 삭제 완료")
    
    def _save_index(self):
        """FAISS 인덱스와 메타데이터 저장"""
        if not self.index_path:
            return
        
        try:
            import faiss
            
            # 디렉토리 생성
            index_dir = Path(self.index_path).parent
            index_dir.mkdir(parents=True, exist_ok=True)
            
            # FAISS 인덱스 저장
            faiss.write_index(self.index, str(self.index_path))
            
            # 메타데이터 저장
            metadata_path = str(self.index_path).replace('.faiss', '_metadata.json')
            metadata_info = {
                'metadata_store': {str(k): v for k, v in self.metadata_store.items()},
                'doc_id_to_faiss_idx': self.doc_id_to_faiss_idx,
                'faiss_idx_to_doc_id': {str(k): v for k, v in self.faiss_idx_to_doc_id.items()},
                'embedding_dim': self.embedding_dim,
                'total_docs': self.index.ntotal
            }
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata_info, f, ensure_ascii=False, indent=2)
            
            logger.info(f"FAISS 인덱스 저장 완료: {self.index_path}")
            
        except Exception as e:
            logger.error(f"FAISS 인덱스 저장 실패: {e}")
    
    def _load_index(self):
        """저장된 FAISS 인덱스와 메타데이터 로드"""
        try:
            import faiss
            
            # FAISS 인덱스 로드
            self.index = faiss.read_index(str(self.index_path))
            
            # 메타데이터 로드
            metadata_path = str(self.index_path).replace('.faiss', '_metadata.json')
            if Path(metadata_path).exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata_info = json.load(f)
                
                self.metadata_store = {int(k): v for k, v in metadata_info['metadata_store'].items()}
                self.doc_id_to_faiss_idx = metadata_info['doc_id_to_faiss_idx']
                self.faiss_idx_to_doc_id = {int(k): v for k, v in metadata_info['faiss_idx_to_doc_id'].items()}
                
                logger.info(f"FAISS 인덱스 로드 완료: {self.index.ntotal}개 문서")
            else:
                logger.warning("메타데이터 파일을 찾을 수 없음")
                
        except Exception as e:
            logger.error(f"FAISS 인덱스 로드 실패: {e}")
            # 새 인덱스로 초기화
            self.index = faiss.IndexFlatL2(self.embedding_dim)
    
    def _convert_to_gpu_index(self):
        """CPU 인덱스를 GPU 인덱스로 변환"""
        try:
            import faiss
            
            # GPU 리소스 생성
            res = faiss.StandardGpuResources()
            
            # GPU 인덱스로 변환
            gpu_index = faiss.index_cpu_to_gpu(res, 0, self.index)
            self.index = gpu_index
            logger.info("FAISS 인덱스를 GPU로 이동했습니다.")
            
        except Exception as e:
            logger.warning(f"GPU 인덱스 변환 실패, CPU 계속 사용: {e}")
            self.use_gpu = False
    
    def encode_query(self, query_text: str) -> List[float]:
        """쿼리 텍스트를 임베딩으로 변환"""
        try:
            embedding = self.embedding_model.encode([query_text])
            return embedding[0].tolist()
        except Exception as e:
            logger.error(f"쿼리 임베딩 실패: {e}")
            return [0.0] * self.embedding_dim


class ChromaDBVectorStore(VectorStore):
    """ChromaDB 기반 Vector Store (향후 구현)"""
    
    def __init__(self, collection_name: str = "naviyam_docs", persist_directory: Optional[str] = None):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.client = None  # chromadb.Client()
        self.collection = None
        logger.info("ChromaDBVectorStore initialized (구현 예정)")
    
    def add_documents(self, documents: List[Document]):
        logger.info(f"{len(documents)}개의 문서를 ChromaDB에 추가합니다 (구현 예정)")
        # TODO: ChromaDB 구현
        pass
    
    def search(self, query_embedding: List[float], top_k: int = 10, 
               filters: Optional[Dict[str, Any]] = None) -> List[str]:
        logger.info(f"ChromaDB에서 검색 (구현 예정): 필터={filters}")
        # TODO: ChromaDB 검색 구현
        return []
    
    def get_documents_by_ids(self, doc_ids: List[str]) -> List[Document]:
        return []
    
    def clear(self):
        logger.info("ChromaDB 데이터 삭제 (구현 예정)")
        pass


class CommercialVectorStore(VectorStore):
    """상용 Vector DB (Pinecone 등) 기반 Vector Store (향후 구현)"""
    
    def __init__(self, api_key: str, environment: str, index_name: str):
        self.api_key = api_key
        self.environment = environment
        self.index_name = index_name
        self.client = None  # pinecone.init() 등
        logger.info("CommercialVectorStore initialized (구현 예정)")
    
    def add_documents(self, documents: List[Document]):
        logger.info(f"{len(documents)}개의 문서를 상용 Vector DB에 추가합니다 (구현 예정)")
        # TODO: 상용 DB 클라이언트를 사용하여 배치로 데이터 추가
        pass
    
    def search(self, query_embedding: List[float], top_k: int = 10, 
               filters: Optional[Dict[str, Any]] = None) -> List[str]:
        logger.info(f"상용 Vector DB에서 검색 (구현 예정): 필터={filters}")
        # TODO: 상용 DB는 대부분 metadata filtering을 검색 시 함께 지원 (pre-filtering)
        # client.query(vector=query_embedding, filter=filters, top_k=top_k)
        return []
    
    def get_documents_by_ids(self, doc_ids: List[str]) -> List[Document]:
        return []
    
    def clear(self):
        logger.info("상용 Vector DB 데이터 삭제 (구현 예정)")
        pass


def create_vector_store(store_type: str = "mock", **kwargs) -> VectorStore:
    """Vector Store 팩토리 함수
    
    Args:
        store_type: "mock", "faiss", "prebuilt_faiss", "chromadb", "commercial" 중 하나
        **kwargs: 각 Vector Store 구현체별 설정
    
    Returns:
        VectorStore 인스턴스
    """
    if store_type == "mock":
        return MockVectorStore(kwargs.get('storage_path'))
    elif store_type == "faiss":
        return FAISSVectorStore(kwargs.get('embedding_model'), kwargs.get('index_path'))
    elif store_type == "prebuilt_faiss":
        return PrebuiltFAISSVectorStore(
            index_path=kwargs.get('index_path', 'outputs/prebuilt_faiss.faiss'),
            metadata_path=kwargs.get('metadata_path'),
            embedding_model=kwargs.get('embedding_model')
        )
    elif store_type == "chromadb":
        return ChromaDBVectorStore(kwargs.get('collection_name', 'naviyam_docs'), 
                                  kwargs.get('persist_directory'))
    elif store_type == "commercial":
        return CommercialVectorStore(kwargs['api_key'], kwargs['environment'], kwargs['index_name'])
    else:
        raise ValueError(f"Unknown vector store type: {store_type}")