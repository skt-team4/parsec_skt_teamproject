"""
나비얌 챗봇 FastAPI 서버
백엔드 담당자용 기본 구조
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import asyncio
import uuid

from src.inference.unified_chatbot_v2 import UnifiedChatbotV2
from src.data.data_structure import UserInput, ChatbotOutput
from src.utils.config import load_config
from src.utils.logging_utils import setup_logging

# OpenAI 호환 어댑터 임포트는 제거 (존재하지 않음)

# 로깅 설정
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="나비얌 챗봇 API",
    description="아동 대상 착한가게 추천 AI 챗봇 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 변수
chatbot: Optional[NaviyamChatbot] = None

# OpenAI 어댑터 라우터 등록
app.include_router(openai_router)

# OpenAI 어댑터에 챗봇 인스턴스 주입
from api.openai_adapter import get_chatbot_instance
app.dependency_overrides[get_chatbot_instance] = get_chatbot


# === 요청/응답 모델 정의 ===

class ChatRequest(BaseModel):
    """채팅 요청 모델"""
    message: str = Field(..., description="사용자 메시지", min_length=1, max_length=1000)
    user_id: str = Field(..., description="사용자 ID", min_length=1, max_length=100)
    session_id: Optional[str] = Field(None, description="세션 ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "치킨 먹고 싶어!",
                "user_id": "child_001",
                "session_id": "session_123"
            }
        }


class ChatResponse(BaseModel):
    """채팅 응답 모델"""
    response: str = Field(..., description="챗봇 응답")
    user_id: str = Field(..., description="사용자 ID")
    session_id: str = Field(..., description="세션 ID")
    timestamp: str = Field(..., description="응답 시간")
    recommendations: List[Dict[str, Any]] = Field(default_factory=list, description="추천 결과")
    follow_up_questions: List[str] = Field(default_factory=list, description="후속 질문")
    intent: str = Field(..., description="감지된 의도")
    confidence: float = Field(..., description="신뢰도")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="메타데이터")


class UserProfileResponse(BaseModel):
    """사용자 프로필 응답 모델"""
    user_id: str
    interaction_count: int
    preferred_categories: List[str]
    average_budget: float
    last_interaction: str
    data_completeness: float


class HealthResponse(BaseModel):
    """헬스체크 응답 모델"""
    status: str
    timestamp: str
    version: str
    components: Dict[str, str]


class ErrorResponse(BaseModel):
    """에러 응답 모델"""
    error: str
    message: str
    timestamp: str
    request_id: Optional[str] = None


# === 의존성 함수 ===

def get_chatbot() -> NaviyamChatbot:
    """챗봇 인스턴스 의존성"""
    if chatbot is None:
        raise HTTPException(status_code=503, detail="챗봇이 초기화되지 않았습니다")
    return chatbot


def generate_session_id() -> str:
    """세션 ID 생성"""
    return str(uuid.uuid4())


# === API 엔드포인트 ===

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """헬스체크 엔드포인트"""
    try:
        # 각 컴포넌트 상태 확인
        components = {
            "api": "healthy",
            "chatbot": "healthy" if chatbot is not None else "not_initialized",
            "database": "healthy",  # TODO: 실제 DB 연결 체크
            "redis": "healthy"      # TODO: 실제 Redis 연결 체크
        }
        
        return HealthResponse(
            status="healthy" if all(v == "healthy" for v in components.values()) else "degraded",
            timestamp=datetime.now().isoformat(),
            version="1.0.0",
            components=components
        )
    except Exception as e:
        logger.error(f"헬스체크 실패: {e}")
        raise HTTPException(status_code=503, detail="서비스 점검 중")


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기화"""
    global chatbot
    try:
        logger.info("나비얌 챗봇 API 서버 시작...")
        
        # 설정 로드
        config = load_config()
        
        # 로깅 설정
        setup_logging(config)
        
        # 챗봇 초기화
        logger.info("챗봇 초기화 중...")
        chatbot = create_naviyam_chatbot(config)
        
        logger.info("나비얌 챗봇 API 서버 초기화 완료")
        
    except Exception as e:
        logger.error(f"서버 초기화 실패: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 정리"""
    global chatbot
    try:
        logger.info("나비얌 챗봇 API 서버 종료 중...")
        
        # 챗봇 상태 저장
        if chatbot:
            chatbot.save_state("outputs/chatbot_state_backup.json")
            
        logger.info("나비얌 챗봇 API 서버 종료 완료")
        
    except Exception as e:
        logger.error(f"서버 종료 중 오류: {e}")


@app.get("/", response_model=Dict[str, str])
async def root():
    """루트 엔드포인트"""
    return {
        "message": "나비얌 챗봇 API에 오신 것을 환영합니다!",
        "docs": "/docs",
        "health": "/health",
        "version": "1.0.0"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """헬스체크 엔드포인트"""
    try:
        components = {
            "chatbot": "healthy" if chatbot and chatbot.is_initialized else "unhealthy",
            "knowledge_base": "healthy" if chatbot and chatbot.knowledge else "unhealthy",
            "model": "healthy" if chatbot and chatbot.model else "not_loaded"
        }
        
        return HealthResponse(
            status="healthy" if all(status == "healthy" for status in components.values() if status != "not_loaded") else "unhealthy",
            timestamp=datetime.now().isoformat(),
            version="1.0.0",
            components=components
        )
        
    except Exception as e:
        logger.error(f"헬스체크 실패: {e}")
        raise HTTPException(status_code=500, detail="헬스체크 실패")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, chatbot_instance: NaviyamChatbot = Depends(get_chatbot)):
    """메인 채팅 엔드포인트"""
    try:
        # 세션 ID 처리
        session_id = request.session_id or generate_session_id()
        
        # 사용자 입력 생성
        user_input = UserInput(
            text=request.message,
            user_id=request.user_id,
            session_id=session_id,
            timestamp=datetime.now()
        )
        
        # 챗봇 처리
        output: ChatbotOutput = chatbot_instance.process_user_input(user_input)
        
        # 응답 변환
        response = ChatResponse(
            response=output.response.text,
            user_id=request.user_id,
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            recommendations=output.response.recommendations,
            follow_up_questions=output.response.follow_up_questions,
            intent=output.extracted_info.intent.value,
            confidence=output.extracted_info.confidence,
            metadata=output.response.metadata
        )
        
        logger.info(f"챗봇 응답 완료 - 사용자: {request.user_id}, 의도: {output.extracted_info.intent.value}")
        return response
        
    except Exception as e:
        logger.error(f"챗봇 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"챗봇 처리 실패: {str(e)}")


@app.get("/users/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(user_id: str, chatbot_instance: NaviyamChatbot = Depends(get_chatbot)):
    """사용자 프로필 조회"""
    try:
        profile = chatbot_instance.get_user_profile(user_id)
        
        if not profile:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        return UserProfileResponse(
            user_id=profile.user_id,
            interaction_count=profile.interaction_count,
            preferred_categories=profile.preferred_categories,
            average_budget=profile.average_budget,
            last_interaction=profile.last_interaction.isoformat(),
            data_completeness=profile.data_completeness
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자 프로필 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="사용자 프로필 조회 실패")


@app.get("/users/{user_id}/history")
async def get_conversation_history(
    user_id: str, 
    count: int = 10, 
    chatbot_instance: NaviyamChatbot = Depends(get_chatbot)
):
    """대화 기록 조회"""
    try:
        history = chatbot_instance.get_conversation_history(user_id, count)
        return {
            "user_id": user_id,
            "conversation_count": len(history),
            "conversations": history
        }
        
    except Exception as e:
        logger.error(f"대화 기록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="대화 기록 조회 실패")


@app.delete("/users/{user_id}/history")
async def reset_conversation(user_id: str, chatbot_instance: NaviyamChatbot = Depends(get_chatbot)):
    """대화 기록 리셋"""
    try:
        chatbot_instance.reset_conversation(user_id)
        return {"message": f"사용자 {user_id}의 대화 기록이 리셋되었습니다"}
        
    except Exception as e:
        logger.error(f"대화 리셋 실패: {e}")
        raise HTTPException(status_code=500, detail="대화 리셋 실패")


@app.get("/metrics")
async def get_metrics(chatbot_instance: NaviyamChatbot = Depends(get_chatbot)):
    """성능 지표 조회"""
    try:
        metrics = chatbot_instance.get_performance_metrics()
        return {
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error(f"성능 지표 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="성능 지표 조회 실패")


@app.get("/knowledge/stats")
async def get_knowledge_stats(chatbot_instance: NaviyamChatbot = Depends(get_chatbot)):
    """지식베이스 통계 조회"""
    try:
        if not chatbot_instance.knowledge:
            raise HTTPException(status_code=503, detail="지식베이스를 사용할 수 없습니다")
        
        return {
            "shops_count": len(chatbot_instance.knowledge.shops),
            "menus_count": len(chatbot_instance.knowledge.menus),
            "coupons_count": len(chatbot_instance.knowledge.coupons),
            "reviews_count": len(chatbot_instance.knowledge.reviews)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"지식베이스 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="지식베이스 통계 조회 실패")


# === 에러 핸들러 ===

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP 에러 핸들러"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": exc.detail,
            "timestamp": datetime.now().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """일반 에러 핸들러"""
    logger.error(f"예상치 못한 오류: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "서버 내부 오류가 발생했습니다",
            "timestamp": datetime.now().isoformat()
        }
    )


# === 개발용 유틸리티 엔드포인트 ===

@app.post("/admin/reload")
async def reload_chatbot():
    """챗봇 재로드 (개발용)"""
    global chatbot
    try:
        logger.info("챗봇 재로드 시작...")
        
        # 기존 챗봇 정리
        if chatbot:
            chatbot.save_state("outputs/chatbot_state_before_reload.json")
        
        # 새 챗봇 초기화
        config = load_config()
        chatbot = create_naviyam_chatbot(config)
        
        logger.info("챗봇 재로드 완료")
        return {"message": "챗봇이 성공적으로 재로드되었습니다"}
        
    except Exception as e:
        logger.error(f"챗봇 재로드 실패: {e}")
        raise HTTPException(status_code=500, detail="챗봇 재로드 실패")


if __name__ == "__main__":
    import uvicorn
    
    # 개발 서버 실행
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )