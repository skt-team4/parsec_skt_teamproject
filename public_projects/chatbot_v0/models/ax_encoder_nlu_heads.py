"""
A.X Encoder에 NLU 헤드 추가
- 의도 분류 (Intent Classification Head)
- 엔티티 추출 (Entity Extraction Head)
"""

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer
from typing import Dict, List, Tuple
import json
from pathlib import Path


class AXEncoderNLUModel(nn.Module):
    """A.X Encoder + NLU 헤드"""
    
    def __init__(self, model_path: str = "./models/ax_encoder_base"):
        super().__init__()
        
        # A.X Encoder 베이스 모델 로드
        self.encoder = AutoModel.from_pretrained(model_path)
        self.config = self.encoder.config
        hidden_size = self.config.hidden_size  # 768
        
        # 의도 레이블
        self.intent_labels = [
            "음식추천",
            "가격문의",
            "잔액확인",
            "쿠폰조회",
            "가게정보",
            "위치검색",
            "영업시간",
            "일반대화",
            "감사인사",
            "기타"
        ]
        
        # 엔티티 레이블 (BIO 태깅)
        self.entity_labels = [
            "O",
            "B-MENU", "I-MENU",
            "B-LOCATION", "I-LOCATION",
            "B-PRICE", "I-PRICE",
            "B-TIME", "I-TIME",
            "B-SHOP", "I-SHOP"
        ]
        
        # 1. 의도 분류 헤드 (CLS 토큰 사용)
        self.intent_head = nn.Sequential(
            nn.Dropout(0.1),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.GELU(),  # ModernBERT는 GELU 사용
            nn.Dropout(0.1),
            nn.Linear(hidden_size // 2, len(self.intent_labels))
        )
        
        # 2. 엔티티 추출 헤드 (각 토큰별 분류)
        self.entity_head = nn.Sequential(
            nn.Dropout(0.1),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_size // 2, len(self.entity_labels))
        )
        
        # 가중치 초기화
        self._init_weights()
        
        # 레이블 인덱스 매핑
        self.intent2idx = {label: idx for idx, label in enumerate(self.intent_labels)}
        self.idx2intent = {idx: label for idx, label in enumerate(self.intent_labels)}
        
        self.entity2idx = {label: idx for idx, label in enumerate(self.entity_labels)}
        self.idx2entity = {idx: label for idx, label in enumerate(self.entity_labels)}
    
    def _init_weights(self):
        """가중치 초기화 (Xavier/He 초기화)"""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                # Xavier 초기화
                nn.init.xavier_uniform_(module.weight, gain=0.02)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
    
    def forward(self, input_ids, attention_mask):
        """
        Forward pass
        
        Returns:
            intent_logits: [batch_size, num_intents]
            entity_logits: [batch_size, seq_len, num_entities]
        """
        # A.X Encoder 출력
        outputs = self.encoder(
            input_ids=input_ids,
            attention_mask=attention_mask
        )
        
        # 시퀀스 출력 (모든 토큰)
        sequence_output = outputs.last_hidden_state  # [batch_size, seq_len, hidden_size]
        
        # CLS 토큰 (첫 번째 토큰)
        cls_output = sequence_output[:, 0, :]  # [batch_size, hidden_size]
        
        # 의도 분류
        intent_logits = self.intent_head(cls_output)  # [batch_size, num_intents]
        
        # 엔티티 추출
        entity_logits = self.entity_head(sequence_output)  # [batch_size, seq_len, num_entities]
        
        return intent_logits, entity_logits
    
    def predict_intent(self, intent_logits):
        """의도 예측"""
        probs = torch.softmax(intent_logits, dim=-1)
        predicted_idx = torch.argmax(probs, dim=-1)
        confidence = probs[0, predicted_idx].item()
        intent = self.idx2intent[predicted_idx.item()]
        return intent, confidence
    
    def predict_entities(self, entity_logits, tokens):
        """엔티티 예측 (BIO 디코딩)"""
        predictions = torch.argmax(entity_logits, dim=-1)[0]  # [seq_len]
        
        entities = []
        current_entity = None
        current_tokens = []
        
        for idx, (token, pred_idx) in enumerate(zip(tokens, predictions.tolist())):
            label = self.idx2entity[pred_idx]
            
            if label.startswith("B-"):
                # 새 엔티티 시작
                if current_entity:
                    entities.append({
                        "type": current_entity,
                        "tokens": current_tokens,
                        "start": current_tokens[0]["idx"],
                        "end": current_tokens[-1]["idx"]
                    })
                current_entity = label[2:]
                current_tokens = [{"token": token, "idx": idx}]
                
            elif label.startswith("I-") and current_entity == label[2:]:
                # 현재 엔티티 계속
                current_tokens.append({"token": token, "idx": idx})
                
            else:
                # 엔티티 종료
                if current_entity:
                    entities.append({
                        "type": current_entity,
                        "tokens": current_tokens,
                        "start": current_tokens[0]["idx"],
                        "end": current_tokens[-1]["idx"]
                    })
                    current_entity = None
                    current_tokens = []
        
        # 마지막 엔티티 처리
        if current_entity:
            entities.append({
                "type": current_entity,
                "tokens": current_tokens,
                "start": current_tokens[0]["idx"],
                "end": current_tokens[-1]["idx"]
            })
        
        return entities


class AXEncoderNLUPipeline:
    """NLU 파이프라인"""
    
    def __init__(self, model_path: str = "./models/ax_encoder_base"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # 토크나이저 로드
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        
        # NLU 모델 로드
        self.model = AXEncoderNLUModel(model_path)
        self.model.to(self.device)
        self.model.eval()
        
        print(f"[NLU] 모델 로드 완료 (디바이스: {self.device})")
    
    def __call__(self, text: str) -> Dict:
        """
        텍스트 분석
        
        Args:
            text: 입력 텍스트
            
        Returns:
            {
                "text": 원본 텍스트,
                "intent": 의도,
                "intent_confidence": 신뢰도,
                "entities": 엔티티 리스트
            }
        """
        # 토크나이징
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=128
        )
        
        # token_type_ids 제거 (ModernBERT)
        inputs = {k: v.to(self.device) for k, v in inputs.items() if k != 'token_type_ids'}
        
        # 추론
        with torch.no_grad():
            intent_logits, entity_logits = self.model(**inputs)
        
        # 의도 예측
        intent, confidence = self.model.predict_intent(intent_logits)
        
        # 토큰 리스트
        tokens = self.tokenizer.convert_ids_to_tokens(inputs['input_ids'][0].tolist())
        
        # 엔티티 예측
        entities = self.model.predict_entities(entity_logits, tokens)
        
        # 엔티티 텍스트 복원
        for entity in entities:
            entity_tokens = [t["token"] for t in entity["tokens"]]
            entity["text"] = self.tokenizer.convert_tokens_to_string(entity_tokens)
            # 토큰 정보 제거 (간결화)
            del entity["tokens"]
        
        return {
            "text": text,
            "intent": intent,
            "intent_confidence": confidence,
            "entities": entities
        }
    
    def save_model(self, save_path: str):
        """모델 저장"""
        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)
        
        # 모델 가중치 저장
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'intent_labels': self.model.intent_labels,
            'entity_labels': self.model.entity_labels
        }, save_path / "nlu_heads.pth")
        
        print(f"[NLU] 모델 저장 완료: {save_path}")
    
    def load_model(self, load_path: str):
        """모델 로드"""
        checkpoint = torch.load(Path(load_path) / "nlu_heads.pth", map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        print(f"[NLU] 모델 로드 완료: {load_path}")


def test_nlu_heads():
    """NLU 헤드 테스트"""
    print("="*60)
    print("A.X Encoder NLU 헤드 테스트")
    print("="*60)
    
    # NLU 파이프라인 생성
    nlu = AXEncoderNLUPipeline()
    
    # 테스트 문장들
    test_sentences = [
        "치킨 먹고 싶어",
        "강남역 맛집 추천해줘",
        "만원으로 뭐 먹지?",
        "아샷추 얼마야 ㅋㅋ",
        "쿠폰 있어?",
        "잔액 확인",
        "고마워",
        "안녕하세요"
    ]
    
    print("\n[테스트 결과]")
    print("-"*60)
    
    for text in test_sentences:
        result = nlu(text)
        
        print(f"\n입력: {text}")
        print(f"의도: {result['intent']} (신뢰도: {result['intent_confidence']:.3f})")
        
        if result['entities']:
            print("엔티티:")
            for entity in result['entities']:
                print(f"  - {entity['type']}: {entity['text']} [{entity['start']}:{entity['end']}]")
    
    print("\n" + "="*60)
    print("[OK] NLU 헤드 테스트 완료!")
    print("="*60)


if __name__ == "__main__":
    test_nlu_heads()