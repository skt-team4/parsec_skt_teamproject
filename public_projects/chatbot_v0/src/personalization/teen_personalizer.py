"""
TeenPersonalizer: 10대 청소년 맞춤 실시간 개인화 엔진
11개 피처 기반 + EMA 실시간 학습 + Multi-Armed Bandit
"""

import json
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import numpy as np
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class TeenProfile:
    """10대 사용자 프로필"""
    user_id: str
    category_scores: Dict[str, float] = field(default_factory=lambda: {})
    price_preference: Dict[str, float] = field(default_factory=lambda: {
        "under_5000": 0.3,
        "5000_7000": 0.4,
        "7000_9500": 0.3
    })
    emotion_history: List[str] = field(default_factory=list)
    group_size_history: List[int] = field(default_factory=list)
    interaction_count: int = 0
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 학습 통계
    click_history: List[Dict] = field(default_factory=list)
    order_history: List[Dict] = field(default_factory=list)
    
    # 10대 특화 속성
    school_area: Optional[str] = None
    favorite_trends: List[str] = field(default_factory=list)
    quest_progress: Dict[str, int] = field(default_factory=dict)
    monthly_budget: int = 285000  # 급식카드 월 예산
    daily_budget_left: int = 9500


class TeenPersonalizer:
    """11개 피처 통합 실시간 개인화 엔진"""
    
    def __init__(self, profile_dir: str = "outputs/user_profiles/teen"):
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        # 하이퍼파라미터
        self.learning_rate = 0.4  # EMA 학습률 (부정 피드백 빠른 반영 위해 상향)
        self.exploration_rate = 0.25  # MAB epsilon (다양성 증가를 위해 25%로 상향)
        
        # 피처 가중치 (100점 만점) - 균형잡힌 가중치
        self.feature_weights = {
            "personal_preference": 5,  # 35 -> 5로 대폭 하향 (과도한 개인화 방지)
            "realtime_context": 20,
            "emotion_mood": 15,
            "social_trend": 15,
            "nutrition": 10,
            "price_value": 5,
            "group_size": 3,
            "budget_pacing": 3,
            "study_context": 2,
            "condition_care": 2,
            "explicit_intent": 20  # 명시적 요청 가중치 추가
        }
        
        # 메모리 캐시
        self.profiles_cache = {}
        
        # 최근 추천 히스토리 (다양성 확보용)
        self.recent_recommendations = {}  # user_id -> [shop_ids]
        
        # 트렌드 데이터 (시간대별 동적 변경)
        hour = datetime.now().hour
        if 6 <= hour < 11:  # 아침
            self.school_trends = {
                "강남고": ["카페", "빵", "샌드위치"],
                "서초고": ["토스트", "죽", "김밥"],
                "default": ["카페", "빵", "편의점"]
            }
        elif 11 <= hour < 14:  # 점심
            self.school_trends = {
                "강남고": ["한식", "중식", "분식"],
                "서초고": ["도시락", "일식", "한식"],
                "default": ["한식", "도시락", "분식"]
            }
        else:  # 저녁/야식
            self.school_trends = {
                "강남고": ["치킨", "떡볶이", "마라탕"],
                "서초고": ["버거", "파스타", "초밥"],
                "default": ["치킨", "피자", "떡볶이"]
            }
        
        logger.info("TeenPersonalizer 초기화 완료")
    
    def get_profile(self, user_id: str) -> TeenProfile:
        """사용자 프로필 로드 또는 생성"""
        if user_id in self.profiles_cache:
            return self.profiles_cache[user_id]
        
        profile_path = self.profile_dir / f"{user_id}_teen.json"
        
        if profile_path.exists():
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    profile = TeenProfile(**data)
            except:
                profile = TeenProfile(user_id=user_id)
        else:
            profile = TeenProfile(user_id=user_id)
            # 페르소나별 기본 프로필 설정
            if user_id == 'tae_hoon':
                profile.interaction_count = 5  # Cold Start 회피
                profile.school_area = '강남고'
            elif user_id == 'min_ho':
                profile.interaction_count = 5
                profile.school_area = '서초고'
            elif user_id == 'myeong_bin':
                profile.interaction_count = 5
                profile.school_area = 'default'
        
        self.profiles_cache[user_id] = profile
        return profile
    
    def save_profile(self, profile: TeenProfile):
        """프로필 저장"""
        profile_path = self.profile_dir / f"{profile.user_id}_teen.json"
        profile.last_updated = datetime.now().isoformat()
        
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(profile.__dict__, f, ensure_ascii=False, indent=2)
    
    def load_profile(self, user_id: str, profile_data: Dict):
        """외부에서 프로필 데이터 로드"""
        # TeenProfile 객체 생성
        profile = TeenProfile(user_id=user_id)
        
        # 프로필 데이터 매핑
        if 'category_scores' in profile_data:
            profile.category_scores = profile_data['category_scores']
        else:
            # 기본 카테고리 점수 초기화 (페르소나별 차별화)
            if user_id == 'tae_hoon':
                profile.category_scores = {
                    '치킨': 0.9, '피자': 0.8, '햄버거': 0.7, '편의점': 0.85,
                    '한식': 0.3, '중식': 0.4, '일식': 0.2, '양식': 0.6,
                    '분식': 0.7, '카페': 0.5, '디저트': 0.6
                }
            elif user_id == 'min_ho':
                profile.category_scores = {
                    '한식': 0.9, '중식': 0.6, '일식': 0.5, '양식': 0.4,
                    '치킨': 0.6, '피자': 0.4, '분식': 0.8, '김밥': 0.85,
                    '카페': 0.3, '디저트': 0.2, '편의점': 0.3
                }
            elif user_id == 'myeong_bin':
                profile.category_scores = {
                    '한식': 0.8, '샐러드': 0.9, '죽': 0.85, '도시락': 0.7,
                    '일식': 0.6, '양식': 0.7, '카페': 0.5, '디저트': 0.3,
                    '치킨': 0.3, '피자': 0.2, '편의점': 0.2
                }
            else:
                # 기본값
                profile.category_scores = {}
        
        if 'price_patterns' in profile_data:
            if 'avg_spending' in profile_data['price_patterns']:
                avg = profile_data['price_patterns']['avg_spending']
                if avg < 5000:
                    profile.price_preference = {"under_5000": 0.7, "5000_7000": 0.2, "7000_9500": 0.1}
                elif avg < 7000:
                    profile.price_preference = {"under_5000": 0.2, "5000_7000": 0.6, "7000_9500": 0.2}
                else:
                    profile.price_preference = {"under_5000": 0.1, "5000_7000": 0.3, "7000_9500": 0.6}
        
        if 'interaction_count' in profile_data:
            profile.interaction_count = profile_data['interaction_count']
        
        if 'meal_card' in profile_data:
            profile.monthly_budget = profile_data['meal_card'].get('balance', 285000)
            profile.daily_budget_left = profile_data['meal_card'].get('daily_limit', 9500)
        
        # 캐시에 저장
        self.profiles_cache[user_id] = profile
        logger.info(f"프로필 로드 완료: {user_id}, 카테고리 점수: {profile.category_scores}")
    
    def rank_candidates(
        self, 
        candidates: List[Dict],
        extracted_info: Any,
        user_profile: Dict,
        context: Optional[Dict] = None
    ) -> List[Tuple[Dict, float]]:
        """11개 피처 기반 후보 랭킹"""
        
        user_id = user_profile.get('user_id', 'guest')
        profile = self.get_profile(user_id)
        
        # 컨텍스트 준비
        if context is None:
            context = self._prepare_context(extracted_info)
        
        # Cold Start 처리
        if profile.interaction_count < 3:
            return self._cold_start_ranking(candidates, context, profile)
        
        # Multi-Armed Bandit - 더 지능적인 Exploration
        if random.random() < self.exploration_rate:
            # Exploration: 기존 점수 + 랜덤 요소로 탐색
            logger.info(f"MAB Exploration mode for user {user_id}")
            scored_candidates = []
            for shop in candidates:
                # 기본 점수 계산
                base_score = self._calculate_shop_score(shop, profile, context, extracted_info)
                # Exploration을 위한 더 큰 랜덤 노이즈 (베타 분포 사용)
                exploration_factor = random.betavariate(2, 2)  # 0~1 사이 베타 분포
                final_score = base_score * (0.5 + exploration_factor)  # 0.5~1.5배 변동
                scored_candidates.append((shop, final_score))
            
            # 랜덤화된 점수로 정렬
            scored_candidates.sort(key=lambda x: x[1], reverse=True)
            return scored_candidates[:3]
        
        # Exploitation: 11개 피처 스코어링 (약간의 노이즈 추가)
        scored_candidates = []
        for shop in candidates:
            base_score = self._calculate_shop_score(shop, profile, context, extracted_info)
            # 점수가 비슷한 가게들을 구분하기 위해 작은 노이즈 추가
            noise = random.uniform(-2, 2)  # ±2점 랜덤 변동
            final_score = base_score + noise
            scored_candidates.append((shop, final_score))
        
        # 상위 3개 선정
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        # 최근 추천 히스토리 업데이트
        if user_id not in self.recent_recommendations:
            self.recent_recommendations[user_id] = []
        
        # 상위 3개의 shop_id 저장
        for shop, _ in scored_candidates[:3]:
            shop_id = shop.get('shop_id')
            if shop_id and shop_id not in self.recent_recommendations[user_id]:
                self.recent_recommendations[user_id].append(shop_id)
        
        # 최근 10개만 유지
        self.recent_recommendations[user_id] = self.recent_recommendations[user_id][-10:]
        
        # 로깅
        logger.info(f"TeenPersonalizer ranked {len(candidates)} shops for user {user_id}")
        for i, (shop, score) in enumerate(scored_candidates[:3]):
            # shop_name 또는 name 키 확인
            shop_name = shop.get('shop_name') or shop.get('name', 'Unknown')
            logger.info(f"  #{i+1}: {shop_name} (score: {score:.2f})")
        
        return scored_candidates[:3]
    
    def _calculate_shop_score(
        self, 
        shop: Dict,
        profile: TeenProfile,
        context: Dict,
        extracted_info: Any
    ) -> float:
        """11개 피처 기반 점수 계산"""
        
        scores = {}
        category = shop.get('category', '기타')
        
        # 0. 명시적 의도 점수 (explicit_intent) - 사용자가 특정 카테고리 요청 시
        explicit_score = 0.0
        if hasattr(extracted_info, 'entities') and extracted_info.entities:
            # entities가 iterable인지 확인
            entities_list = extracted_info.entities if hasattr(extracted_info.entities, '__iter__') else []
            for entity in entities_list:
                # food_category 엔티티 확인
                if entity.type == 'food_category':
                    requested_category = entity.value
                    # 요청한 카테고리와 일치하면 보너스
                    if requested_category == category:
                        explicit_score = 1.0
                    # 베이커리 관련 동의어 처리
                    elif requested_category in ['빵', '베이커리', '빵집'] and category == '베이커리':
                        explicit_score = 1.0
                    break
        
        # 또한 context에서 original_query 확인 (Context Enricher에서 전달)
        if explicit_score == 0 and context.get('original_query'):
            query = context['original_query'].lower()
            if ('빵' in query or '베이커리' in query) and category == '베이커리':
                explicit_score = 1.0
            elif ('떡볶이' in query or '분식' in query) and category == '분식':
                explicit_score = 1.0
            elif ('치킨' in query) and category == '치킨':
                explicit_score = 1.0
            elif ('피자' in query) and category == '피자':
                explicit_score = 1.0
            elif ('한식' in query) and category == '한식':
                explicit_score = 1.0
        
        scores['explicit_intent'] = explicit_score * self.feature_weights.get('explicit_intent', 20)
        
        # 1. 개인 선호도 (5점으로 감소) - 카테고리별 차별화
        # 카테고리 점수가 없으면 기본값 + 노이즈로 차별화
        if category in profile.category_scores:
            personal_score = profile.category_scores[category]
        else:
            # 카테고리별 기본 점수 + 작은 랜덤 요소
            import random
            # 카테고리별 기본 점수 범위 확대 (0.3~0.8)
            category_defaults = {
                '치킨': 0.7, '피자': 0.65, '햄버거': 0.6, '한식': 0.75,
                '중식': 0.55, '일식': 0.5, '양식': 0.55, '분식': 0.7,
                '카페': 0.4, '디저트': 0.35, '편의점': 0.6, '샐러드': 0.45,
                '죽': 0.5, '김밥': 0.65, '도시락': 0.6,
                '베이커리': 0.65  # 베이커리 점수 상향 (0.5 -> 0.65)
            }
            base = category_defaults.get(category, 0.4)
            # 더 큰 변동성으로 다양성 확보
            personal_score = base + random.uniform(-0.2, 0.2)  # ±0.2로 확대
            profile.category_scores[category] = personal_score  # 캐시에 저장
        scores['personal_preference'] = personal_score * self.feature_weights['personal_preference']
        
        # 2. 실시간 상황 (20점)
        context_score = self._calculate_context_score(shop, context)
        scores['realtime_context'] = context_score * self.feature_weights['realtime_context']
        
        # 3. 감정/기분 (15점)
        emotion_score = self._calculate_emotion_score(shop, context.get('emotion'))
        scores['emotion_mood'] = emotion_score * self.feature_weights['emotion_mood']
        
        # 4. 소셜/트렌드 (15점)
        trend_score = self._calculate_trend_score(shop, profile)
        scores['social_trend'] = trend_score * self.feature_weights['social_trend']
        
        # 5. 영양 (10점)
        nutrition_score = self._calculate_nutrition_score(shop, context)
        scores['nutrition'] = nutrition_score * self.feature_weights['nutrition']
        
        # 6. 가성비 (5점)
        price_score = self._calculate_price_value_score(shop, profile)
        scores['price_value'] = price_score * self.feature_weights['price_value']
        
        # 7. 그룹 크기 적합성 (3점) - 차별화
        group_score = self._calculate_group_score(shop, context)
        scores['group_size'] = group_score * self.feature_weights['group_size']
        
        # 8. 예산 페이싱 (3점)
        scores['budget_pacing'] = self._calculate_budget_score(shop, profile) * self.feature_weights['budget_pacing']
        
        # 9. 학습 컨텍스트 (2점) - 시험기간/평일 차별화
        study_score = self._calculate_study_context_score(shop, context)
        scores['study_context'] = study_score * self.feature_weights['study_context']
        
        # 10. 컨디션 케어 (2점)
        condition_score = self._calculate_condition_score(shop, context)
        scores['condition_care'] = condition_score * self.feature_weights['condition_care']
        
        # 11. 거리/위치 점수 추가 (중요!)
        location_score = self._calculate_location_score(shop, context)
        scores['location'] = location_score * 10  # 10점 배점
        
        # 총점 계산
        total_score = sum(scores.values())
        
        # 최근 추천 페널티 적용 (더 강화)
        shop_id = shop.get('shop_id')
        user_id = profile.user_id
        if user_id in self.recent_recommendations:
            if shop_id in self.recent_recommendations[user_id]:
                # 최근 추천된 가게는 70% 페널티 (기존 40%에서 강화)
                total_score *= 0.3
                logger.debug(f"최근 추천 강한 페널티 적용: shop_id={shop_id}")
        
        # 로깅 (디버깅용)
        shop_name = shop.get('shop_name', shop.get('name', 'Unknown'))
        logger.debug(f"Shop: {shop_name} ({category}) - Total: {total_score:.2f}")
        logger.debug(f"  Details: {', '.join([f'{k}: {v:.2f}' for k, v in scores.items()])}")
        
        return total_score
    
    def _calculate_context_score(self, shop: Dict, context: Dict) -> float:
        """실시간 상황 점수 - Context Enrich 정보 활용"""
        score = 0.5
        
        # 시간대별 보정 - Context Enrich의 time_context 활용
        time_context = context.get('time_context', {})
        time_period = time_context.get('period', None)
        
        if time_period == 'breakfast':  # 아침 (6-10시)
            if shop.get('category') in ['카페', '베이커리', '죽', '샌드위치']:
                score += 0.4
            elif shop.get('category') in ['한식'] and '국밥' in shop.get('menu_summary', ''):
                score += 0.3
            elif shop.get('category') in ['치킨', '피자', '야식']:  # 아침에 부적합
                score -= 0.3
        elif time_period == 'lunch':  # 점심 (10-14시)
            if shop.get('category') in ['한식', '중식', '일식', '분식']:
                score += 0.3
        elif time_period == 'dinner':  # 저녁 (17-21시)
            if shop.get('category') in ['한식', '양식', '중식', '치킨']:
                score += 0.3
        elif time_period == 'late_night':  # 야식 (21시 이후)
            if shop.get('category') in ['치킨', '족발', '편의점', '야식']:
                score += 0.4
        else:  # 시간 정보 없으면 기존 방식
            hour = datetime.now().hour
            if 11 <= hour <= 13:
                if shop.get('category') in ['한식', '중식', '일식']:
                    score += 0.2
            elif 17 <= hour <= 19:
                if shop.get('category') in ['치킨', '피자', '야식']:
                    score += 0.2
        
        # 날씨 보정 - Context Enrich의 weather 정보 활용
        weather_info = context.get('weather', {})
        weather_condition = weather_info.get('condition', '')
        temperature = weather_info.get('temp', 20)
        category = shop.get('category', '').lower()
        menu_summary = shop.get('menu_summary', '').lower()
        
        # 비/눈 오는 날
        if weather_condition in ['rain', 'Rain', '비', 'snow', 'Snow', '눈']:
            if any(w in category or w in menu_summary for w in ['국물', '국밥', '탕', '전골', '찌개', '라면']):
                score += 0.4
            elif any(w in category for w in ['샐러드', '빙수', '아이스']):
                score -= 0.3
        
        # 추운 날 (5도 이하)
        elif temperature <= 5:
            if any(w in category or w in menu_summary for w in ['국물', '국밥', '탕', '전골', '찌개', '우동']):
                score += 0.35
            elif any(w in category or w in menu_summary for w in ['냉면', '빙수', '아이스', '샐러드']):
                score -= 0.4
        
        # 더운 날 (28도 이상)
        elif temperature >= 28:
            if any(w in category or w in menu_summary for w in ['냉면', '샐러드', '빙수', '아이스']):
                score += 0.35
            elif any(w in category or w in menu_summary for w in ['탕', '전골', '찌개']):
                score -= 0.2
        
        return min(max(score, 0.0), 1.0)  # 0-1 범위로 제한
    
    def _calculate_group_score(self, shop: Dict, context: Dict) -> float:
        """그룹 크기 적합성 점수"""
        group_size = context.get('group_size', 1)
        category = shop.get('category', '')
        
        # 그룹 크기별 적합한 카테고리
        if group_size == 1:  # 혼자
            if category in ['도시락', '김밥', '편의점', '카페']:
                return 0.8
            elif category in ['치킨', '피자']:  # 혼자 먹기엔 많은 음식
                return 0.3
        elif group_size >= 3:  # 단체
            if category in ['치킨', '피자', '한식', '중식']:
                return 0.9
            elif category in ['도시락', '김밥']:
                return 0.4
        
        return 0.5
    
    def _calculate_study_context_score(self, shop: Dict, context: Dict) -> float:
        """학습 컨텍스트 점수 (시험기간, 평일/주말)"""
        import datetime
        day_of_week = datetime.datetime.now().weekday()
        category = shop.get('category', '')
        
        # 평일 (0-4): 빠른 식사 선호
        if day_of_week < 5:
            if category in ['김밥', '도시락', '편의점', '분식']:
                return 0.7
            elif category in ['한식', '중식']:  # 시간 걸리는 식사
                return 0.3
        # 주말: 여유있는 식사 가능
        else:
            if category in ['한식', '양식', '일식', '중식']:
                return 0.7
        
        return 0.5
    
    def _calculate_condition_score(self, shop: Dict, context: Dict) -> float:
        """컨디션 케어 점수"""
        # 감정이나 날씨로 컨디션 추정
        emotion = context.get('emotion')
        weather = context.get('weather', {})
        category = shop.get('category', '')
        
        # 피곤하거나 아플 때
        if emotion in ['😴', '🤒']:
            if category in ['죽', '스프', '도시락']:
                return 0.9
            elif category in ['치킨', '피자', '햄버거']:  # 무거운 음식
                return 0.2
        
        # 추운 날씨
        if weather.get('temp', 20) < 10:
            if category in ['한식', '중식', '일식'] and '국' in shop.get('menu_summary', ''):
                return 0.8
        
        return 0.5
    
    def _calculate_location_score(self, shop: Dict, context: Dict) -> float:
        """위치/거리 기반 점수"""
        # Context에서 사용자 위치 정보 확인
        user_location = context.get('location', {})
        
        # 사용자 좌표
        user_lat = context.get('user_latitude') or user_location.get('latitude')
        user_lng = context.get('user_longitude') or user_location.get('longitude')
        
        # 가게 좌표
        shop_lat = shop.get('latitude')
        shop_lng = shop.get('longitude')
        
        # 좌표가 모두 있으면 실제 거리 계산
        if user_lat and user_lng and shop_lat and shop_lng:
            try:
                from src.utils.location_utils import calculate_distance
                distance_km = calculate_distance(user_lat, user_lng, shop_lat, shop_lng)
                
                # 거리별 점수 (가까울수록 높은 점수)
                if distance_km <= 0.5:
                    return 1.0  # 500m 이내
                elif distance_km <= 1.0:
                    return 0.8  # 1km 이내
                elif distance_km <= 2.0:
                    return 0.6  # 2km 이내
                elif distance_km <= 3.0:
                    return 0.4  # 3km 이내
                elif distance_km <= 5.0:
                    return 0.2  # 5km 이내
                else:
                    return 0.0  # 5km 초과는 0점
                    
            except Exception as e:
                logger.debug(f"거리 계산 실패: {e}")
        
        # 좌표가 없으면 주소 텍스트 매칭
        user_district = user_location.get('name', '')
        shop_address = shop.get('address', '')
        
        if user_district and user_district in shop_address:
            return 0.7  # 같은 구/동
        elif '서울' in user_district and '서울' in shop_address:
            return 0.3  # 같은 시
        elif '경기' in user_district and '경기' in shop_address:
            return 0.3  # 같은 도
        
        return 0.1  # 기본 점수 (거리 정보 없음)
    
    def _calculate_emotion_score(self, shop: Dict, emotion: Optional[str]) -> float:
        """감정 기반 점수"""
        if not emotion:
            return 0.5
        
        emotion_food_map = {
            "😊": ["치킨", "피자", "햄버거"],  # 행복
            "😢": ["떡볶이", "마라탕", "짬뽕"],  # 슬픔 -> 매운음식
            "😡": ["매운탕", "불족발", "마라"],  # 화남 -> 더 매운음식
            "😴": ["커피", "에너지드링크", "당"],  # 피곤 -> 카페인/당
            "🤒": ["죽", "스프", "따뜻한"],  # 아픔 -> 부드러운음식
        }
        
        preferred_foods = emotion_food_map.get(emotion, [])
        
        # shop_name 또는 name 키 확인
        shop_name = shop.get('shop_name') or shop.get('name', '')
        for food in preferred_foods:
            if food in shop_name or food in shop.get('menu_summary', ''):
                return 0.9
        
        return 0.5
    
    def _calculate_trend_score(self, shop: Dict, profile: TeenProfile) -> float:
        """소셜/트렌드 점수"""
        school = profile.school_area or "default"
        trends = self.school_trends.get(school, self.school_trends["default"])
        
        category = shop.get('category', '')
        if category in trends:
            rank = trends.index(category)
            return 1.0 - (rank * 0.2)  # 1위: 1.0, 2위: 0.8, 3위: 0.6
        
        # 트렌드에 없는 카테고리도 차별화
        import random
        return 0.3 + random.uniform(0, 0.2)  # 0.3~0.5 범위
    
    def _calculate_nutrition_score(self, shop: Dict, context: Dict) -> float:
        """영양 점수"""
        category = shop.get('category', '').lower()
        shop_name = shop.get('shop_name', shop.get('name', '')).lower()
        menu = shop.get('menu_summary', '').lower()
        
        # 카테고리별 영양 점수
        nutrition_by_category = {
            '한식': 0.8,  # 균형잡힌 영양
            '샐러드': 0.9,  # 비타민, 섬유질
            '치킨': 0.6,  # 단백질 높지만 기름진
            '피자': 0.4,  # 고칼로리
            '햄버거': 0.45,  # 패스트푸드
            '죽': 0.7,  # 소화 좋고 영양
            '도시락': 0.75,  # 균형잡힌 구성
            '분식': 0.5,  # 탄수화물 위주
            '편의점': 0.3,  # 가공식품
            '디저트': 0.2,  # 당분 높음
            '카페': 0.25  # 영양가 낮음
        }
        
        score = nutrition_by_category.get(category, 0.5)
        
        # 특정 키워드 보너스/페널티
        if any(w in shop_name or w in menu for w in ['단백질', '고기', '닭', '소고기', '돼지']):
            score += 0.1  # 단백질 보너스
        if any(w in shop_name or w in menu for w in ['야채', '채소', '샐러드', '비빔']):
            score += 0.1  # 채소 보너스
        if any(w in shop_name or w in menu for w in ['튀김', '프라이드', '기름']):
            score -= 0.1  # 기름진 음식 페널티
        
        return min(max(score, 0.0), 1.0)
    
    def _calculate_price_value_score(self, shop: Dict, profile: TeenProfile) -> float:
        """가성비 점수"""
        # shop에서 가격 정보 추출 (여러 필드 체크)
        price = shop.get('price_range', shop.get('price', shop.get('avg_price', 8000)))
        
        # 문자열이면 숫자로 변환 시도
        if isinstance(price, str):
            try:
                price = int(price.replace(',', '').replace('원', ''))
            except:
                price = 8000  # 기본값
        
        # 프로필의 가격 선호도와 매칭
        if price <= 5000:
            score = profile.price_preference.get('under_5000', 0.3)
        elif price <= 7000:
            score = profile.price_preference.get('5000_7000', 0.4)
        elif price <= 9500:
            score = profile.price_preference.get('7000_9500', 0.3)
        else:
            score = 0.1  # 한도 초과는 낮은 점수
        
        # 급식카드 한도 고려 보너스
        if price <= profile.daily_budget_left:
            score += 0.2
        
        return min(score, 1.0)
    
    def _calculate_budget_score(self, shop: Dict, profile: TeenProfile) -> float:
        """예산 페이싱 점수"""
        daily_left = profile.daily_budget_left
        price = shop.get('price_range', 10000)
        
        if price <= daily_left:
            return 1.0
        else:
            return 0.3
    
    def _cold_start_ranking(
        self,
        candidates: List[Dict],
        context: Dict,
        profile: TeenProfile
    ) -> List[Tuple[Dict, float]]:
        """Cold Start 사용자를 위한 인기도 기반 랭킹"""
        logger.info(f"Cold start ranking for user {profile.user_id}")
        
        # 인기도 + 가격 기반 랭킹
        scored = []
        for shop in candidates:
            score = 0.5
            
            # 가격 적정성
            if shop.get('price_range', 10000) <= 9500:
                score += 0.3
            
            # 인기 카테고리
            if shop.get('category') in ['치킨', '피자', '떡볶이']:
                score += 0.2
            
            scored.append((shop, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:3]
    
    def update_from_interaction(
        self,
        user_id: str,
        shop_id: int,
        interaction_type: str,  # 'view', 'click', 'order', 'like'
        metadata: Optional[Dict] = None
    ):
        """EMA 기반 실시간 프로필 업데이트"""
        profile = self.get_profile(user_id)
        
        # 상호작용 가중치
        weights = {
            'view': 0.1,
            'click': 0.3,
            'order': 1.0,
            'like': 0.7,
            'dislike': -0.8  # 부정 피드백 가중치 강화
        }
        
        weight = weights.get(interaction_type, 0.1)
        
        # 카테고리 점수 업데이트 (EMA)
        if metadata and 'category' in metadata:
            category = metadata['category']
            old_score = profile.category_scores.get(category, 0.5)
            new_score = self.learning_rate * weight + (1 - self.learning_rate) * old_score
            profile.category_scores[category] = max(0, min(1, new_score))  # 0~1 클리핑
        
        # 상호작용 기록
        interaction_log = {
            'timestamp': datetime.now().isoformat(),
            'shop_id': shop_id,
            'type': interaction_type,
            'metadata': metadata
        }
        
        if interaction_type in ['click', 'order']:
            profile.click_history.append(interaction_log)
            profile.click_history = profile.click_history[-50:]  # 최근 50개만 유지
        
        if interaction_type == 'order':
            profile.order_history.append(interaction_log)
            profile.order_history = profile.order_history[-20:]  # 최근 20개만 유지
        
        # 상호작용 카운트 증가
        profile.interaction_count += 1
        
        # 프로필 저장
        self.save_profile(profile)
        
        logger.info(
            f"Profile updated for {user_id}: "
            f"{interaction_type} on shop {shop_id}, "
            f"category scores: {profile.category_scores}"
        )
    
    def _prepare_context(self, extracted_info: Any) -> Dict:
        """컨텍스트 정보 준비"""
        context = {
            'time': datetime.now().isoformat(),
            'hour': datetime.now().hour,
            'day_of_week': datetime.now().weekday(),
            'weather': 'sunny',  # TODO: 실제 날씨 API 연동
            'emotion': None,
            'original_query': getattr(extracted_info, 'text', '')  # 원본 쿼리 추가
        }
        
        # 엔티티에서 감정 추출
        if hasattr(extracted_info, 'entities') and extracted_info.entities:
            # entities가 iterable인지 확인
            entities_list = extracted_info.entities if hasattr(extracted_info.entities, '__iter__') else []
            for entity in entities_list:
                if hasattr(entity, 'type') and entity.type == 'emotion':
                    context['emotion'] = entity.value
                    break
        
        return context
    
    def get_personalization_level(self, user_id: str) -> str:
        """개인화 수준 반환"""
        profile = self.get_profile(user_id)
        count = profile.interaction_count
        
        if count == 0:
            return "0% (Cold Start)"
        elif count <= 2:
            return "20% (초기 학습)"
        elif count <= 4:
            return "60% (학습 중)"
        else:
            return "100% (완전 개인화)"


# 싱글톤 인스턴스
_personalizer_instance = None

def get_personalizer() -> TeenPersonalizer:
    """싱글톤 TeenPersonalizer 인스턴스 반환"""
    global _personalizer_instance
    if _personalizer_instance is None:
        _personalizer_instance = TeenPersonalizer()
    return _personalizer_instance