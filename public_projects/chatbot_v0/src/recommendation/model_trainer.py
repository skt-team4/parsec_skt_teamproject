"""
Layer 2: 모델 학습 시스템
Wide & Deep 랭킹 모델의 학습, 평가, 저장/로드 담당
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pickle
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime
from sklearn.metrics import roc_auc_score, accuracy_score, precision_recall_curve
import matplotlib.pyplot as plt

try:
    from .ranking_model import WideAndDeepRankingModel, RankingModelConfig
    from .feature_engineering import FeatureEngineer, FeatureConfig
except ImportError:
    from ranking_model import WideAndDeepRankingModel, RankingModelConfig
    from feature_engineering import FeatureEngineer, FeatureConfig

logger = logging.getLogger(__name__)


class RecommendationDataset(Dataset):
    """추천 모델용 데이터셋"""
    
    def __init__(self, features: Dict[str, np.ndarray], id_mappings: Dict[str, Dict[str, int]]):
        """
        Args:
            features: 특성 딕셔너리 (wide_features, numerical_features, labels 등)
            id_mappings: ID 매핑 딕셔너리 (user_id_map, shop_id_map, category_id_map)
        """
        self.wide_features = torch.FloatTensor(features['wide_features'])
        self.numerical_features = torch.FloatTensor(features['numerical_features'])
        self.labels = torch.FloatTensor(features['labels']) if 'labels' in features else None
        
        # ID 매핑 적용
        self.user_ids = torch.LongTensor([id_mappings['user_id_map'].get(uid, 0) for uid in features['user_ids']])
        self.shop_ids = torch.LongTensor([id_mappings['shop_id_map'].get(sid, 0) for sid in features['shop_ids']]) 
        self.category_ids = torch.LongTensor([id_mappings['category_id_map'].get(cid, 0) for cid in features['category_ids']])
        
        assert len(self.wide_features) == len(self.user_ids), "Feature와 ID 길이 불일치"
        
        logger.info(f"데이터셋 생성 완료: {len(self)} 샘플")
    
    def __len__(self):
        return len(self.wide_features)
    
    def __getitem__(self, idx):
        item = {
            'wide_features': self.wide_features[idx],
            'user_ids': self.user_ids[idx],
            'shop_ids': self.shop_ids[idx],
            'category_ids': self.category_ids[idx],
            'numerical_features': self.numerical_features[idx]
        }
        
        if self.labels is not None:
            item['labels'] = self.labels[idx]
            
        return item


class ModelTrainer:
    """Wide & Deep 모델 학습기"""
    
    def __init__(self, 
                 model_config: Optional[RankingModelConfig] = None,
                 feature_config: Optional[FeatureConfig] = None,
                 save_dir: str = "./outputs/recommendation_models"):
        
        self.model_config = model_config or RankingModelConfig()
        self.feature_config = feature_config or FeatureConfig()
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # 모델 및 유틸리티
        self.model = None
        self.feature_engineer = FeatureEngineer(self.feature_config)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # ID 매핑 (문자열 ID -> 숫자 ID)
        self.id_mappings = {
            'user_id_map': {},
            'shop_id_map': {},
            'category_id_map': {}
        }
        
        # 학습 이력
        self.training_history = {
            'train_loss': [],
            'val_loss': [],
            'train_auc': [],
            'val_auc': []
        }
        
        logger.info(f"ModelTrainer 초기화 완료 (Device: {self.device})")
    
    def prepare_training_data(self, 
                            interaction_data: List[Dict[str, Any]]) -> Tuple[RecommendationDataset, RecommendationDataset]:
        """
        학습 데이터 준비
        
        Args:
            interaction_data: 사용자-매장 상호작용 데이터
                [{"user_profile": {...}, "candidate": {...}, "context": {...}, "clicked": True/False}, ...]
        
        Returns:
            (train_dataset, val_dataset)
        """
        logger.info(f"학습 데이터 준비 시작: {len(interaction_data)} 샘플")
        
        # ID 매핑 구축
        self._build_id_mappings(interaction_data)
        
        # 특성 추출
        all_features = []
        all_labels = []
        
        for interaction in interaction_data:
            user_profile = interaction['user_profile']
            candidate = interaction['candidate']
            context = interaction['context']
            label = 1.0 if interaction.get('clicked', False) else 0.0
            
            # 특성 추출
            features = self.feature_engineer.create_training_features(
                [candidate], user_profile, context, [label]
            )
            
            all_features.append(features)
            all_labels.append(label)
        
        # 배치로 결합
        combined_features = self._combine_feature_batches(all_features)
        combined_features['labels'] = np.array(all_labels)
        
        # Train/Validation 분할 (80:20)
        split_idx = int(len(all_labels) * 0.8)
        
        train_features = {k: v[:split_idx] for k, v in combined_features.items()}
        val_features = {k: v[split_idx:] for k, v in combined_features.items()}
        
        # 데이터셋 생성
        train_dataset = RecommendationDataset(train_features, self.id_mappings)
        val_dataset = RecommendationDataset(val_features, self.id_mappings)
        
        logger.info(f"데이터 분할 완료: Train {len(train_dataset)}, Val {len(val_dataset)}")
        return train_dataset, val_dataset
    
    def train_model(self, 
                   train_dataset: RecommendationDataset,
                   val_dataset: Optional[RecommendationDataset] = None,
                   epochs: Optional[int] = None,
                   batch_size: Optional[int] = None) -> Dict[str, Any]:
        """
        모델 학습
        
        Args:
            train_dataset: 학습 데이터셋
            val_dataset: 검증 데이터셋
            epochs: 학습 에폭 수
            batch_size: 배치 크기
            
        Returns:
            학습 결과 딕셔너리
        """
        epochs = epochs or self.model_config.epochs
        batch_size = batch_size or self.model_config.batch_size
        
        logger.info(f"모델 학습 시작: {epochs} 에폭, 배치 크기 {batch_size}")
        
        # 모델 초기화
        self.model = WideAndDeepRankingModel(self.model_config).to(self.device)
        
        # 손실 함수 및 옵티마이저
        criterion = nn.BCELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=self.model_config.learning_rate)
        
        # 데이터 로더
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False) if val_dataset else None
        
        # 학습 루프
        best_val_auc = 0.0
        
        for epoch in range(epochs):
            # 학습
            train_loss, train_auc = self._train_epoch(train_loader, criterion, optimizer)
            self.training_history['train_loss'].append(train_loss)
            self.training_history['train_auc'].append(train_auc)
            
            # 검증
            if val_loader:
                val_loss, val_auc = self._validate_epoch(val_loader, criterion)
                self.training_history['val_loss'].append(val_loss)
                self.training_history['val_auc'].append(val_auc)
                
                # 최고 성능 모델 저장
                if val_auc > best_val_auc:
                    best_val_auc = val_auc
                    self._save_best_model()
                
                logger.info(f"Epoch {epoch+1}/{epochs}: "
                          f"Train Loss={train_loss:.4f}, Train AUC={train_auc:.4f}, "
                          f"Val Loss={val_loss:.4f}, Val AUC={val_auc:.4f}")
            else:
                logger.info(f"Epoch {epoch+1}/{epochs}: "
                          f"Train Loss={train_loss:.4f}, Train AUC={train_auc:.4f}")
        
        # 학습 완료
        training_result = {
            'final_train_loss': self.training_history['train_loss'][-1],
            'final_train_auc': self.training_history['train_auc'][-1],
            'best_val_auc': best_val_auc,
            'total_epochs': epochs,
            'history': self.training_history.copy()
        }
        
        if val_dataset:
            training_result['final_val_loss'] = self.training_history['val_loss'][-1]
            training_result['final_val_auc'] = self.training_history['val_auc'][-1]
        
        logger.info(f"학습 완료! 최고 검증 AUC: {best_val_auc:.4f}")
        return training_result
    
    def _train_epoch(self, train_loader: DataLoader, criterion, optimizer) -> Tuple[float, float]:
        """한 에폭 학습"""
        self.model.train()
        total_loss = 0.0
        all_preds = []
        all_labels = []
        
        for batch in train_loader:
            # 데이터를 디바이스로 이동
            batch = {k: v.to(self.device) for k, v in batch.items()}
            
            # Forward pass
            outputs = self.model(
                batch['wide_features'],
                batch['user_ids'],
                batch['shop_ids'], 
                batch['category_ids'],
                batch['numerical_features']
            ).squeeze()
            
            loss = criterion(outputs, batch['labels'])
            
            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            # 통계 수집
            total_loss += loss.item()
            all_preds.extend(outputs.detach().cpu().numpy())
            all_labels.extend(batch['labels'].detach().cpu().numpy())
        
        avg_loss = total_loss / len(train_loader)
        auc = roc_auc_score(all_labels, all_preds) if len(set(all_labels)) > 1 else 0.0
        
        return avg_loss, auc
    
    def _validate_epoch(self, val_loader: DataLoader, criterion) -> Tuple[float, float]:
        """한 에폭 검증"""
        self.model.eval()
        total_loss = 0.0
        all_preds = []
        all_labels = []
        
        with torch.no_grad():
            for batch in val_loader:
                batch = {k: v.to(self.device) for k, v in batch.items()}
                
                outputs = self.model(
                    batch['wide_features'],
                    batch['user_ids'],
                    batch['shop_ids'],
                    batch['category_ids'], 
                    batch['numerical_features']
                ).squeeze()
                
                loss = criterion(outputs, batch['labels'])
                
                total_loss += loss.item()
                all_preds.extend(outputs.cpu().numpy())
                all_labels.extend(batch['labels'].cpu().numpy())
        
        avg_loss = total_loss / len(val_loader)
        auc = roc_auc_score(all_labels, all_preds) if len(set(all_labels)) > 1 else 0.0
        
        return avg_loss, auc
    
    def save_model(self, model_name: str = "wide_deep_ranking_model") -> str:
        """모델 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = self.save_dir / f"{model_name}_{timestamp}.pth"
        
        save_dict = {
            'model_state_dict': self.model.state_dict(),
            'model_config': self.model_config,
            'feature_config': self.feature_config,
            'id_mappings': self.id_mappings,
            'training_history': self.training_history
        }
        
        torch.save(save_dict, model_path)
        logger.info(f"모델 저장 완료: {model_path}")
        return str(model_path)
    
    def load_model(self, model_path: str) -> bool:
        """모델 로드"""
        try:
            checkpoint = torch.load(model_path, map_location=self.device)
            
            # 설정 복원
            self.model_config = checkpoint['model_config']
            self.feature_config = checkpoint['feature_config']
            self.id_mappings = checkpoint['id_mappings']
            self.training_history = checkpoint['training_history']
            
            # 모델 복원
            self.model = WideAndDeepRankingModel(self.model_config).to(self.device)
            self.model.load_state_dict(checkpoint['model_state_dict'])
            
            # Feature Engineer 갱신
            self.feature_engineer = FeatureEngineer(self.feature_config)
            
            logger.info(f"모델 로드 완료: {model_path}")
            return True
            
        except Exception as e:
            logger.error(f"모델 로드 실패: {e}")
            return False
    
    def _save_best_model(self):
        """최고 성능 모델 저장 (내부용)"""
        best_model_path = self.save_dir / "best_model.pth"
        
        save_dict = {
            'model_state_dict': self.model.state_dict(),
            'model_config': self.model_config,
            'feature_config': self.feature_config,
            'id_mappings': self.id_mappings,
            'training_history': self.training_history
        }
        
        torch.save(save_dict, best_model_path)
    
    def _build_id_mappings(self, interaction_data: List[Dict[str, Any]]):
        """ID 매핑 딕셔너리 구축"""
        users = set()
        shops = set()
        categories = set()
        
        for interaction in interaction_data:
            users.add(interaction['user_profile'].get('user_id', 'unknown'))
            shops.add(interaction['candidate']['shop_id'])
            categories.add(interaction['candidate'].get('category', 'unknown'))
        
        # 매핑 구축 (0은 unknown/padding용으로 예약)
        self.id_mappings['user_id_map'] = {uid: i+1 for i, uid in enumerate(users)}
        self.id_mappings['shop_id_map'] = {sid: i+1 for i, sid in enumerate(shops)}
        self.id_mappings['category_id_map'] = {cid: i+1 for i, cid in enumerate(categories)}
        
        logger.info(f"ID 매핑 구축 완료: Users {len(users)}, Shops {len(shops)}, Categories {len(categories)}")
    
    def _combine_feature_batches(self, feature_batches: List[Dict[str, np.ndarray]]) -> Dict[str, np.ndarray]:
        """특성 배치들을 하나로 결합"""
        combined = {}
        
        for key in feature_batches[0].keys():
            if key in ['user_ids', 'shop_ids', 'category_ids']:
                # 리스트 결합
                combined[key] = []
                for batch in feature_batches:
                    combined[key].extend(batch[key])
            else:
                # numpy 배열 결합
                combined[key] = np.vstack([batch[key] for batch in feature_batches])
        
        return combined
    
    def plot_training_history(self, save_path: Optional[str] = None):
        """학습 이력 시각화"""
        if not self.training_history['train_loss']:
            logger.warning("학습 이력이 없습니다.")
            return
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
        
        # Loss 그래프
        epochs = range(1, len(self.training_history['train_loss']) + 1)
        ax1.plot(epochs, self.training_history['train_loss'], 'b-', label='Train Loss')
        if self.training_history['val_loss']:
            ax1.plot(epochs, self.training_history['val_loss'], 'r-', label='Val Loss')
        ax1.set_title('Training Loss')
        ax1.set_xlabel('Epoch')
        ax1.set_ylabel('Loss')
        ax1.legend()
        
        # AUC 그래프
        ax2.plot(epochs, self.training_history['train_auc'], 'b-', label='Train AUC')
        if self.training_history['val_auc']:
            ax2.plot(epochs, self.training_history['val_auc'], 'r-', label='Val AUC')
        ax2.set_title('Training AUC')
        ax2.set_xlabel('Epoch')
        ax2.set_ylabel('AUC')
        ax2.legend()
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
            logger.info(f"학습 이력 그래프 저장: {save_path}")
        else:
            plt.show()


# 테스트 함수
def test_model_trainer():
    """모델 학습기 테스트"""
    print("=== Layer 2: 모델 학습기 테스트 ===")
    
    # 설정
    model_config = RankingModelConfig(epochs=3, batch_size=8)
    trainer = ModelTrainer(model_config=model_config)
    
    # 가짜 상호작용 데이터 생성
    interaction_data = []
    
    candidates = [
        {'shop_id': 'shop_1', 'shop_name': '건강한집', 'category': '한식', 'rating': 4.2},
        {'shop_id': 'shop_2', 'shop_name': '맛있는피자', 'category': '양식', 'rating': 4.0},
        {'shop_id': 'shop_3', 'shop_name': '착한치킨', 'category': '치킨', 'rating': 4.5}
    ]
    
    user_profiles = [
        {'user_id': 'user_1', 'preferred_categories': ['한식'], 'average_budget': 15000},
        {'user_id': 'user_2', 'preferred_categories': ['양식'], 'average_budget': 25000}
    ]
    
    context = {
        'user_location': '관악구',
        'time_of_day': 'lunch',
        'current_time': datetime.now()
    }
    
    # 상호작용 데이터 생성 (100개 샘플)
    for i in range(100):
        user_profile = user_profiles[i % len(user_profiles)]
        candidate = candidates[i % len(candidates)]
        
        # Layer 1 점수 추가
        candidate.update({
            'collaborative_score': np.random.uniform(5, 9),
            'content_score': np.random.uniform(5, 9),
            'context_score': np.random.uniform(5, 9),
            'base_score': np.random.uniform(5, 9)
        })
        
        # 클릭 여부 (선호 카테고리면 높은 확률)
        click_prob = 0.8 if candidate['category'] in user_profile['preferred_categories'] else 0.3
        clicked = np.random.random() < click_prob
        
        interaction_data.append({
            'user_profile': user_profile,
            'candidate': candidate,
            'context': context,
            'clicked': clicked
        })
    
    print(f"가짜 상호작용 데이터 생성: {len(interaction_data)}개")
    
    # 학습 데이터 준비
    train_dataset, val_dataset = trainer.prepare_training_data(interaction_data)
    
    # 모델 학습
    result = trainer.train_model(train_dataset, val_dataset)
    
    print(f"\n=== 학습 결과 ===")
    print(f"최종 Train AUC: {result['final_train_auc']:.4f}")
    print(f"최종 Val AUC: {result['final_val_auc']:.4f}")
    print(f"최고 Val AUC: {result['best_val_auc']:.4f}")
    
    # 모델 저장 테스트
    model_path = trainer.save_model("test_model")
    print(f"모델 저장 완료: {model_path}")
    
    # 모델 로드 테스트
    new_trainer = ModelTrainer()
    success = new_trainer.load_model(model_path)
    print(f"모델 로드 {'성공' if success else '실패'}")


if __name__ == "__main__":
    test_model_trainer()