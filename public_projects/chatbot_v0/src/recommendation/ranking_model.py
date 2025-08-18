"""
Layer 2: Wide & Deep 개인화 랭킹 모델
Layer 1에서 생성된 후보들을 사용자별로 개인화하여 최종 순위 결정
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RankingModelConfig:
    """Wide & Deep 모델 설정"""
    
    # Wide 파트 설정
    wide_feature_size: int = 50  # Wide 파트 입력 특성 수
    
    # Deep 파트 설정  
    embedding_dim: int = 32      # 임베딩 차원
    hidden_dims: List[int] = None  # Hidden layer 차원들
    dropout_rate: float = 0.3    # 드롭아웃 비율
    
    # 훈련 설정
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 10
    
    # 특성 관련
    max_user_id: int = 10000     # 최대 사용자 ID
    max_shop_id: int = 1000      # 최대 매장 ID
    max_category_id: int = 50    # 최대 카테고리 ID
    
    def __post_init__(self):
        if self.hidden_dims is None:
            self.hidden_dims = [128, 64, 32]


class WideAndDeepRankingModel(nn.Module):
    """Wide & Deep Architecture for Personalized Ranking"""
    
    def __init__(self, config: RankingModelConfig):
        super().__init__()
        self.config = config
        
        # Wide 파트 - 선형 결합
        self.wide = nn.Linear(config.wide_feature_size, 1)
        
        # Deep 파트 - 임베딩 + DNN
        self._build_deep_part()
        
        # 최종 출력 결합
        deep_output_dim = config.hidden_dims[-1]
        self.final = nn.Linear(deep_output_dim + 1, 1)  # Wide(1) + Deep(last_dim)
        
        # 초기화
        self._initialize_weights()
        
        logger.info(f"Wide & Deep 모델 초기화 완료: Wide({config.wide_feature_size}) + Deep({deep_output_dim})")
    
    def _build_deep_part(self):
        """Deep 파트 구축"""
        config = self.config
        
        # 임베딩 레이어들
        self.user_embedding = nn.Embedding(config.max_user_id, config.embedding_dim)
        self.shop_embedding = nn.Embedding(config.max_shop_id, config.embedding_dim)
        self.category_embedding = nn.Embedding(config.max_category_id, config.embedding_dim)
        
        # DNN 레이어들
        # 입력: user_emb + shop_emb + category_emb + numerical_features
        deep_input_dim = config.embedding_dim * 3 + 10  # 10개 수치형 특성
        
        layers = []
        prev_dim = deep_input_dim
        
        for hidden_dim in config.hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(config.dropout_rate)
            ])
            prev_dim = hidden_dim
        
        self.deep_layers = nn.Sequential(*layers)
    
    def _initialize_weights(self):
        """가중치 초기화"""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, mean=0, std=0.1)
    
    def forward(self, wide_features: torch.Tensor, 
                user_ids: torch.Tensor,
                shop_ids: torch.Tensor, 
                category_ids: torch.Tensor,
                numerical_features: torch.Tensor) -> torch.Tensor:
        """
        Forward pass
        
        Args:
            wide_features: Wide 파트 입력 특성 [batch_size, wide_feature_size]
            user_ids: 사용자 ID [batch_size]
            shop_ids: 매장 ID [batch_size] 
            category_ids: 카테고리 ID [batch_size]
            numerical_features: 수치형 특성 [batch_size, 10]
            
        Returns:
            랭킹 점수 [batch_size, 1]
        """
        
        # Wide 파트
        wide_output = self.wide(wide_features)  # [batch_size, 1]
        
        # Deep 파트
        user_emb = self.user_embedding(user_ids)      # [batch_size, embedding_dim]
        shop_emb = self.shop_embedding(shop_ids)      # [batch_size, embedding_dim]
        category_emb = self.category_embedding(category_ids)  # [batch_size, embedding_dim]
        
        # 임베딩과 수치형 특성 결합
        deep_input = torch.cat([
            user_emb, shop_emb, category_emb, numerical_features
        ], dim=1)  # [batch_size, embedding_dim*3 + 10]
        
        deep_output = self.deep_layers(deep_input)  # [batch_size, hidden_dims[-1]]
        
        # Wide + Deep 결합
        combined = torch.cat([wide_output, deep_output], dim=1)  # [batch_size, 1 + hidden_dims[-1]]
        final_output = self.final(combined)  # [batch_size, 1]
        
        return torch.sigmoid(final_output)  # 0~1 사이 점수


class PersonalizedRanker:
    """개인화 랭킹 시스템"""
    
    def __init__(self, config: Optional[RankingModelConfig] = None):
        self.config = config or RankingModelConfig()
        self.model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # 특성 매핑 딕셔너리 (ID 변환용)
        self.user_id_map = {}
        self.shop_id_map = {}
        self.category_id_map = {}
        
        logger.info(f"PersonalizedRanker 초기화 완료 (Device: {self.device})")
    
    def initialize_model(self):
        """모델 초기화"""
        self.model = WideAndDeepRankingModel(self.config).to(self.device)
        logger.info("Wide & Deep 모델 생성 완료")
    
    def rank_candidates(self, 
                       candidates: List[Dict[str, Any]], 
                       user_profile: Dict[str, Any],
                       context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Layer 1 후보들을 개인화하여 재순위화
        
        Args:
            candidates: Layer 1에서 생성된 후보 리스트
            user_profile: 사용자 프로필 정보
            context: 상황 정보 (시간, 위치 등)
            
        Returns:
            개인화된 순위의 후보 리스트
        """
        if not candidates:
            return []
        
        if self.model is None:
            # 모델이 없으면 규칙 기반 랭킹 사용
            return self._rule_based_ranking(candidates, user_profile, context)
        
        # 딥러닝 모델 기반 랭킹
        return self._model_based_ranking(candidates, user_profile, context)
    
    def _rule_based_ranking(self, 
                           candidates: List[Dict[str, Any]], 
                           user_profile: Dict[str, Any],
                           context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        규칙 기반 랭킹 (모델 없을 때 사용)
        """
        logger.info("규칙 기반 랭킹 수행")
        
        for candidate in candidates:
            # 기본 점수 (Layer 1에서 가장 높은 점수 사용)
            base_score = max([
                candidate.get('collaborative_score', 0),
                candidate.get('content_score', 0), 
                candidate.get('context_score', 0),
                candidate.get('base_score', 0)
            ])
            
            personalization_bonus = 0
            
            # 선호 카테고리 보너스
            preferred_categories = user_profile.get('preferred_categories', [])
            if candidate.get('category') in preferred_categories:
                personalization_bonus += 10
                
            # 예산 적합성 보너스
            avg_budget = user_profile.get('average_budget', 0)
            if avg_budget > 0:
                shop_price_range = candidate.get('price_range', 'medium')
                if (avg_budget <= 10000 and shop_price_range == 'low') or \
                   (10000 < avg_budget <= 30000 and shop_price_range == 'medium') or \
                   (avg_budget > 30000 and shop_price_range == 'high'):
                    personalization_bonus += 5
            
            # 착한가게 보너스
            if candidate.get('is_good_price', False):
                personalization_bonus += 3
                
            # 거리 페널티 (상황 정보 활용)
            user_location = context.get('user_location', '')
            if user_location and candidate.get('district') != user_location:
                personalization_bonus -= 2
            
            # 최종 점수 계산
            final_score = base_score + personalization_bonus
            candidate['personalized_score'] = final_score
            candidate['personalization_bonus'] = personalization_bonus
            candidate['ranking_method'] = 'rule_based'
        
        # 점수 기준 정렬
        ranked_candidates = sorted(candidates, 
                                 key=lambda x: x['personalized_score'], 
                                 reverse=True)
        
        logger.info(f"규칙 기반 랭킹 완료: {len(ranked_candidates)}개 후보")
        return ranked_candidates
    
    def _model_based_ranking(self,
                           candidates: List[Dict[str, Any]], 
                           user_profile: Dict[str, Any],
                           context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        딥러닝 모델 기반 랭킹
        """
        logger.info("딥러닝 모델 기반 랭킹 수행")
        
        self.model.eval()
        with torch.no_grad():
            # 특성 추출 및 텐서 변환
            features = self._extract_features(candidates, user_profile, context)
            
            # 모델 예측
            scores = self.model(
                features['wide_features'],
                features['user_ids'], 
                features['shop_ids'],
                features['category_ids'],
                features['numerical_features']
            )
            
            # 결과 적용
            scores_np = scores.cpu().numpy().flatten()
            for i, candidate in enumerate(candidates):
                candidate['personalized_score'] = float(scores_np[i])
                candidate['ranking_method'] = 'deep_learning'
        
        # 점수 기준 정렬
        ranked_candidates = sorted(candidates,
                                 key=lambda x: x['personalized_score'],
                                 reverse=True)
        
        logger.info(f"딥러닝 랭킹 완료: {len(ranked_candidates)}개 후보")
        return ranked_candidates
    
    def _extract_features(self, 
                         candidates: List[Dict[str, Any]], 
                         user_profile: Dict[str, Any],
                         context: Dict[str, Any]) -> Dict[str, torch.Tensor]:
        """
        모델 학습/예측용 특성 추출
        """
        batch_size = len(candidates)
        
        # Wide 파트 특성 (Layer 1 점수들 + 기본 특성)
        wide_features = []
        user_ids = []
        shop_ids = []
        category_ids = []
        numerical_features = []
        
        user_id = self._get_or_create_id(user_profile.get('user_id', 'unknown'), 
                                        self.user_id_map, 
                                        self.config.max_user_id)
        
        for candidate in candidates:
            # Wide 특성: Layer 1 점수들을 주요 특성으로 사용
            wide_feat = np.zeros(self.config.wide_feature_size)
            
            # Layer 1 점수들
            wide_feat[0] = candidate.get('collaborative_score', 0)
            wide_feat[1] = candidate.get('content_score', 0)
            wide_feat[2] = candidate.get('context_score', 0)
            wide_feat[3] = candidate.get('base_score', 0)
            
            # 기본 특성들
            wide_feat[4] = 1 if candidate.get('is_good_price', False) else 0
            wide_feat[5] = 1 if candidate.get('category') in user_profile.get('preferred_categories', []) else 0
            # 나머지는 0으로 패딩
            
            wide_features.append(wide_feat)
            
            # ID 특성들
            user_ids.append(user_id)
            shop_ids.append(self._get_or_create_id(candidate['shop_id'], 
                                                 self.shop_id_map, 
                                                 self.config.max_shop_id))
            category_ids.append(self._get_or_create_id(candidate.get('category', 'unknown'),
                                                     self.category_id_map,
                                                     self.config.max_category_id))
            
            # 수치형 특성들
            numerical_feat = np.zeros(10)
            numerical_feat[0] = user_profile.get('average_budget', 0) / 100000  # 정규화
            numerical_feat[1] = len(user_profile.get('favorite_shops', [])) / 10  # 정규화
            # 나머지는 0으로 패딩
            
            numerical_features.append(numerical_feat)
        
        # 텐서 변환
        return {
            'wide_features': torch.FloatTensor(wide_features).to(self.device),
            'user_ids': torch.LongTensor(user_ids).to(self.device),
            'shop_ids': torch.LongTensor(shop_ids).to(self.device), 
            'category_ids': torch.LongTensor(category_ids).to(self.device),
            'numerical_features': torch.FloatTensor(numerical_features).to(self.device)
        }
    
    def _get_or_create_id(self, key: str, id_map: Dict[str, int], max_id: int) -> int:
        """키를 ID로 변환 (없으면 새로 생성)"""
        if key not in id_map:
            if len(id_map) >= max_id - 1:
                return max_id - 1  # 최대값 사용
            id_map[key] = len(id_map) + 1
        return id_map[key]
    
    def get_ranking_explanation(self, 
                               ranked_candidates: List[Dict[str, Any]],
                               top_k: int = 3) -> List[str]:
        """
        랭킹 결과 설명 생성
        """
        explanations = []
        
        for i, candidate in enumerate(ranked_candidates[:top_k]):
            rank = i + 1
            shop_name = candidate['shop_name']
            score = candidate.get('personalized_score', 0)
            method = candidate.get('ranking_method', 'unknown')
            
            explanation = f"{rank}. {shop_name} (점수: {score:.1f}, 방법: {method})"
            
            if method == 'rule_based':
                bonus = candidate.get('personalization_bonus', 0)
                if bonus > 0:
                    explanation += f" - 개인화 보너스: +{bonus}점"
            
            explanations.append(explanation)
        
        return explanations


# 테스트 함수
def test_ranking_model():
    """랭킹 모델 테스트"""
    print("=== Layer 2: Wide & Deep 랭킹 모델 테스트 ===")
    
    # 설정 및 랭커 초기화
    config = RankingModelConfig()
    ranker = PersonalizedRanker(config)
    
    # 테스트용 Layer 1 후보들
    test_candidates = [
        {
            'shop_id': 'shop_1',
            'shop_name': '건강한집',
            'category': '한식',
            'collaborative_score': 8.5,
            'content_score': 7.2,
            'context_score': 6.8,
            'base_score': 7.5,
            'is_good_price': True
        },
        {
            'shop_id': 'shop_2', 
            'shop_name': '맛있는피자',
            'category': '양식',
            'collaborative_score': 7.8,
            'content_score': 8.1,
            'context_score': 7.5,
            'base_score': 8.0,
            'is_good_price': False
        },
        {
            'shop_id': 'shop_3',
            'shop_name': '착한치킨',
            'category': '치킨',
            'collaborative_score': 6.9,
            'content_score': 7.8,
            'context_score': 8.2,
            'base_score': 7.2,
            'is_good_price': True
        }
    ]
    
    # 테스트용 사용자 프로필
    test_user_profile = {
        'user_id': 'test_user',
        'preferred_categories': ['한식', '치킨'],
        'average_budget': 15000,
        'favorite_shops': ['shop_1']
    }
    
    # 테스트용 상황 정보
    test_context = {
        'user_location': '관악구',
        'time_of_day': 'lunch'
    }
    
    # 규칙 기반 랭킹 테스트
    ranked = ranker.rank_candidates(test_candidates, test_user_profile, test_context)
    
    print("\n=== 규칙 기반 랭킹 결과 ===")
    for i, candidate in enumerate(ranked, 1):
        name = candidate['shop_name']
        score = candidate['personalized_score']
        bonus = candidate.get('personalization_bonus', 0)
        print(f"{i}. {name}: {score:.1f}점 (보너스: +{bonus})")
    
    # 설명 생성
    explanations = ranker.get_ranking_explanation(ranked)
    print("\n=== 랭킹 설명 ===")
    for explanation in explanations:
        print(explanation)


if __name__ == "__main__":
    test_ranking_model()