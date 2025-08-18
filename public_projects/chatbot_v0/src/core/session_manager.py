"""
세션 및 대화 상태 관리
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
import uuid
import json

@dataclass
class ConversationState:
    """대화 상태 추적을 위한 데이터 클래스"""
    intent: Optional[str] = None
    entities: Dict[str, Any] = field(default_factory=dict)
    required_info: List[str] = field(default_factory=list)
    context_history: List[Dict] = field(default_factory=list)
    intent_stack: List[str] = field(default_factory=list)  # 이전 의도 추적
    is_intent_changed: bool = False  # 의도 변경 플래그
    
    def get_missing_info(self) -> List[str]:
        """아직 수집되지 않은 필수 정보 반환"""
        collected = set(self.entities.keys())
        required = set(self.required_info)
        return list(required - collected)
    
    def is_complete(self) -> bool:
        """필수 정보가 모두 수집되었는지 확인"""
        return len(self.get_missing_info()) == 0
    
    def add_context(self, turn_type: str, content: str):
        """대화 컨텍스트 추가"""
        self.context_history.append({
            'turn_type': turn_type,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })

@dataclass
class Session:
    """사용자 세션 정보"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    conversation_history: List[Dict] = field(default_factory=list)
    state_tracker: ConversationState = field(default_factory=ConversationState)
    last_bot_action: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """대화 메시지 추가"""
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        self.conversation_history.append(message)
        self.updated_at = datetime.now()
        
        # 상태 컨텍스트에도 추가
        self.state_tracker.add_context(role, content)
    
    def get_conversation_context(self, last_n: int = 5) -> str:
        """최근 대화 컨텍스트를 문자열로 반환"""
        recent_messages = self.conversation_history[-last_n:]
        context_parts = []
        for msg in recent_messages:
            role = "사용자" if msg['role'] == 'user' else "챗봇"
            context_parts.append(f"{role}: {msg['content']}")
        return "\n".join(context_parts)

class SessionManager:
    """세션 관리자"""
    
    def __init__(self, session_timeout_minutes: int = 30):
        self.sessions: Dict[str, Session] = {}
        self.session_timeout_minutes = session_timeout_minutes
    
    def create_session(self, user_id: Optional[str] = None) -> Session:
        """새 세션 생성"""
        session = Session(user_id=user_id)
        self.sessions[session.session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """세션 ID로 세션 조회"""
        return self.sessions.get(session_id)
    
    def update_session_state(self, session_id: str, **kwargs) -> bool:
        """세션 상태 업데이트"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        state = session.state_tracker
        
        # Intent 업데이트 (의도 변경 감지)
        if 'intent' in kwargs:
            new_intent = kwargs['intent']
            if state.intent and state.intent != new_intent:
                # 의도가 변경되었다면 이전 의도를 스택에 저장
                state.intent_stack.append(state.intent)
                state.is_intent_changed = True
                # 의도 변경 시 엔티티 리셋 여부 확인
                if kwargs.get('reset_entities', False):
                    state.entities.clear()
            else:
                state.is_intent_changed = False
            state.intent = new_intent
        
        # Entities 업데이트
        if 'entities' in kwargs:
            state.entities.update(kwargs['entities'])
        
        # Required info 업데이트
        if 'required_info' in kwargs:
            state.required_info = kwargs['required_info']
        
        # Last bot action 업데이트
        if 'last_bot_action' in kwargs:
            session.last_bot_action = kwargs['last_bot_action']
        
        session.updated_at = datetime.now()
        return True
    
    def is_session_active(self, session_id: str) -> bool:
        """세션이 활성 상태인지 확인"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        time_diff = datetime.now() - session.updated_at
        return time_diff.total_seconds() < self.session_timeout_minutes * 60
    
    def clean_expired_sessions(self):
        """만료된 세션 정리"""
        expired_sessions = []
        for session_id, session in self.sessions.items():
            if not self.is_session_active(session_id):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
    
    def get_active_sessions_count(self) -> int:
        """활성 세션 수 반환"""
        self.clean_expired_sessions()
        return len(self.sessions)
    
    def export_session(self, session_id: str) -> Optional[Dict]:
        """세션 정보를 딕셔너리로 내보내기"""
        session = self.get_session(session_id)
        if not session:
            return None
        
        return {
            'session_id': session.session_id,
            'user_id': session.user_id,
            'created_at': session.created_at.isoformat(),
            'updated_at': session.updated_at.isoformat(),
            'conversation_history': session.conversation_history,
            'state_tracker': {
                'intent': session.state_tracker.intent,
                'entities': session.state_tracker.entities,
                'required_info': session.state_tracker.required_info,
                'context_history': session.state_tracker.context_history
            },
            'last_bot_action': session.last_bot_action,
            'metadata': session.metadata
        }