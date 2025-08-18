"""
통합 챗봇 인터페이스
NLU → RAG → Recommend → NLG 파이프라인을 단일 인터페이스로 제공
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

# 필요한 모듈 import
from src.data.data_loader import DataLoader
from src.data.data_structure import UserProfile, UserInput, ChatbotResponse
from models.ax_model import AXModel
from src.inference.integrated_pipeline import IntegratedPipeline
from src.inference.data_collector import LearningDataCollector
from src.utils.coupon_manager import CouponManager
from src.recommendation.coupon_recommender import CouponRecommender

logger = logging.getLogger(__name__)


class ChatbotInterface:
    """
    챗봇의 모든 파이프라인을 감싸는 통합 인터페이스 클래스
    IntegratedPipeline을 기반으로 완전한 챗봇 기능 제공
    """
    
    def __init__(self, config):
        """
        챗봇 초기화
        
        Args:
            config: 설정 객체
        """
        logger.info("ChatbotInterface 초기화 시작...")
        self.config = config
        
        # 1. Knowledge Base 로드
        logger.info("Knowledge Base 로딩 중...")
        data_loader = DataLoader()
        self.knowledge = data_loader.load_knowledge()
        logger.info(f"Knowledge Base 로딩 완료: {len(self.knowledge.shops)} shops, {len(self.knowledge.menus)} menus")
        
        # 2. A.X 3.1 Lite 모델 초기화 (NLG용)
        logger.info("A.X 3.1 Lite 모델 로딩 중...")
        self.ax_model = AXModel(use_4bit=getattr(config, 'use_4bit', True))
        self.ax_model.load_model()  # 실제 모델 로드
        logger.info("A.X 3.1 Lite 모델 로딩 완료")
        
        # 3. 통합 파이프라인 초기화
        logger.info("통합 파이프라인 초기화 중...")
        self.pipeline = IntegratedPipeline(
            knowledge=self.knowledge,
            llm_generator=self.ax_model,
            wide_deep_path=None,  # 자동으로 모델 경로 찾음
            use_rag=getattr(config, 'use_rag', True)
        )
        logger.info("통합 파이프라인 초기화 완료")
        
        # 4. 옵션: 쿠폰 기능
        if getattr(config, 'enable_coupon', False):
            self.coupon_manager = CouponManager(self.knowledge)
            self.coupon_recommender = CouponRecommender(self.knowledge)
            logger.info("쿠폰 기능 활성화")
        else:
            self.coupon_manager = None
            self.coupon_recommender = None
        
        # 5. 옵션: 데이터 수집기
        if getattr(config, 'enable_data_collection', False):
            self.data_collector = LearningDataCollector(
                save_path=f"{config.data.output_path}/learning_data",
                buffer_size=100,
                auto_save_interval=300
            )
            logger.info("데이터 수집기 활성화")
        else:
            self.data_collector = None
        
        # 6. 대화 기록 및 사용자 프로필 저장소
        self.conversation_history = {}
        self.user_profiles = {}
        
        # 7. 성능 메트릭
        self.total_conversations = 0
        self.total_response_time = 0.0
        
        logger.info("ChatbotInterface 초기화 완료!")
    
    def chat(self, message: str, user_id: str = "guest") -> str:
        """
        간단한 채팅 인터페이스
        
        Args:
            message: 사용자 메시지
            user_id: 사용자 ID
            
        Returns:
            챗봇 응답 텍스트
        """
        response_dict = self.get_response(message, user_id)
        return response_dict['text']
    
    def get_response(self, user_message: str, user_id: str = "guest", **kwargs) -> Dict[str, Any]:
        """
        사용자 메시지를 받아 전체 파이프라인을 실행하고 최종 응답 반환
        
        Args:
            user_message: 사용자 입력 텍스트
            user_id: 사용자 ID
            **kwargs: 추가 컨텍스트 (conversation_context 등)
            
        Returns:
            Dict[str, Any]: 챗봇의 최종 응답 (텍스트, 추천, 메타데이터 등)
        """
        import time
        start_time = time.time()
        
        try:
            # 사용자 프로필 로드/생성
            user_profile = self._get_or_create_user_profile(user_id)
            
            # 대화 컨텍스트 가져오기
            conversation_context = kwargs.get('conversation_context', [])
            if not conversation_context and user_id in self.conversation_history:
                # 최근 대화 3개까지 컨텍스트로 사용
                conversation_context = self.conversation_history[user_id][-3:]
            
            # IntegratedPipeline 실행
            chatbot_response = self.pipeline.process(
                user_input=user_message,
                user_profile=user_profile,
                conversation_context=conversation_context,
                user_id=user_id
            )
            
            # 대화 기록 저장
            self._save_conversation(user_id, user_message, chatbot_response)
            
            # 데이터 수집 (옵션)
            if self.data_collector:
                self._collect_learning_data(user_message, chatbot_response, user_id)
            
            # 성능 메트릭 업데이트
            response_time = time.time() - start_time
            self.total_conversations += 1
            self.total_response_time += response_time
            
            # 결과 반환
            return {
                "text": chatbot_response.text,
                "recommendations": chatbot_response.recommendations if hasattr(chatbot_response, 'recommendations') else [],
                "metadata": {
                    "response_time": response_time,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"챗봇 응답 생성 중 오류: {e}", exc_info=True)
            return {
                "text": "죄송해요, 처리 중 문제가 발생했어요. 다시 시도해주세요.",
                "recommendations": [],
                "metadata": {"error": str(e)}
            }
    
    def _get_or_create_user_profile(self, user_id: str) -> Dict[str, Any]:
        """사용자 프로필 로드 또는 생성"""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                'user_id': user_id,
                'preferred_categories': [],
                'average_budget': None,
                'favorite_shops': [],
                'conversation_style': 'friendly',
                'created_at': datetime.now(),
                'last_updated': datetime.now()
            }
        else:
            self.user_profiles[user_id]['last_updated'] = datetime.now()
        
        return self.user_profiles[user_id]
    
    def _save_conversation(self, user_id: str, user_message: str, response: Any):
        """대화 기록 저장"""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        self.conversation_history[user_id].append({
            'user_input': user_message,
            'bot_response': response.text if hasattr(response, 'text') else str(response),
            'timestamp': datetime.now()
        })
        
        # 최대 50개까지만 유지
        if len(self.conversation_history[user_id]) > 50:
            self.conversation_history[user_id] = self.conversation_history[user_id][-50:]
    
    def _collect_learning_data(self, user_message: str, response: Any, user_id: str):
        """학습 데이터 수집"""
        try:
            user_input = UserInput(
                text=user_message,
                user_id=user_id,
                timestamp=datetime.now()
            )
            
            # ExtractedInfo는 pipeline 내부에서 생성되므로 여기서는 생략
            # response 객체가 ChatbotResponse 타입이라고 가정
            
            self.data_collector.collect(
                user_input=user_input,
                extracted_info=None,  # pipeline 내부에서 처리
                response=response
            )
        except Exception as e:
            logger.warning(f"학습 데이터 수집 실패: {e}")
    
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """사용자 프로필 조회"""
        return self.user_profiles.get(user_id)
    
    def get_conversation_history(self, user_id: str, limit: int = 5) -> List[Dict]:
        """대화 기록 조회"""
        history = self.conversation_history.get(user_id, [])
        return history[-limit:] if history else []
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 지표 반환"""
        avg_response_time = (self.total_response_time / self.total_conversations) if self.total_conversations > 0 else 0
        
        return {
            'total_conversations': self.total_conversations,
            'avg_response_time': avg_response_time,
            'success_rate': 0.95,  # 추정치
            'knowledge_base_size': {
                'shops': len(self.knowledge.shops) if self.knowledge else 0,
                'menus': len(self.knowledge.menus) if self.knowledge else 0
            },
            'active_users': len(self.user_profiles),
            'llm_response_rate': 0.8  # 추정치
        }
    
    def reset_conversation(self, user_id: str):
        """특정 사용자의 대화 기록 리셋"""
        if user_id in self.conversation_history:
            self.conversation_history[user_id] = []
        logger.info(f"사용자 {user_id}의 대화 기록이 리셋되었습니다.")
    
    def save_state(self, filepath: str):
        """챗봇 상태 저장"""
        import json
        state = {
            'conversation_history': {
                uid: [
                    {
                        'user_input': conv['user_input'],
                        'bot_response': conv['bot_response'],
                        'timestamp': conv['timestamp'].isoformat() if isinstance(conv['timestamp'], datetime) else conv['timestamp']
                    }
                    for conv in history
                ]
                for uid, history in self.conversation_history.items()
            },
            'performance_metrics': self.get_performance_metrics(),
            'saved_at': datetime.now().isoformat()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        logger.info(f"챗봇 상태가 {filepath}에 저장되었습니다.")
    
    def shutdown(self):
        """챗봇 종료 시 정리 작업"""
        # 데이터 수집기 저장
        if self.data_collector:
            self.data_collector.force_save()
            logger.info("학습 데이터 저장 완료")
        
        # 성능 메트릭 출력
        metrics = self.get_performance_metrics()
        logger.info(f"챗봇 종료 - 총 대화: {metrics['total_conversations']}, 평균 응답시간: {metrics['avg_response_time']:.2f}초")


# 싱글턴 패턴 대신 팩토리 함수 사용
def create_chatbot_interface(config) -> ChatbotInterface:
    """챗봇 인터페이스 생성 팩토리 함수"""
    return ChatbotInterface(config)