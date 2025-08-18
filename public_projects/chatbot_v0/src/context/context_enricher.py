"""
Context Enricher Module
NLU와 RAG 사이에서 사용자 컨텍스트를 풍부하게 만들어 RAG 검색 다양성 확보
"""

import json
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from pathlib import Path
import os

logger = logging.getLogger(__name__)


class ContextEnricher:
    """사용자 컨텍스트를 풍부하게 만들어 RAG 검색 개선"""
    
    
    def __init__(self):
        """초기화"""
        self.personas = self._load_personas()
        self.user_histories = {}  # 사용자별 최근 이용 내역
        self.nutrition_status = {}  # 사용자별 영양 상태
        
    def _load_personas(self) -> Dict:
        """페르소나 데이터 로드"""
        try:
            base_dir = Path(__file__).parent.parent.parent
            personas_path = base_dir / 'data' / 'personas.json'
            
            with open(personas_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {p['id']: p for p in data['personas']}
        except Exception as e:
            logger.error(f"페르소나 데이터 로드 실패: {e}")
            return {}
    
    def enrich(self, 
               nlu_result: Dict,
               user_id: str,
               persona_id: Optional[str] = None,
               weather_info: Optional[Dict] = None) -> Dict[str, Any]:
        """
        NLU 결과를 받아 풍부한 컨텍스트 생성
        
        Args:
            nlu_result: NLU 분석 결과 (intent, entities)
            user_id: 사용자 ID
            persona_id: 페르소나 ID (tae_hoon, min_ho, myeong_bin)
            
        Returns:
            enriched_context: RAG 검색에 사용할 풍부한 컨텍스트
        """
        context = {
            'original_query': nlu_result.get('text', ''),
            'intent': nlu_result.get('intent'),
            'entities': nlu_result.get('entities', {}),
            'timestamp': datetime.now().isoformat()
        }
        
        # 1. 페르소나 정보 추가
        if persona_id and persona_id in self.personas:
            persona = self.personas[persona_id]
            context['persona'] = {
                'id': persona_id,
                'age': persona['age'],
                'preferences': persona.get('preferences', {}),
                'dietary_restrictions': persona.get('teen_personalizer_features', {}).get('dietary_restrictions', [])
            }
            
            # 위치 정보 추가 (personas.json에서 가져옴)
            if 'location' in persona:
                context['location'] = persona['location']
            
            # 급식카드 잔고 정보
            context['meal_card'] = persona.get('meal_card_info', {})
            
            # 영양 상태
            context['nutrition_status'] = persona.get('nutrition_status', {})
        
        # 2. 최근 이용 내역 분석 (30일 데이터 활용)
        recent_history = self._analyze_recent_history(user_id, persona_id)
        context['recent_history'] = recent_history
        
        # 3. 제외/선호 카테고리 계산 (사용자 명시적 요청 고려)
        # entities에서 사용자가 명시적으로 요청한 카테고리 확인
        requested_category = nlu_result.get('entities', {}).get('food_type')
        context['category_weights'] = self._calculate_category_weights(recent_history, persona_id, requested_category)
        
        # 4. 시간대별 컨텍스트
        context['time_context'] = self._get_time_context()
        
        # 5. 날씨 컨텍스트 (외부에서 전달받거나 mock 사용)
        if weather_info:
            context['weather'] = weather_info
        else:
            context['weather'] = self._get_weather_context()
        
        # 6. RAG 검색 쿼리 증강
        context['enhanced_query'] = self._generate_enhanced_query(context)
        
        logger.info(f"Context enriched for {user_id}: {context.get('enhanced_query', '')}")
        
        return context
    
    def _analyze_recent_history(self, user_id: str, persona_id: Optional[str]) -> Dict:
        """최근 이용 내역 분석 (30일 데이터 기반)"""
        history = {
            'recent_3days': [],
            'recent_7days': [],
            'category_frequency': {},
            'last_order_time': None
        }
        
        # TeenPersonalizer에서 실제 사용 데이터 가져오기
        try:
            from src.personalization.teen_personalizer import get_personalizer
            personalizer = get_personalizer()
            profile = personalizer.get_profile(persona_id or user_id)
            
            # 프로필의 order_history와 click_history에서 데이터 추출
            if profile.order_history or profile.click_history:
                # 최근 주문 내역에서 카테고리 추출
                from datetime import datetime, timedelta
                now = datetime.now()
                three_days_ago = now - timedelta(days=3)
                seven_days_ago = now - timedelta(days=7)
                
                all_interactions = profile.order_history + profile.click_history
                
                for interaction in all_interactions:
                    if 'timestamp' in interaction and 'metadata' in interaction:
                        timestamp = datetime.fromisoformat(interaction['timestamp'])
                        category = interaction.get('metadata', {}).get('category')
                        
                        if category:
                            # 7일 이내
                            if timestamp >= seven_days_ago:
                                history['recent_7days'].append(category)
                                history['category_frequency'][category] = history['category_frequency'].get(category, 0) + 1
                                
                                # 3일 이내
                                if timestamp >= three_days_ago:
                                    history['recent_3days'].append(category)
                
                # 마지막 주문 시간
                if all_interactions:
                    last_interaction = max(all_interactions, key=lambda x: x.get('timestamp', ''))
                    history['last_order_time'] = last_interaction.get('timestamp')
                
                # 데이터가 있다면 바로 반환
                if history['recent_7days']:
                    logger.info(f"실제 사용 데이터 분석: {user_id} - 최근 7일 {len(history['recent_7days'])}건")
                    return history
        except Exception as e:
            logger.debug(f"TeenPersonalizer 데이터 로드 실패, 목 데이터 사용: {e}")
        
        # 실제 데이터가 없으면 페르소나별 시뮬레이션 데이터 사용
        if persona_id == 'tae_hoon':
            # 강태훈: 편의점, 인스턴트 위주
            history['recent_3days'] = ['치킨', '컵라면', '삼각김밥']
            history['recent_7days'] = ['치킨', '컵라면', '삼각김밥', '피자', '햄버거', '치킨', '떡볶이']
            history['category_frequency'] = {
                '치킨': 3,
                '편의점': 5,
                '패스트푸드': 2
            }
            # 프로필에 시뮬레이션 데이터 저장
            self._save_simulation_data_to_profile(persona_id, history)
        elif persona_id == 'min_ho':
            # 김민호: 한식 위주, 학생
            history['recent_3days'] = ['김치찌개', '제육볶음', '치킨']
            history['recent_7days'] = ['김치찌개', '제육볶음', '치킨', '불고기', '김밥', '떡볶이', '삼겹살']
            history['category_frequency'] = {
                '한식': 4,
                '치킨': 1,
                '분식': 2
            }
            self._save_simulation_data_to_profile(persona_id, history)
        elif persona_id == 'myeong_bin':
            # 김명빈: 균형잡힌 식사
            history['recent_3days'] = ['닭죽', '비빔밥', '샐러드']
            history['recent_7days'] = ['닭죽', '비빔밥', '샐러드', '도시락', '김밥', '파스타', '죽']
            history['category_frequency'] = {
                '한식': 3,
                '죽': 2,
                '양식': 1,
                '샐러드': 1
            }
            self._save_simulation_data_to_profile(persona_id, history)
        
        return history
    
    def _save_simulation_data_to_profile(self, persona_id: str, history: Dict):
        """시뮬레이션 데이터를 TeenPersonalizer 프로필에 저장"""
        try:
            from src.personalization.teen_personalizer import get_personalizer
            from datetime import datetime, timedelta
            
            personalizer = get_personalizer()
            
            # 각 카테고리에 대해 가상의 상호작용 생성
            now = datetime.now()
            for i, category in enumerate(history.get('recent_7days', [])):
                # 7일 내 분산된 타임스탬프로 상호작용 생성
                days_ago = 7 - (i % 7)
                interaction_time = now - timedelta(days=days_ago, hours=i % 24)
                
                # 주문 또는 클릭으로 기록
                interaction_type = 'order' if i % 3 == 0 else 'click'
                
                personalizer.update_from_interaction(
                    user_id=persona_id,
                    shop_id=1000 + i,  # 가상의 shop_id
                    interaction_type=interaction_type,
                    metadata={
                        'category': category,
                        'timestamp': interaction_time.isoformat(),
                        'simulated': True
                    }
                )
            
            logger.info(f"시뮬레이션 데이터 {len(history.get('recent_7days', []))}건을 {persona_id} 프로필에 저장")
        except Exception as e:
            logger.debug(f"시뮬레이션 데이터 저장 실패: {e}")
    
    def _calculate_category_weights(self, history: Dict, persona_id: Optional[str], requested_category: Optional[str] = None) -> Dict:
        """카테고리별 가중치 계산 (다양성 확보)"""
        weights = {
            'boost_categories': [],
            'penalize_categories': {},
            'exclude_categories': []
        }
        
        # 최근 3일 내 2회 이상 먹은 카테고리는 페널티
        recent_3days = history.get('recent_3days', [])
        category_count = {}
        for item in recent_3days:
            category_count[item] = category_count.get(item, 0) + 1
        
        for category, count in category_count.items():
            if count >= 2:
                # 사용자가 명시적으로 요청한 카테고리는 페널티 제외
                if requested_category and category.lower() in requested_category.lower():
                    logger.info(f"카테고리 '{category}' - 사용자 명시적 요청으로 페널티 제외")
                else:
                    weights['penalize_categories'][category] = 0.3  # 70% 감점
                    logger.info(f"카테고리 '{category}' 페널티 적용 (최근 3일 {count}회)")
        
        # 페르소나별 영양 균형 고려
        if persona_id:
            persona = self.personas.get(persona_id, {})
            nutrition_issues = persona.get('nutrition_status', {}).get('current_issues', [])
            
            if 'vitamin_deficiency' in nutrition_issues:
                weights['boost_categories'].extend(['샐러드', '과일', '채소'])
            if 'excess_sugar' in nutrition_issues:
                weights['penalize_categories']['디저트'] = 0.2
                weights['penalize_categories']['음료'] = 0.3
            if 'excess_sodium' in nutrition_issues:
                weights['penalize_categories']['라면'] = 0.2
                weights['penalize_categories']['찌개'] = 0.5
        
        return weights
    
    def _get_time_context(self) -> Dict:
        """시간대별 컨텍스트"""
        now = datetime.now()
        hour = now.hour
        
        if 6 <= hour < 10:
            return {'period': 'breakfast', 'preferences': ['죽', '샌드위치', '토스트']}
        elif 10 <= hour < 14:
            return {'period': 'lunch', 'preferences': ['한식', '도시락', '백반']}
        elif 14 <= hour < 17:
            return {'period': 'snack', 'preferences': ['카페', '디저트', '간식']}
        elif 17 <= hour < 21:
            return {'period': 'dinner', 'preferences': ['한식', '양식', '중식']}
        else:
            return {'period': 'late_night', 'preferences': ['야식', '편의점', '포장마차']}
    
    def _get_weather_context(self) -> Dict:
        """날씨 컨텍스트 (실제로는 API 연동)"""
        # Mock 데이터 - 실제로는 날씨 API 호출
        import random
        weather_options = [
            {'condition': 'rain', 'temp': 15, 'preferences': ['국물요리', '전', '라면']},
            {'condition': 'clear', 'temp': 28, 'preferences': ['냉면', '샐러드', '빙수']},
            {'condition': 'cloudy', 'temp': 20, 'preferences': []},
        ]
        return random.choice(weather_options)
    
    def _generate_enhanced_query(self, context: Dict) -> str:
        """컨텍스트 기반 RAG 검색 쿼리 생성"""
        parts = []
        
        # 원본 쿼리
        original = context.get('original_query', '')
        if original:
            parts.append(original)
        
        # 위치 정보
        if 'location' in context:
            parts.append(f"{context['location']['name']} 근처")
        
        # 시간대
        time_ctx = context.get('time_context', {})
        if time_ctx.get('period'):
            parts.append(f"{time_ctx['period']} 시간대")
        
        # 날씨
        weather = context.get('weather', {})
        weather_condition = weather.get('condition', '').lower()
        weather_temp = weather.get('temp', 20)
        
        if weather_condition in ['rain', '비']:
            parts.append("비오는 날 먹기 좋은")
        elif weather_condition in ['snow', '눈']:
            parts.append("눈오는 날 따뜻한")
        elif weather_condition in ['clear', '맑음'] and weather_temp > 25:
            parts.append("더운 날 시원한")
        elif weather_temp <= 5:
            parts.append("추운 날 따뜻한")
        
        # 카테고리 가중치 반영
        weights = context.get('category_weights', {})
        
        # 페널티 카테고리 제외
        if weights.get('penalize_categories'):
            excluded = list(weights['penalize_categories'].keys())
            if excluded:
                parts.append(f"({', '.join(excluded)} 제외하고)")
        
        # 추천 카테고리
        if weights.get('boost_categories'):
            parts.append(f"{', '.join(weights['boost_categories'][:2])} 위주로")
        
        # 알레르기/제한사항
        if 'persona' in context:
            restrictions = context['persona'].get('dietary_restrictions', [])
            if restrictions:
                parts.append(f"({', '.join(restrictions)} 없는)")
        
        # 예산
        if 'meal_card' in context:
            daily_limit = context['meal_card'].get('daily_limit', 9500)
            parts.append(f"{daily_limit}원 이내")
        
        enhanced_query = " ".join(parts)
        
        # 쿼리가 너무 길면 핵심만 추출
        if len(enhanced_query) > 200:
            # 우선순위: 원본 쿼리, 제외 조건, 위치, 예산
            priority_parts = [original]
            if weights.get('penalize_categories'):
                priority_parts.append(f"({', '.join(list(weights['penalize_categories'].keys())[:2])} 제외)")
            if 'location' in context:
                priority_parts.append(f"{context['location']['name']} 근처")
            priority_parts.append(f"{daily_limit}원 이내")
            enhanced_query = " ".join(priority_parts)
        
        return enhanced_query
    
    def update_history(self, user_id: str, order_info: Dict):
        """사용자 주문 내역 업데이트"""
        if user_id not in self.user_histories:
            self.user_histories[user_id] = []
        
        self.user_histories[user_id].append({
            'timestamp': datetime.now().isoformat(),
            'shop_name': order_info.get('shop_name'),
            'category': order_info.get('category'),
            'menu': order_info.get('menu'),
            'price': order_info.get('price')
        })
        
        # 최근 30개만 유지
        if len(self.user_histories[user_id]) > 30:
            self.user_histories[user_id] = self.user_histories[user_id][-30:]
        
        logger.info(f"주문 내역 업데이트: {user_id} - {order_info.get('shop_name')}")


# 싱글톤 인스턴스
_context_enricher = None

def get_context_enricher() -> ContextEnricher:
    """Context Enricher 싱글톤 인스턴스 반환"""
    global _context_enricher
    if _context_enricher is None:
        _context_enricher = ContextEnricher()
    return _context_enricher