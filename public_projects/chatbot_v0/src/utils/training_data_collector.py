"""
[DEPRECATED] 이 모듈은 더 이상 사용되지 않습니다.
대신 inference/data_collector.py의 LearningDataCollector를 사용하세요.

기존 시스템과의 호환성을 위해 남겨둡니다.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import hashlib

from src.data.data_structure import UserInput, ExtractedInfo, ResponseOutput


@dataclass
class TrainingDataEntry:
    """학습 데이터 엔트리"""
    id: str  # 고유 ID (해시)
    timestamp: datetime
    
    # 입력 데이터
    input_text: str
    session_id: str
    user_id: Optional[str]
    conversation_turn: int
    
    # NLU 결과
    predicted_intent: str
    intent_confidence: float
    extracted_entities: Dict[str, Any]
    
    # 응답 데이터
    response_text: str
    recommendations: List[Dict[str, Any]]
    
    # 품질 지표
    response_time_ms: int
    user_feedback: Optional[str] = None  # positive/negative/none
    is_successful: bool = True  # 성공적인 대화인지
    
    # 학습 메타데이터
    is_verified: bool = False  # 검증 완료 여부
    quality_score: float = 0.0  # 0.0 ~ 1.0
    should_use_for_training: bool = True
    notes: Optional[str] = None


class TrainingDataCollector:
    """학습 데이터 수집기"""
    
    def __init__(self, data_dir: str = "training_data"):
        self.data_dir = data_dir
        self.current_date = datetime.now().strftime("%Y%m%d")
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(os.path.join(data_dir, "raw"), exist_ok=True)
        os.makedirs(os.path.join(data_dir, "processed"), exist_ok=True)
        os.makedirs(os.path.join(data_dir, "verified"), exist_ok=True)
        
        # 세션별 임시 저장소
        self.session_buffer: Dict[str, List[TrainingDataEntry]] = {}
        
    def generate_id(self, text: str, timestamp: datetime) -> str:
        """고유 ID 생성"""
        content = f"{text}_{timestamp.isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def collect_from_interaction(
        self,
        user_input: UserInput,
        extracted_info: ExtractedInfo,
        response: ResponseOutput,
        response_time_ms: int,
        conversation_turn: int = 1
    ) -> TrainingDataEntry:
        """단일 상호작용에서 학습 데이터 수집"""
        
        # 추천 결과 정리
        recommendations = []
        if response.recommendations:
            for rec in response.recommendations:
                if isinstance(rec, dict):
                    recommendations.append({
                        "shop_id": rec.get("shop_id"),
                        "shop_name": rec.get("shop_name"),
                        "score": rec.get("score", 0.0),
                        "price": rec.get("price", 0)
                    })
        
        # 학습 데이터 엔트리 생성
        entry = TrainingDataEntry(
            id=self.generate_id(user_input.text, user_input.timestamp),
            timestamp=user_input.timestamp,
            input_text=user_input.text,
            session_id=getattr(user_input, 'session_id', 'unknown'),
            user_id=user_input.user_id,
            conversation_turn=conversation_turn,
            predicted_intent=extracted_info.intent.value,
            intent_confidence=extracted_info.confidence,
            extracted_entities=extracted_info.entities,
            response_text=response.text,
            recommendations=recommendations,
            response_time_ms=response_time_ms,
            quality_score=self._calculate_quality_score(
                extracted_info, response, response_time_ms
            )
        )
        
        # 세션 버퍼에 추가
        session_id = getattr(user_input, 'session_id', 'unknown')
        if session_id not in self.session_buffer:
            self.session_buffer[session_id] = []
        self.session_buffer[session_id].append(entry)
        
        # 즉시 파일에도 저장 (백업용)
        self._save_to_raw(entry)
        
        return entry
    
    def _calculate_quality_score(
        self,
        extracted_info: ExtractedInfo,
        response: ResponseOutput,
        response_time_ms: int
    ) -> float:
        """학습 데이터 품질 점수 계산"""
        score = 0.0
        
        # 1. NLU 신뢰도 (30%)
        score += extracted_info.confidence * 0.3
        
        # 2. 응답 시간 (20%) - 2초 이내면 만점
        time_score = max(0, 1 - (response_time_ms / 2000))
        score += time_score * 0.2
        
        # 3. 추천 결과 존재 여부 (30%)
        if response.recommendations:
            score += 0.3
        
        # 4. 응답 길이 적절성 (20%) - 50~300자 적절
        response_length = len(response.text)
        if 50 <= response_length <= 300:
            score += 0.2
        elif 30 <= response_length <= 500:
            score += 0.1
        
        return min(1.0, score)
    
    def _save_to_raw(self, entry: TrainingDataEntry):
        """원시 데이터 저장"""
        filename = f"raw/{self.current_date}_raw.jsonl"
        filepath = os.path.join(self.data_dir, filename)
        
        with open(filepath, 'a', encoding='utf-8') as f:
            json.dump(asdict(entry), f, ensure_ascii=False, default=str)
            f.write('\n')
    
    def mark_user_feedback(self, session_id: str, feedback: str):
        """사용자 피드백 표시"""
        if session_id in self.session_buffer:
            # 마지막 엔트리에 피드백 추가
            if self.session_buffer[session_id]:
                self.session_buffer[session_id][-1].user_feedback = feedback
    
    def process_session_end(self, session_id: str) -> Dict[str, Any]:
        """세션 종료 시 처리"""
        if session_id not in self.session_buffer:
            return {"status": "no_data"}
        
        session_entries = self.session_buffer[session_id]
        if not session_entries:
            return {"status": "empty_session"}
        
        # 세션 통계 계산
        stats = {
            "session_id": session_id,
            "total_turns": len(session_entries),
            "avg_quality_score": sum(e.quality_score for e in session_entries) / len(session_entries),
            "successful_interactions": sum(1 for e in session_entries if e.is_successful),
            "has_recommendations": sum(1 for e in session_entries if e.recommendations),
            "timestamp": datetime.now()
        }
        
        # 학습 가치 평가
        is_valuable = (
            len(session_entries) >= 2 and  # 최소 2턴 이상
            stats["avg_quality_score"] >= 0.5 and  # 평균 품질 0.5 이상
            stats["has_recommendations"] > 0  # 추천이 있었음
        )
        
        if is_valuable:
            # 처리된 데이터로 저장
            self._save_processed_session(session_id, session_entries, stats)
        
        # 버퍼에서 제거
        del self.session_buffer[session_id]
        
        return {
            "status": "processed",
            "is_valuable": is_valuable,
            "stats": stats
        }
    
    def _save_processed_session(
        self,
        session_id: str,
        entries: List[TrainingDataEntry],
        stats: Dict[str, Any]
    ):
        """처리된 세션 데이터 저장"""
        filename = f"processed/{self.current_date}_sessions.jsonl"
        filepath = os.path.join(self.data_dir, filename)
        
        session_data = {
            "session_id": session_id,
            "stats": stats,
            "entries": [asdict(e) for e in entries],
            "processed_at": datetime.now().isoformat()
        }
        
        with open(filepath, 'a', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, default=str)
            f.write('\n')
    
    def get_training_ready_data(
        self,
        min_quality_score: float = 0.6,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """학습 준비된 데이터 조회"""
        training_data = []
        
        # processed 디렉토리에서 파일 읽기
        processed_dir = os.path.join(self.data_dir, "processed")
        for filename in os.listdir(processed_dir):
            if filename.endswith('.jsonl'):
                filepath = os.path.join(processed_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        session = json.loads(line)
                        for entry in session['entries']:
                            if (entry['quality_score'] >= min_quality_score and
                                entry['should_use_for_training']):
                                training_data.append({
                                    'input': entry['input_text'],
                                    'intent': entry['predicted_intent'],
                                    'entities': entry['extracted_entities'],
                                    'response': entry['response_text']
                                })
                                
                                if limit and len(training_data) >= limit:
                                    return training_data
        
        return training_data
    
    def export_for_nlu_training(self, output_file: str):
        """NLU 학습용 데이터 내보내기"""
        data = self.get_training_ready_data()
        
        nlu_format = []
        for item in data:
            nlu_format.append({
                "text": item['input'],
                "intent": item['intent'],
                "entities": item['entities']
            })
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(nlu_format, f, ensure_ascii=False, indent=2)
        
        return len(nlu_format)
    
    def get_statistics(self) -> Dict[str, Any]:
        """수집된 데이터 통계"""
        stats = {
            "total_raw_entries": 0,
            "total_sessions": 0,
            "total_valuable_sessions": 0,
            "avg_session_length": 0,
            "intents_distribution": {},
            "date_range": {}
        }
        
        # Raw 데이터 카운트
        raw_dir = os.path.join(self.data_dir, "raw")
        for filename in os.listdir(raw_dir):
            if filename.endswith('.jsonl'):
                filepath = os.path.join(raw_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    stats["total_raw_entries"] += sum(1 for _ in f)
        
        # Processed 세션 분석
        processed_dir = os.path.join(self.data_dir, "processed")
        session_lengths = []
        
        for filename in os.listdir(processed_dir):
            if filename.endswith('.jsonl'):
                filepath = os.path.join(processed_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        session = json.loads(line)
                        stats["total_sessions"] += 1
                        
                        session_length = len(session['entries'])
                        session_lengths.append(session_length)
                        
                        if session['stats']['avg_quality_score'] >= 0.5:
                            stats["total_valuable_sessions"] += 1
                        
                        # 의도 분포
                        for entry in session['entries']:
                            intent = entry['predicted_intent']
                            stats["intents_distribution"][intent] = \
                                stats["intents_distribution"].get(intent, 0) + 1
        
        if session_lengths:
            stats["avg_session_length"] = sum(session_lengths) / len(session_lengths)
        
        return stats


# 사용 예시
if __name__ == "__main__":
    collector = TrainingDataCollector()
    
    # 통계 출력
    stats = collector.get_statistics()
    print("=== 학습 데이터 통계 ===")
    print(f"전체 원시 엔트리: {stats['total_raw_entries']}")
    print(f"전체 세션: {stats['total_sessions']}")
    print(f"가치있는 세션: {stats['total_valuable_sessions']}")
    print(f"평균 세션 길이: {stats['avg_session_length']:.2f}")
    print(f"의도 분포: {stats['intents_distribution']}")