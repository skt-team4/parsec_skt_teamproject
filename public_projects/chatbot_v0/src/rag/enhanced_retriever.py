"""
향상된 검색 엔진 - 동의어 처리 및 하이브리드 검색
"""
import json
import re
import pickle
import hashlib
import asyncio
import concurrent.futures
from typing import List, Dict, Optional, Set, Tuple
from pathlib import Path
import numpy as np

class EnhancedRetriever:
    """동의어 및 하이브리드 검색을 지원하는 향상된 검색기"""
    
    def __init__(self, 
                 knowledge_base: Dict,
                 vector_retriever=None,
                 synonyms_path: str = "data/synonyms.json",
                 cache_dir: str = "cache"):
        self.knowledge_base = knowledge_base
        self.vector_retriever = vector_retriever
        self.restaurants = knowledge_base.get('restaurants', {})
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # 동의어 사전 로드
        self.synonyms = self._load_synonyms(synonyms_path)
        
        # 캐싱된 역방향 인덱스 로드 또는 구축
        self.inverted_index = self._load_or_build_inverted_index()
        
    def _load_synonyms(self, path: str) -> Dict:
        """동의어 사전 로드"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"음식_동의어": {}}
    
    def _get_data_hash(self) -> str:
        """데이터 해시 생성 (캐시 무효화 확인용)"""
        data_str = json.dumps(self.restaurants, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def _load_or_build_inverted_index(self) -> Dict[str, Set[str]]:
        """캐싱된 인덱스 로드 또는 새로 구축"""
        cache_file = self.cache_dir / "inverted_index.pkl"
        hash_file = self.cache_dir / "data_hash.txt"
        
        current_hash = self._get_data_hash()
        
        # 캐시 파일이 존재하고 데이터가 변경되지 않았다면 로드
        if cache_file.exists() and hash_file.exists():
            try:
                with open(hash_file, 'r') as f:
                    cached_hash = f.read().strip()
                
                if cached_hash == current_hash:
                    with open(cache_file, 'rb') as f:
                        return pickle.load(f)
            except Exception:
                pass  # 캐시 로드 실패 시 새로 구축
        
        # 새로 구축
        index = self._build_inverted_index()
        
        # 캐시 저장
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(index, f)
            with open(hash_file, 'w') as f:
                f.write(current_hash)
        except Exception:
            pass  # 캐시 저장 실패 무시
        
        return index
    
    def _build_inverted_index(self) -> Dict[str, Set[str]]:
        """역방향 인덱스 구축 - 키워드로 레스토랑 ID 찾기"""
        index = {}
        
        for shop_id, restaurant in self.restaurants.items():
            # 텍스트 필드들 추출
            text_fields = []
            
            # 가게 이름
            text_fields.append(restaurant.get('shopName', ''))
            
            # 카테고리
            text_fields.append(restaurant.get('category', ''))
            
            # 태그들
            tags = restaurant.get('tags', [])
            text_fields.extend(tags)
            
            # 설명
            text_fields.append(restaurant.get('description', ''))
            
            # 메뉴 이름들
            menus = restaurant.get('menus', [])
            for menu in menus:
                text_fields.append(menu.get('name', ''))
            
            # 모든 텍스트를 소문자로 변환하고 토큰화
            for text in text_fields:
                if text:
                    tokens = self._tokenize(text.lower())
                    for token in tokens:
                        if token not in index:
                            index[token] = set()
                        index[token].add(shop_id)
        
        return index
    
    def _tokenize(self, text: str) -> List[str]:
        """텍스트를 토큰으로 분리"""
        # 한글, 영문, 숫자만 추출
        tokens = re.findall(r'[가-힣]+|[a-zA-Z]+|[0-9]+', text)
        return [t for t in tokens if len(t) > 0]
    
    def expand_query(self, query: str) -> List[str]:
        """동의어를 사용하여 쿼리 확장"""
        expanded_terms = [query.lower()]
        
        # 동의어 사전에서 관련 단어 찾기
        for category, synonym_dict in self.synonyms.items():
            for key, synonyms in synonym_dict.items():
                # 쿼리가 키와 일치하면 동의어 추가
                if query.lower() == key.lower():
                    expanded_terms.extend([s.lower() for s in synonyms])
                # 쿼리가 동의어 중 하나와 일치하면 키와 다른 동의어 추가
                elif query.lower() in [s.lower() for s in synonyms]:
                    expanded_terms.append(key.lower())
                    expanded_terms.extend([s.lower() for s in synonyms if s.lower() != query.lower()])
        
        # 중복 제거
        return list(set(expanded_terms))
    
    def keyword_search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """키워드 기반 검색"""
        # 쿼리 확장
        expanded_queries = self.expand_query(query)
        
        # 각 레스토랑의 매칭 점수 계산
        scores = {}
        
        for expanded_query in expanded_queries:
            tokens = self._tokenize(expanded_query)
            
            for token in tokens:
                # 역방향 인덱스에서 매칭되는 레스토랑 찾기
                matching_shops = self.inverted_index.get(token, set())
                
                for shop_id in matching_shops:
                    if shop_id not in scores:
                        scores[shop_id] = 0
                    
                    # 원래 쿼리와의 매칭이면 높은 점수
                    if expanded_query == query.lower():
                        scores[shop_id] += 2.0
                    else:
                        scores[shop_id] += 1.0
        
        # 점수별로 정렬
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # 정규화된 점수와 함께 반환
        if sorted_results:
            max_score = sorted_results[0][1]
            normalized_results = [(shop_id, score/max_score) for shop_id, score in sorted_results[:top_k]]
            return normalized_results
        
        return []
    
    def vector_search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """벡터 기반 의미 검색"""
        if self.vector_retriever:
            # 기존 벡터 검색 활용
            results = self.vector_retriever.search(query, k=top_k)
            # 결과 형식 변환 (필요시)
            return [(r['shop_id'], r['score']) for r in results]
        return []
    
    def hybrid_search(self, query: str, top_k: int = 10, 
                     keyword_weight: float = 0.5,
                     vector_weight: float = 0.5) -> List[Dict]:
        """하이브리드 검색 - 키워드와 벡터 검색 결합 (병렬 처리)"""
        # 병렬로 검색 수행
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # 비동기 태스크 제출
            keyword_future = executor.submit(self.keyword_search, query, top_k=top_k*2)
            vector_future = executor.submit(self.vector_search, query, top_k=top_k*2)
            
            # 결과 대기
            keyword_results = keyword_future.result()
            vector_results = vector_future.result()
        
        keyword_scores = {shop_id: score for shop_id, score in keyword_results}
        vector_scores = {shop_id: score for shop_id, score in vector_results}
        
        # 모든 후보 shop_id 수집
        all_shop_ids = set(keyword_scores.keys()) | set(vector_scores.keys())
        
        # 하이브리드 점수 계산
        hybrid_scores = []
        for shop_id in all_shop_ids:
            k_score = keyword_scores.get(shop_id, 0)
            v_score = vector_scores.get(shop_id, 0)
            
            # 가중 평균
            final_score = keyword_weight * k_score + vector_weight * v_score
            
            # 레스토랑 정보 가져오기
            restaurant = self.restaurants.get(shop_id, {})
            
            hybrid_scores.append({
                'shop_id': shop_id,
                'shop_name': restaurant.get('shopName', ''),
                'category': restaurant.get('category', ''),
                'score': final_score,
                'keyword_score': k_score,
                'vector_score': v_score,
                'menus': restaurant.get('menus', []),
                'description': restaurant.get('description', ''),
                'tags': restaurant.get('tags', [])
            })
        
        # 점수별로 정렬
        hybrid_scores.sort(key=lambda x: x['score'], reverse=True)
        
        return hybrid_scores[:top_k]
    
    def search_by_context(self, query: str, context: Dict, top_k: int = 10) -> List[Dict]:
        """컨텍스트를 고려한 검색"""
        # 기본 하이브리드 검색
        results = self.hybrid_search(query, top_k=top_k*2)
        
        # 컨텍스트 기반 필터링 및 재정렬
        filtered_results = []
        
        for result in results:
            # 예산 필터링
            if 'budget' in context and context['budget']:
                budget = int(context['budget'])
                # 메뉴 중 예산 내에서 먹을 수 있는 것이 있는지 확인
                affordable_menus = [m for m in result['menus'] 
                                  if m.get('price', float('inf')) <= budget]
                if not affordable_menus:
                    continue
                result['affordable_menus'] = affordable_menus
            
            # 위치 필터링 (구현 필요시 추가)
            if 'location' in context and context['location']:
                # 위치 기반 필터링 로직
                pass
            
            # 시간 필터링 (구현 필요시 추가)
            if 'time' in context and context['time']:
                # 영업시간 기반 필터링 로직
                pass
            
            filtered_results.append(result)
        
        return filtered_results[:top_k]