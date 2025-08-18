"""
Layer 1: 후보 생성자 (4-Funnel 통합 관리)
현재 구현된 Funnel들을 통합하여 다양한 후보군 생성
"""

import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime

try:
    from .popularity_funnel import PopularityFunnel
    from .contextual_funnel import ContextualFunnel
    from .content_funnel import ContentFunnel
    from .collaborative_funnel import CollaborativeFunnel
except ImportError:
    from popularity_funnel import PopularityFunnel
    from contextual_funnel import ContextualFunnel
    from content_funnel import ContentFunnel
    from collaborative_funnel import CollaborativeFunnel

logger = logging.getLogger(__name__)


class CandidateGenerationConfig:
    """후보 생성 설정"""
    
    # 각 Funnel별 기본 후보 수
    POPULARITY_CANDIDATES = 30
    CONTEXTUAL_CANDIDATES = 30
    CONTENT_CANDIDATES = 50      # TODO: 구현 예정
    COLLABORATIVE_CANDIDATES = 50 # TODO: 구현 예정
    
    # 최종 후보 수 제한
    MAX_TOTAL_CANDIDATES = 150
    
    # Funnel별 가중치 (추후 튜닝 가능)
    FUNNEL_WEIGHTS = {
        'popularity': 1.0,
        'contextual': 1.0,
        'content': 1.0,
        'collaborative': 1.0
    }


class CandidateGenerator:
    """Layer 1: 4-Funnel 후보 생성 시스템"""
    
    def __init__(self, config: Optional[CandidateGenerationConfig] = None):
        """
        Args:
            config: 후보 생성 설정
        """
        self.config = config or CandidateGenerationConfig()
        
        # 구현된 Funnel들 초기화
        self.popularity_funnel = PopularityFunnel()
        self.contextual_funnel = ContextualFunnel()
        self.content_funnel = ContentFunnel()
        self.collaborative_funnel = CollaborativeFunnel()
        
        logger.info("CandidateGenerator 초기화 완료")
    
    def generate_candidates(self,
                          user_id: Optional[str] = None,
                          user_location: Optional[str] = None, 
                          query: Optional[str] = None,
                          time_of_day: Optional[str] = None,
                          user_type: Optional[str] = None,
                          filters: Optional[Dict[str, Any]] = None,
                          current_time: Optional[datetime] = None,
                          recent_categories: Set[str] = None,
                          user_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        4-Funnel을 통해 다양한 후보군 생성
        
        Args:
            user_id: 사용자 ID (협업 필터링용)
            user_location: 사용자 위치
            query: 검색 쿼리 (콘텐츠 기반용)
            time_of_day: 시간대 
            user_type: 사용자 타입 (협업 필터링용)
            filters: 필터 조건
            current_time: 현재 시간
            
        Returns:
            통합된 후보 리스트
        """
        if current_time is None:
            current_time = datetime.now()
        
        all_candidates = []
        
        # Funnel 1: 협업 필터링 기반 후보 생성
        try:
            collaborative_candidates = self.collaborative_funnel.get_candidates(
                user_id=user_id,
                user_type=user_type,
                filters=filters,
                limit=self.config.COLLABORATIVE_CANDIDATES,
                recent_categories=recent_categories,
                user_context=user_context
            )
            all_candidates.extend(collaborative_candidates)
            logger.info(f"협업 Funnel: {len(collaborative_candidates)}개 후보 생성")
        except Exception as e:
            logger.error(f"협업 Funnel 오류: {e}")
        
        # Funnel 2: 콘텐츠 기반 후보 생성
        if query:
            try:
                content_candidates = self.content_funnel.get_candidates(
                    query=query,
                    filters=filters,
                    limit=self.config.CONTENT_CANDIDATES,
                    recent_categories=recent_categories,
                    user_context=user_context
                )
                all_candidates.extend(content_candidates)
                logger.info(f"콘텐츠 Funnel: {len(content_candidates)}개 후보 생성")
            except Exception as e:
                logger.error(f"콘텐츠 Funnel 오류: {e}")
        
        # Funnel 3: 상황/규칙 기반 후보 생성  
        try:
            contextual_candidates = self.contextual_funnel.get_candidates(
                user_location=user_location,
                current_time=current_time,
                time_of_day=time_of_day,
                filters=filters,
                limit=self.config.CONTEXTUAL_CANDIDATES,
                recent_categories=recent_categories,
                user_context=user_context
            )
            all_candidates.extend(contextual_candidates)
            logger.info(f"상황 Funnel: {len(contextual_candidates)}개 후보 생성")
        except Exception as e:
            logger.error(f"상황 Funnel 오류: {e}")
        
        # Funnel 4: 인기도 기반 후보 생성
        try:
            popularity_candidates = self.popularity_funnel.get_candidates(
                filters=filters,
                limit=self.config.POPULARITY_CANDIDATES,
                recent_categories=recent_categories,
                user_context=user_context
            )
            all_candidates.extend(popularity_candidates)
            logger.info(f"인기도 Funnel: {len(popularity_candidates)}개 후보 생성")
        except Exception as e:
            logger.error(f"인기도 Funnel 오류: {e}")
        
        # 중복 제거 및 통합
        unique_candidates = self._remove_duplicates(all_candidates)
        
        # exclude_shop_ids 필터 적용
        if filters and filters.get('exclude_shop_ids'):
            exclude_ids = set(filters['exclude_shop_ids'])
            unique_candidates = [c for c in unique_candidates if c['shop_id'] not in exclude_ids]
            logger.info(f"가게 ID 제외 필터 적용: {len(exclude_ids)}개 제외")
        
        # 최종 후보 수 제한
        final_candidates = unique_candidates[:self.config.MAX_TOTAL_CANDIDATES]
        
        logger.info(f"후보 생성 완료: 총 {len(final_candidates)}개 (중복 제거 후)")
        return final_candidates
    
    def _remove_duplicates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """중복 후보 제거 및 통합"""
        seen_shops = {}
        unique_candidates = []
        
        for candidate in candidates:
            shop_id = candidate['shop_id']
            
            if shop_id not in seen_shops:
                # 첫 번째 등장하는 매장
                seen_shops[shop_id] = candidate
                unique_candidates.append(candidate)
            else:
                # 이미 있는 매장 - funnel_source 정보 추가
                existing = seen_shops[shop_id]
                existing_sources = existing.get('funnel_sources', [existing['funnel_source']])
                new_source = candidate['funnel_source']
                
                if new_source not in existing_sources:
                    existing_sources.append(new_source)
                    existing['funnel_sources'] = existing_sources
                    existing['funnel_source'] = ' + '.join(existing_sources)
                
                # 점수 통합 (최고 점수 사용)
                existing_score = existing.get('base_score', existing.get('context_score', existing.get('content_score', existing.get('collaborative_score', 0))))
                new_score = candidate.get('base_score', candidate.get('context_score', candidate.get('content_score', candidate.get('collaborative_score', 0))))
                if new_score > existing_score:
                    for score_key in ['base_score', 'context_score', 'content_score', 'collaborative_score']:
                        if score_key in existing and score_key in candidate:
                            existing[score_key] = candidate[score_key]
        
        return unique_candidates
    
    def get_funnel_stats(self) -> Dict[str, Any]:
        """각 Funnel별 통계 정보"""
        stats = {
            'config': {
                'max_candidates': self.config.MAX_TOTAL_CANDIDATES,
                'funnel_limits': {
                    'popularity': self.config.POPULARITY_CANDIDATES,
                    'contextual': self.config.CONTEXTUAL_CANDIDATES,
                    'content': self.config.CONTENT_CANDIDATES,
                    'collaborative': self.config.COLLABORATIVE_CANDIDATES
                }
            },
            'popularity_stats': self.popularity_funnel.get_popularity_stats()
        }
        
        return stats


# 테스트 함수
def test_candidate_generator():
    """후보 생성자 테스트"""
    generator = CandidateGenerator()
    
    print("=== Layer 1: 후보 생성자 통합 테스트 ===")
    
    # 종합적인 후보 생성 테스트
    candidates = generator.generate_candidates(
        user_location="관악구",
        time_of_day="lunch",
        query="비빔밥", 
        user_type="healthy_eater",
        filters={'category': '한식'}
    )
    
    print(f"\n관악구 점심시간 한식 '비빔밥' 검색 (건강지향 사용자) Top 10:")
    for i, candidate in enumerate(candidates[:10], 1):
        shop_name = candidate['shop_name']
        category = candidate['category']
        funnel_source = candidate['funnel_source']
        
        # 점수 정보 
        score_parts = []
        if 'collaborative_score' in candidate:
            score_parts.append(f"협업: {candidate['collaborative_score']:.1f}")
        if 'content_score' in candidate:
            score_parts.append(f"콘텐츠: {candidate['content_score']:.1f}")
        if 'context_score' in candidate:
            score_parts.append(f"상황: {candidate['context_score']:.1f}")
        if 'base_score' in candidate:
            score_parts.append(f"인기도: {candidate['base_score']:.1f}")
        
        score_info = ", ".join(score_parts) if score_parts else "N/A"
        
        print(f"{i}. {shop_name} ({category})")
        print(f"   출처: {funnel_source}")
        print(f"   점수: {score_info}")
        print(f"   이유: {candidate.get('reason', 'N/A')}")
        print()
    
    # 통계 정보
    stats = generator.get_funnel_stats()
    print(f"=== 통계 정보 ===")
    print(f"최대 후보 수: {stats['config']['max_candidates']}")
    print(f"인기도 매장 수: {stats['popularity_stats']['total_shops']}")
    print(f"인기도 평균 점수: {stats['popularity_stats']['avg_score']:.1f}")


if __name__ == "__main__":
    test_candidate_generator()