"""
A.X Encoder 기반 경량 NLU 모듈
- 의도 분류 (Intent Classification)
- 엔티티 추출 (Entity Extraction)
- 청소년 언어 처리 특화
- 기존 A.X 3.1 Lite NLU와 선택적 사용 가능
"""

import json
import time
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import re

import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel, AutoConfig

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """추출된 엔티티 정보"""
    entity_type: str  # MENU, LOCATION, PRICE, TIME 등
    value: str        # 실제 값
    start_char: int   # 원본 텍스트에서 시작 위치
    end_char: int     # 원본 텍스트에서 끝 위치
    confidence: float = 0.95


@dataclass
class NLUOutput:
    """NLU 분석 결과"""
    text: str
    intent: str
    entities: List[Entity] = field(default_factory=list)
    confidence: float = 0.0
    processing_time: float = 0.0


class AXEncoderMultiTaskModel(nn.Module):
    """Multi-task Learning 모델 (의도 분류 + 엔티티 추출)"""
    
    def __init__(self, encoder, num_intents: int, num_entity_labels: int):
        super().__init__()
        self.encoder = encoder
        hidden_size = encoder.config.hidden_size
        
        # Intent Classification Head
        self.intent_classifier = nn.Sequential(
            nn.Dropout(0.1),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_size // 2, num_intents)
        )
        
        # Entity Extraction Head (Token Classification)
        self.entity_classifier = nn.Sequential(
            nn.Dropout(0.1),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_size // 2, num_entity_labels)
        )
    
    def forward(self, input_ids, attention_mask):
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        sequence_output = outputs.last_hidden_state
        pooled_output = outputs.pooler_output if hasattr(outputs, 'pooler_output') else sequence_output[:, 0]
        
        intent_logits = self.intent_classifier(pooled_output)
        entity_logits = self.entity_classifier(sequence_output)
        
        return intent_logits, entity_logits


class AXEncoderNLU:
    """A.X Encoder 기반 NLU 모듈"""
    
    # 의도 정의
    INTENT_LABELS = [
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
    ENTITY_LABELS = [
        "O",
        "B-MENU", "I-MENU",
        "B-LOCATION", "I-LOCATION",
        "B-PRICE", "I-PRICE",
        "B-TIME", "I-TIME",
        "B-SHOP", "I-SHOP"
    ]
    
    # 청소년 언어 패턴
    YOUTH_PATTERNS = {
        # 줄임말
        "아샷추": "아이스 샷 추가",
        "뭐먹": "뭐 먹",
        "얼마임": "얼마야",
        "어디임": "어디야",
        "맛집추": "맛집 추천",
        
        # 신조어
        "존맛": "정말 맛있는",
        "개맛": "정말 맛있는",
        "핵맛": "정말 맛있는",
        "ㄹㅇ": "진짜",
        "ㅇㅈ": "인정",
        
        # 이모티콘 제거
        "ㅋㅋ": "",
        "ㅎㅎ": "",
        "ㅠㅠ": "",
        "ㅜㅜ": ""
    }
    
    def __init__(self, model_path: Optional[str] = None):
        """
        초기화
        
        Args:
            model_path: 파인튜닝된 모델 경로 (없으면 규칙 기반 폴백)
        """
        self.model_path = model_path
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # 청소년 언어 사전 로드
        self._load_youth_slang()
        
        if model_path and Path(model_path).exists():
            self._load_model()
        else:
            logger.warning(f"모델 파일이 없습니다. 규칙 기반 모드로 동작합니다: {model_path}")
            self.model = None
            self.tokenizer = None
    
    def _load_youth_slang(self):
        """청소년 언어 사전 로드"""
        slang_path = Path(__file__).parent.parent / "data" / "youth_slang.json"
        if slang_path.exists():
            with open(slang_path, 'r', encoding='utf-8') as f:
                slang_data = json.load(f)
                
                # 모든 카테고리를 하나의 딕셔너리로 병합
                self.YOUTH_PATTERNS = {}
                for category in ['abbreviations', 'slang', 'food_slang', 'expressions']:
                    if category in slang_data and isinstance(slang_data[category], dict):
                        # 각 항목이 문자열인지 확인하면서 병합
                        for key, value in slang_data[category].items():
                            if isinstance(value, str):
                                self.YOUTH_PATTERNS[key] = value
                            else:
                                logger.warning(f"잘못된 값 타입: {key}={value} (타입: {type(value)})")
                
                # 강조 표현과 이모티콘은 별도 저장
                self.intensifiers = slang_data.get('intensifiers', {})
                self.emoticons = slang_data.get('emoticons', {})
                
                logger.info(f"청소년 언어 사전 로드 완료: {len(self.YOUTH_PATTERNS)}개 패턴")
        else:
            logger.warning(f"청소년 언어 사전 파일이 없습니다: {slang_path}")
    
    def _load_model(self):
        """모델 및 토크나이저 로드"""
        try:
            # SKT A.X Encoder 모델 로드 시도
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            # safetensors 형식 우선 시도
            try:
                encoder = AutoModel.from_pretrained(self.model_path, use_safetensors=True)
            except:
                # 실패시 일반 형식 시도
                encoder = AutoModel.from_pretrained(self.model_path)
            
            self.model = AXEncoderMultiTaskModel(
                encoder=encoder,
                num_intents=len(self.INTENT_LABELS),
                num_entity_labels=len(self.ENTITY_LABELS)
            )
            
            # 저장된 가중치 로드
            checkpoint_path = Path(self.model_path) / "nlu_checkpoint.pth"
            if checkpoint_path.exists():
                checkpoint = torch.load(checkpoint_path, map_location=self.device)
                self.model.load_state_dict(checkpoint['model_state_dict'])
            
            self.model.to(self.device)
            self.model.eval()
            
            logger.info(f"A.X Encoder NLU 모델 로드 완료: {self.model_path}")
            
        except Exception as e:
            logger.error(f"모델 로드 실패: {e}")
            self.model = None
            self.tokenizer = None
    
    def preprocess_text(self, text: str) -> str:
        """청소년 언어 전처리"""
        processed = text
        
        # 청소년 언어 패턴 치환 (안전하게 처리)
        if hasattr(self, 'YOUTH_PATTERNS') and isinstance(self.YOUTH_PATTERNS, dict):
            for pattern, replacement in self.YOUTH_PATTERNS.items():
                # 패턴과 대체 문자열이 모두 문자열인지 확인
                if isinstance(pattern, str) and isinstance(replacement, str):
                    processed = processed.replace(pattern, replacement)
                else:
                    logger.debug(f"잘못된 패턴 타입 무시: {pattern}={replacement}")
        
        # 중복 공백 제거
        processed = re.sub(r'\s+', ' ', processed).strip()
        
        return processed
    
    def predict(self, text: str) -> NLUOutput:
        """
        NLU 분석 실행
        
        Args:
            text: 사용자 입력 텍스트
            
        Returns:
            NLUOutput: 분석 결과
        """
        start_time = time.time()
        
        # 전처리
        processed_text = self.preprocess_text(text)
        
        if self.model and self.tokenizer:
            # 모델 기반 예측
            result = self._model_predict(processed_text, original_text=text)
        else:
            # 규칙 기반 폴백
            result = self._rule_based_predict(processed_text, original_text=text)
        
        result.processing_time = time.time() - start_time
        logger.debug(f"NLU 처리 시간: {result.processing_time:.3f}초")
        
        return result
    
    def _model_predict(self, text: str, original_text: str) -> NLUOutput:
        """모델 기반 예측"""
        try:
            with torch.no_grad():
                # 토크나이징
                inputs = self.tokenizer(
                    text,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=128
                ).to(self.device)
                
                # 추론
                intent_logits, entity_logits = self.model(
                    input_ids=inputs['input_ids'],
                    attention_mask=inputs['attention_mask']
                )
                
                # 의도 예측
                intent_probs = torch.softmax(intent_logits, dim=-1)
                intent_idx = torch.argmax(intent_probs, dim=-1).item()
                intent = self.INTENT_LABELS[intent_idx]
                intent_confidence = intent_probs[0, intent_idx].item()
                
                # 신뢰도가 너무 낮으면 규칙 기반으로 폴백
                if intent_confidence < 0.3:
                    logger.debug(f"모델 신뢰도 낮음 ({intent_confidence:.2f}), 규칙 기반 사용")
                    return self._rule_based_predict(text, original_text)
                
                # 엔티티 예측
                entity_preds = torch.argmax(entity_logits, dim=-1)[0]
                entities = self._extract_entities(
                    text, 
                    entity_preds.cpu().numpy(),
                    inputs['input_ids'][0].cpu().numpy()
                )
                
                return NLUOutput(
                    text=original_text,
                    intent=intent,
                    entities=entities,
                    confidence=intent_confidence
                )
        except Exception as e:
            logger.warning(f"모델 예측 실패, 규칙 기반으로 폴백: {e}")
            return self._rule_based_predict(text, original_text)
    
    def _rule_based_predict(self, text: str, original_text: str) -> NLUOutput:
        """규칙 기반 예측 (폴백)"""
        intent = "일반대화"  # 기본값을 일반대화로 변경
        confidence = 0.5
        entities = []
        
        text_lower = text.lower()
        
        # 의도 분류 규칙 (순서가 중요함)
        # 부정 피드백을 먼저 체크 (음식추천의 특수 케이스)
        if any(word in text_lower for word in ["별로", "싫어", "안좋", "다른", "말고", "그거말고", "빼고", "제외"]):
            # 음식 관련 단어가 있으면 음식추천으로 분류 (나중에 modify_request로 매핑됨)
            food_keywords = ["치킨", "피자", "햄버거", "중식", "한식", "일식", "양식", "분식", "카페", "떡볶이", "김밥"]
            if any(food in text_lower for food in food_keywords):
                intent = "음식추천"  # IntentPostProcessor에서 modify_request로 변환
                confidence = 0.85
        # 짧은 부정 대답 (일반대화로 유지)
        elif text_lower in ["아니", "아니요", "아뇨", "ㄴㄴ", "노노", "no"]:
            intent = "일반대화"
            confidence = 0.9
        elif any(word in text_lower for word in ["추천", "뭐 먹", "뭐먹", "배고프", "배고픈", "먹고 싶", "먹을까"]):
            intent = "음식추천"
            confidence = 0.9
        elif any(word in text_lower for word in ["얼마", "가격"]) and "원" in text:
            intent = "가격문의"
            confidence = 0.9
        elif any(word in text_lower for word in ["잔액", "남은 돈", "잔고"]):
            intent = "잔액확인"
            confidence = 0.95
        elif any(word in text_lower for word in ["쿠폰", "할인"]):
            intent = "쿠폰조회"
            confidence = 0.95
        elif any(word in text_lower for word in ["어디", "위치", "주소"]):
            intent = "위치검색"
            confidence = 0.85
        elif any(word in text_lower for word in ["몇시", "영업시간", "언제"]):
            intent = "영업시간"
            confidence = 0.85
        elif any(word in text_lower for word in ["안녕", "하이", "헬로", "반가", "hi", "hello"]):
            intent = "인사"  # 인사는 별도로 분류
            confidence = 0.95
        elif any(word in text_lower for word in ["고마워", "감사", "땡큐", "thanks"]):
            intent = "감사인사"
            confidence = 0.95
        elif any(word in text_lower for word in ["이해", "대답", "뭐하", "뭐해", "무엇", "말", "응", "그래", "맞아", "ㅇㅇ", "ㅇㅋ", "오케이"]):
            intent = "일반대화"
            confidence = 0.8
        
        # 엔티티 추출 규칙
        # 메뉴명 (간단한 예시)
        menu_keywords = ["치킨", "피자", "떡볶이", "햄버거", "김밥", "라면", "파스타", "초밥", "짜장면", "짬뽕"]
        for menu in menu_keywords:
            if menu in text:
                start = original_text.find(menu)
                if start != -1:
                    entities.append(Entity(
                        entity_type="MENU",
                        value=menu,
                        start_char=start,
                        end_char=start + len(menu),
                        confidence=0.8
                    ))
        
        # 가격 추출
        price_pattern = r'(\d{1,2})(천|만)?원'
        for match in re.finditer(price_pattern, original_text):
            value = match.group()
            entities.append(Entity(
                entity_type="PRICE",
                value=value,
                start_char=match.start(),
                end_char=match.end(),
                confidence=0.9
            ))
        
        # 위치 추출 (간단한 예시)
        location_keywords = ["강남", "홍대", "신촌", "명동", "이태원", "건대", "성수", "종로"]
        for loc in location_keywords:
            if loc in text:
                start = original_text.find(loc)
                if start != -1:
                    entities.append(Entity(
                        entity_type="LOCATION",
                        value=loc,
                        start_char=start,
                        end_char=start + len(loc),
                        confidence=0.85
                    ))
        
        return NLUOutput(
            text=original_text,
            intent=intent,
            entities=entities,
            confidence=confidence
        )
    
    def _extract_entities(self, text: str, entity_labels: List[int], token_ids: List[int]) -> List[Entity]:
        """BIO 태그에서 엔티티 추출 (위치 정보 포함)"""
        entities = []
        current_entity = None
        current_tokens = []
        current_token_indices = []
        
        # 토큰을 텍스트로 변환
        tokens = self.tokenizer.convert_ids_to_tokens(token_ids)
        
        # 토큰과 원본 텍스트 위치 매핑
        token_positions = self._get_token_positions(text, tokens)
        
        for i, (token, label_idx) in enumerate(zip(tokens, entity_labels)):
            label = self.ENTITY_LABELS[label_idx] if label_idx < len(self.ENTITY_LABELS) else "O"
            
            if label.startswith("B-"):
                # 새 엔티티 시작
                if current_entity:
                    # 이전 엔티티 저장
                    entity_text = self.tokenizer.convert_tokens_to_string(current_tokens)
                    start_pos, end_pos = self._calculate_entity_position(
                        text, entity_text, current_token_indices, token_positions
                    )
                    entities.append(Entity(
                        entity_type=current_entity,
                        value=entity_text,
                        start_char=start_pos,
                        end_char=end_pos,
                        confidence=0.85
                    ))
                
                current_entity = label[2:]
                current_tokens = [token]
                current_token_indices = [i]
                
            elif label.startswith("I-") and current_entity == label[2:]:
                # 현재 엔티티 계속
                current_tokens.append(token)
                current_token_indices.append(i)
                
            else:
                # 엔티티 종료
                if current_entity:
                    entity_text = self.tokenizer.convert_tokens_to_string(current_tokens)
                    start_pos, end_pos = self._calculate_entity_position(
                        text, entity_text, current_token_indices, token_positions
                    )
                    entities.append(Entity(
                        entity_type=current_entity,
                        value=entity_text,
                        start_char=start_pos,
                        end_char=end_pos,
                        confidence=0.85
                    ))
                    current_entity = None
                    current_tokens = []
                    current_token_indices = []
        
        # 마지막 엔티티 처리
        if current_entity:
            entity_text = self.tokenizer.convert_tokens_to_string(current_tokens)
            start_pos, end_pos = self._calculate_entity_position(
                text, entity_text, current_token_indices, token_positions
            )
            entities.append(Entity(
                entity_type=current_entity,
                value=entity_text,
                start_char=start_pos,
                end_char=end_pos,
                confidence=0.85
            ))
        
        return entities
    
    def _get_token_positions(self, text: str, tokens: List[str]) -> List[Tuple[int, int]]:
        """토큰의 원본 텍스트 내 위치 계산"""
        positions = []
        current_pos = 0
        
        for token in tokens:
            # 특수 토큰 처리
            if token in ['[CLS]', '[SEP]', '[PAD]', '[UNK]']:
                positions.append((-1, -1))
                continue
            
            # 서브워드 토큰 처리 (## 제거)
            clean_token = token.replace('##', '')
            
            # 원본 텍스트에서 토큰 위치 찾기
            idx = text.lower().find(clean_token.lower(), current_pos)
            if idx != -1:
                positions.append((idx, idx + len(clean_token)))
                current_pos = idx + len(clean_token)
            else:
                positions.append((-1, -1))
        
        return positions
    
    def _calculate_entity_position(
        self, 
        text: str, 
        entity_text: str, 
        token_indices: List[int],
        token_positions: List[Tuple[int, int]]
    ) -> Tuple[int, int]:
        """엔티티의 원본 텍스트 내 위치 계산"""
        # 토큰 인덱스에서 위치 정보 추출
        valid_positions = [
            token_positions[i] for i in token_indices 
            if i < len(token_positions) and token_positions[i][0] != -1
        ]
        
        if valid_positions:
            start_pos = valid_positions[0][0]
            end_pos = valid_positions[-1][1]
            return start_pos, end_pos
        
        # 폴백: 텍스트에서 직접 검색
        idx = text.find(entity_text)
        if idx != -1:
            return idx, idx + len(entity_text)
        
        return 0, 0


# 기존 시스템과의 호환성을 위한 래퍼
class AXEncoderNLUWrapper:
    """기존 NaviyamNLU 인터페이스와 호환되는 래퍼"""
    
    def __init__(self, model_path: Optional[str] = None):
        self.nlu = AXEncoderNLU(model_path)
    
    def extract_intent_and_entities(self, text: str) -> Tuple[str, Dict[str, Any], float]:
        """
        기존 인터페이스와 호환되는 메서드
        
        Returns:
            (intent, entities_dict, confidence)
        """
        result = self.nlu.predict(text)
        
        # 엔티티를 딕셔너리로 변환
        entities_dict = {}
        for entity in result.entities:
            if entity.entity_type not in entities_dict:
                entities_dict[entity.entity_type] = []
            entities_dict[entity.entity_type].append(entity.value)
        
        return result.intent, entities_dict, result.confidence