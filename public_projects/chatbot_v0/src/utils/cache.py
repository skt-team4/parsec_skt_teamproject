"""
나비얌 챗봇 캐싱 시스템

쿼리 결과와 임베딩을 캐싱하여 성능 향상
"""

import json
import time
import hashlib
import pickle
from typing import Any, Optional, Dict, List
from pathlib import Path
from functools import lru_cache, wraps
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class QueryCache:
    """쿼리 결과 캐싱 시스템"""
    
    def __init__(self, cache_dir: Path, ttl_minutes: int = 60, max_size: int = 1000):
        """
        Args:
            cache_dir: 캐시 디렉토리
            ttl_minutes: 캐시 유효시간 (분)
            max_size: 최대 캐시 항목 수
        """
        self.cache_dir = cache_dir
        self.ttl = timedelta(minutes=ttl_minutes)
        self.max_size = max_size
        
        # 메모리 캐시
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        
        # 캐시 디렉토리 생성
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        
        # 캐시 통계
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
        
        logger.info(f"QueryCache 초기화: TTL={ttl_minutes}분, 최대크기={max_size}")
    
    def _get_cache_key(self, query: str, filters: Optional[Dict] = None, version: str = "v1") -> str:
        """쿼리와 필터로 캐시 키 생성 (버전 포함)"""
        cache_data = {
            'query': query.strip().lower(),
            'filters': filters or {},
            'version': version  # 캐시 버전 추가
        }
        cache_str = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(cache_str.encode()).hexdigest()
    
    def get(self, query: str, filters: Optional[Dict] = None, version: str = "v1") -> Optional[List[Any]]:
        """캐시에서 결과 조회"""
        cache_key = self._get_cache_key(query, filters, version)
        
        # 1. 메모리 캐시 확인
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if datetime.now() < entry['expires_at']:
                self.stats['hits'] += 1
                logger.debug(f"캐시 히트: {query[:30]}...")
                return entry['result']
            else:
                # 만료된 항목 제거
                del self._memory_cache[cache_key]
        
        # 2. 디스크 캐시 확인
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    entry = pickle.load(f)
                
                if datetime.now() < entry['expires_at']:
                    # 메모리 캐시에 추가
                    self._memory_cache[cache_key] = entry
                    self.stats['hits'] += 1
                    logger.debug(f"디스크 캐시 히트: {query[:30]}...")
                    return entry['result']
                else:
                    # 만료된 파일 삭제
                    cache_file.unlink()
            except UnicodeDecodeError as e:
                logger.warning(f"캐시 파일 읽기 실패 (유니코드 에러): {e}")
                # 손상된 캐시 파일 삭제
                try:
                    cache_file.unlink()
                except:
                    pass
            except Exception as e:
                logger.warning(f"캐시 파일 읽기 실패: {e}")
                # 손상된 캐시 파일 삭제
                try:
                    cache_file.unlink()
                except:
                    pass
        
        self.stats['misses'] += 1
        return None
    
    def set(self, query: str, result: List[Any], filters: Optional[Dict] = None, version: str = "v1"):
        """결과를 캐시에 저장"""
        cache_key = self._get_cache_key(query, filters, version)
        
        # 캐시 크기 제한 확인
        if len(self._memory_cache) >= self.max_size:
            self._evict_oldest()
        
        entry = {
            'query': query,
            'filters': filters,
            'result': result,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + self.ttl
        }
        
        # 메모리 캐시에 저장
        self._memory_cache[cache_key] = entry
        
        # 디스크에도 저장 (비동기적으로 처리 가능)
        try:
            cache_file = self.cache_dir / f"{cache_key}.pkl"
            with open(cache_file, 'wb') as f:
                # UTF-8로 안전하게 저장하기 위해 protocol 버전 명시
                pickle.dump(entry, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.debug(f"캐시 저장: {query[:30]}...")
        except UnicodeEncodeError as e:
            logger.warning(f"캐시 파일 저장 실패 (유니코드 에러): {e}")
            # 이모지나 특수 문자가 있는 경우 메모리 캐시만 사용
        except Exception as e:
            logger.warning(f"캐시 파일 저장 실패: {e}")
    
    def _evict_oldest(self):
        """가장 오래된 캐시 항목 제거"""
        if not self._memory_cache:
            return
        
        # 생성 시간 기준으로 정렬
        sorted_items = sorted(
            self._memory_cache.items(),
            key=lambda x: x[1]['created_at']
        )
        
        # 가장 오래된 10% 제거
        evict_count = max(1, len(sorted_items) // 10)
        for key, _ in sorted_items[:evict_count]:
            del self._memory_cache[key]
            self.stats['evictions'] += 1
            
            # 디스크 파일도 삭제
            cache_file = self.cache_dir / f"{key}.pkl"
            if cache_file.exists():
                cache_file.unlink()
    
    def clear(self):
        """전체 캐시 삭제"""
        self._memory_cache.clear()
        
        # 디스크 캐시 파일 모두 삭제
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
        
        logger.info("캐시 전체 삭제 완료")
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'evictions': self.stats['evictions'],
            'hit_rate': f"{hit_rate:.1%}",
            'memory_items': len(self._memory_cache),
            'disk_files': len(list(self.cache_dir.glob("*.pkl")))
        }


class EmbeddingCache:
    """임베딩 벡터 캐싱 (텍스트 -> 벡터)"""
    
    def __init__(self, cache_size: int = 10000):
        self.cache_size = cache_size
        self._cache = {}
        self.stats = {'hits': 0, 'misses': 0}
    
    @lru_cache(maxsize=10000)
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """캐시된 임베딩 조회"""
        # LRU 캐시가 자동으로 처리
        return None
    
    def set_embedding(self, text: str, embedding: List[float]):
        """임베딩 캐시에 저장"""
        # 실제로는 별도 저장 로직 필요
        pass


def cached_result(cache: QueryCache):
    """쿼리 결과 캐싱 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, user_query: str, *args, **kwargs):
            # 캐시 확인
            filters = kwargs.get('filters')
            cached = cache.get(user_query, filters)
            if cached is not None:
                return cached
            
            # 함수 실행
            result = func(self, user_query, *args, **kwargs)
            
            # 결과 캐싱
            cache.set(user_query, result, filters)
            
            return result
        
        return wrapper
    return decorator


# 전역 캐시 인스턴스 (필요시 생성)
_query_cache: Optional[QueryCache] = None
_embedding_cache: Optional[EmbeddingCache] = None


def get_query_cache(cache_dir: Optional[Path] = None) -> QueryCache:
    """전역 쿼리 캐시 인스턴스 반환"""
    global _query_cache
    if _query_cache is None:
        from utils.config import PathConfig
        path_config = PathConfig()
        cache_dir = cache_dir or path_config.CACHE_DIR / "queries"
        _query_cache = QueryCache(cache_dir)
    return _query_cache


def get_embedding_cache() -> EmbeddingCache:
    """전역 임베딩 캐시 인스턴스 반환"""
    global _embedding_cache
    if _embedding_cache is None:
        _embedding_cache = EmbeddingCache()
    return _embedding_cache