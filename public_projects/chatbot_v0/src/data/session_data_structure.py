#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
세션 기반 데이터 수집 구조
Gemini 제안을 반영한 체계적인 데이터 수집
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import json


class SelectionReason(Enum):
    """선택 이유"""
    DISTANCE = "distance"  # 거리
    PRICE = "price"  # 가격
    MENU = "menu"  # 메뉴
    REVIEW = "review"  # 리뷰
    NAVIGATION = "navigation"  # 길찾기 요청
    MORE_INFO = "more_info"  # 상세정보 요청
    UNKNOWN = "unknown"


class RejectionReason(Enum):
    """거부 이유"""
    TOO_FAR = "too_far"  # 너무 멀다
    TOO_EXPENSIVE = "too_expensive"  # 너무 비싸다
    NOT_PREFERRED = "not_preferred"  # 선호하지 않음
    NO_INTEREST = "no_interest"  # 관심 없음
    UNKNOWN = "unknown"


@dataclass
class UserFeedback:
    """사용자 피드백"""
    selected_shop_id: Optional[int] = None
    unselected_shop_ids: List[int] = field(default_factory=list)
    selection_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    implicit_signals: Dict[str, Any] = field(default_factory=dict)  # 클릭, 스크롤 등
    
    def to_dict(self) -> Dict:
        return {
            'selected_shop_id': self.selected_shop_id,
            'unselected_shop_ids': self.unselected_shop_ids,
            'selection_reason': self.selection_reason,
            'rejection_reason': self.rejection_reason,
            'implicit_signals': self.implicit_signals
        }


@dataclass
class SystemOutput:
    """시스템 출력 데이터"""
    rag_candidates: List[Dict[str, Any]] = field(default_factory=list)  # RAG 검색 결과
    recommendation_scores: List[Dict[str, Any]] = field(default_factory=list)  # 랭킹 점수
    displayed_recommendations: List[int] = field(default_factory=list)  # 실제 표시된 추천
    generated_response: str = ""  # 생성된 응답
    response_time_ms: int = 0  # 응답 시간
    
    def to_dict(self) -> Dict:
        return {
            'rag_candidates': self.rag_candidates[:20],  # 상위 20개만 저장
            'recommendation_scores': self.recommendation_scores,
            'displayed_recommendations': self.displayed_recommendations,
            'generated_response': self.generated_response[:500],  # 처음 500자만
            'response_time_ms': self.response_time_ms
        }


@dataclass
class Interaction:
    """단일 상호작용 (대화 턴)"""
    turn_id: int
    timestamp: datetime
    user_input: Dict[str, str]  # {'text': '...'}
    nlu_output: Dict[str, Any]  # intent, entities, confidence
    system_output: SystemOutput
    user_feedback: Optional[UserFeedback] = None
    
    def to_dict(self) -> Dict:
        return {
            'turn_id': self.turn_id,
            'timestamp': self.timestamp.isoformat(),
            'user_input': self.user_input,
            'nlu_output': self.nlu_output,
            'system_output': self.system_output.to_dict(),
            'user_feedback': self.user_feedback.to_dict() if self.user_feedback else None
        }


@dataclass
class SessionData:
    """세션 전체 데이터"""
    session_id: str
    user_id_anonymous: str
    session_start_time: datetime
    session_end_time: Optional[datetime] = None
    interactions: List[Interaction] = field(default_factory=list)
    session_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_interaction(self, interaction: Interaction):
        """상호작용 추가"""
        self.interactions.append(interaction)
    
    def get_selected_shops(self) -> List[int]:
        """세션에서 선택된 모든 가게 ID"""
        selected = []
        for interaction in self.interactions:
            if interaction.user_feedback and interaction.user_feedback.selected_shop_id:
                selected.append(interaction.user_feedback.selected_shop_id)
        return selected
    
    def get_rejection_patterns(self) -> Dict[str, int]:
        """거부 패턴 분석"""
        patterns = {}
        for interaction in self.interactions:
            if interaction.user_feedback and interaction.user_feedback.rejection_reason:
                reason = interaction.user_feedback.rejection_reason
                patterns[reason] = patterns.get(reason, 0) + 1
        return patterns
    
    def to_dict(self) -> Dict:
        """JSON 직렬화용"""
        return {
            'session_id': self.session_id,
            'user_id_anonymous': self.user_id_anonymous,
            'session_start_time': self.session_start_time.isoformat(),
            'session_end_time': self.session_end_time.isoformat() if self.session_end_time else None,
            'interactions': [i.to_dict() for i in self.interactions],
            'session_metadata': self.session_metadata
        }
    
    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SessionData':
        """딕셔너리에서 생성"""
        session = cls(
            session_id=data['session_id'],
            user_id_anonymous=data['user_id_anonymous'],
            session_start_time=datetime.fromisoformat(data['session_start_time']),
            session_end_time=datetime.fromisoformat(data['session_end_time']) if data.get('session_end_time') else None,
            session_metadata=data.get('session_metadata', {})
        )
        
        # 상호작용 복원
        for i_data in data.get('interactions', []):
            system_output = SystemOutput(
                rag_candidates=i_data['system_output'].get('rag_candidates', []),
                recommendation_scores=i_data['system_output'].get('recommendation_scores', []),
                displayed_recommendations=i_data['system_output'].get('displayed_recommendations', []),
                generated_response=i_data['system_output'].get('generated_response', ''),
                response_time_ms=i_data['system_output'].get('response_time_ms', 0)
            )
            
            user_feedback = None
            if i_data.get('user_feedback'):
                user_feedback = UserFeedback(
                    selected_shop_id=i_data['user_feedback'].get('selected_shop_id'),
                    unselected_shop_ids=i_data['user_feedback'].get('unselected_shop_ids', []),
                    selection_reason=i_data['user_feedback'].get('selection_reason'),
                    rejection_reason=i_data['user_feedback'].get('rejection_reason'),
                    implicit_signals=i_data['user_feedback'].get('implicit_signals', {})
                )
            
            interaction = Interaction(
                turn_id=i_data['turn_id'],
                timestamp=datetime.fromisoformat(i_data['timestamp']),
                user_input=i_data['user_input'],
                nlu_output=i_data['nlu_output'],
                system_output=system_output,
                user_feedback=user_feedback
            )
            session.add_interaction(interaction)
        
        return session


@dataclass
class UserSelectionEvent:
    """사용자 선택 이벤트 (실시간 캡처용)"""
    session_id: str
    turn_id: int
    timestamp: datetime
    event_type: str  # 'select', 'reject', 'more_info', 'navigate'
    shop_id: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'session_id': self.session_id,
            'turn_id': self.turn_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type,
            'shop_id': self.shop_id,
            'metadata': self.metadata
        }


class SessionDataManager:
    """세션 데이터 관리자"""
    
    def __init__(self):
        self.active_sessions: Dict[str, SessionData] = {}
        self.completed_sessions: List[SessionData] = []
    
    def create_session(self, user_id: str) -> SessionData:
        """새 세션 생성"""
        import hashlib
        from datetime import datetime
        
        # 사용자 ID 익명화
        user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]
        
        # 세션 ID 생성
        timestamp = datetime.now()
        session_id = f"sid-{timestamp.strftime('%Y%m%d-%H%M%S')}-{user_hash}"
        
        session = SessionData(
            session_id=session_id,
            user_id_anonymous=f"user-{user_hash}",
            session_start_time=timestamp
        )
        
        self.active_sessions[session_id] = session
        return session
    
    def add_interaction(self, session_id: str, interaction: Interaction):
        """세션에 상호작용 추가"""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].add_interaction(interaction)
    
    def record_user_selection(self, session_id: str, turn_id: int, 
                             selected_shop_id: int, 
                             unselected_shop_ids: List[int],
                             reason: Optional[str] = None):
        """사용자 선택 기록"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            # 해당 턴 찾기
            for interaction in session.interactions:
                if interaction.turn_id == turn_id:
                    if not interaction.user_feedback:
                        interaction.user_feedback = UserFeedback()
                    interaction.user_feedback.selected_shop_id = selected_shop_id
                    interaction.user_feedback.unselected_shop_ids = unselected_shop_ids
                    interaction.user_feedback.selection_reason = reason
                    break
    
    def end_session(self, session_id: str):
        """세션 종료"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.session_end_time = datetime.now()
            self.completed_sessions.append(session)
            del self.active_sessions[session_id]
            return session
        return None
    
    def get_training_data(self) -> List[Dict]:
        """학습용 데이터 추출"""
        training_data = []
        
        for session in self.completed_sessions:
            for interaction in session.interactions:
                if interaction.user_feedback and interaction.user_feedback.selected_shop_id:
                    # Positive example (선택된 것)
                    training_data.append({
                        'session_id': session.session_id,
                        'user_input': interaction.user_input['text'],
                        'shop_id': interaction.user_feedback.selected_shop_id,
                        'label': 1,  # Positive
                        'context': interaction.nlu_output
                    })
                    
                    # Negative examples (선택되지 않은 것들)
                    for rejected_id in interaction.user_feedback.unselected_shop_ids:
                        training_data.append({
                            'session_id': session.session_id,
                            'user_input': interaction.user_input['text'],
                            'shop_id': rejected_id,
                            'label': 0,  # Negative
                            'context': interaction.nlu_output
                        })
        
        return training_data