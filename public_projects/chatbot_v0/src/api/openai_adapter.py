"""
OpenAI API 호환 어댑터
프론트엔드가 GPT API 형식으로 요청하면 나비얌 챗봇 형식으로 변환
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
import uuid
import logging

from src.inference.chatbot import NaviyamChatbot
from src.data.data_structure import UserInput

logger = logging.getLogger(__name__)

# OpenAI API 호환 라우터
router = APIRouter(prefix="/v1")


# === OpenAI 형식 모델 정의 ===

class Message(BaseModel):
    """OpenAI 메시지 형식"""
    role: Literal["system", "user", "assistant"] = Field(..., description="메시지 역할")
    content: str = Field(..., description="메시지 내용")
    name: Optional[str] = Field(None, description="발신자 이름")


class ChatCompletionRequest(BaseModel):
    """OpenAI ChatCompletion 요청 형식"""
    model: str = Field("gpt-3.5-turbo", description="모델 이름 (무시됨)")
    messages: List[Message] = Field(..., description="대화 메시지 목록")
    temperature: Optional[float] = Field(0.7, ge=0, le=2, description="생성 온도")
    max_tokens: Optional[int] = Field(None, description="최대 토큰 수")
    stream: Optional[bool] = Field(False, description="스트리밍 여부")
    user: Optional[str] = Field(None, description="사용자 ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "user", "content": "치킨 먹고 싶어"}
                ]
            }
        }


class ChatCompletionChoice(BaseModel):
    """OpenAI 응답 선택지"""
    index: int = 0
    message: Message
    finish_reason: str = "stop"


class ChatCompletionUsage(BaseModel):
    """토큰 사용량 (더미 데이터)"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """OpenAI ChatCompletion 응답 형식"""
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:8]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    model: str = "naviyam-chatbot"
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage = Field(default_factory=ChatCompletionUsage)


# === 어댑터 함수 ===

def extract_user_message(messages: List[Message]) -> str:
    """메시지 목록에서 마지막 사용자 메시지 추출"""
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    
    # 사용자 메시지가 없으면 마지막 메시지 사용
    if messages:
        return messages[-1].content
    
    raise ValueError("메시지가 비어있습니다")


def extract_conversation_context(messages: List[Message]) -> str:
    """대화 컨텍스트 추출 (선택적)"""
    context_parts = []
    for msg in messages[:-1]:  # 마지막 메시지 제외
        if msg.role == "user":
            context_parts.append(f"사용자: {msg.content}")
        elif msg.role == "assistant":
            context_parts.append(f"챗봇: {msg.content}")
    
    return "\n".join(context_parts) if context_parts else ""


def convert_to_openai_format(naviyam_response: str, 
                            recommendations: List[Dict] = None,
                            metadata: Dict = None) -> ChatCompletionResponse:
    """나비얌 응답을 OpenAI 형식으로 변환"""
    
    # 추천 정보가 있으면 응답에 포함
    if recommendations and len(recommendations) > 0:
        rec_text = "\n\n추천 음식점:\n"
        for i, rec in enumerate(recommendations[:3], 1):
            name = rec.get('name', '알 수 없음')
            category = rec.get('category', '')
            price = rec.get('average_price', 0)
            rec_text += f"{i}. {name}"
            if category:
                rec_text += f" ({category})"
            if price:
                rec_text += f" - 평균 {price:,}원"
            rec_text += "\n"
        naviyam_response += rec_text
    
    # OpenAI 형식으로 포장
    response_message = Message(
        role="assistant",
        content=naviyam_response
    )
    
    choice = ChatCompletionChoice(
        index=0,
        message=response_message,
        finish_reason="stop"
    )
    
    # 더미 토큰 사용량 (실제로는 계산 가능)
    usage = ChatCompletionUsage(
        prompt_tokens=len(naviyam_response.split()) * 2,
        completion_tokens=len(naviyam_response.split()),
        total_tokens=len(naviyam_response.split()) * 3
    )
    
    return ChatCompletionResponse(
        model="naviyam-chatbot",
        choices=[choice],
        usage=usage
    )


# === API 엔드포인트 ===

def get_chatbot_instance():
    """챗봇 인스턴스 가져오기 (서버에서 오버라이드됨)"""
    return None

@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    chatbot_instance: NaviyamChatbot = Depends(get_chatbot_instance)
):
    """OpenAI ChatCompletion API 호환 엔드포인트"""
    
    try:
        # 스트리밍은 현재 지원하지 않음
        if request.stream:
            raise HTTPException(
                status_code=400, 
                detail="스트리밍은 현재 지원되지 않습니다"
            )
        
        # 사용자 메시지 추출
        user_message = extract_user_message(request.messages)
        
        # 사용자 ID 결정 (request.user 또는 기본값)
        user_id = request.user or "openai_user"
        
        # 세션 ID 생성
        session_id = f"openai_session_{uuid.uuid4().hex[:8]}"
        
        # 대화 컨텍스트 추출 (선택적)
        context = extract_conversation_context(request.messages)
        
        # 나비얌 형식으로 변환
        user_input = UserInput(
            text=user_message,
            user_id=user_id,
            session_id=session_id,
            timestamp=datetime.now(),
            context=context if context else None
        )
        
        # 챗봇이 초기화되지 않은 경우 간단한 폴백 응답
        if chatbot_instance is None:
            logger.warning("챗봇이 초기화되지 않았습니다. 폴백 응답 반환")
            fallback_response = "죄송합니다. 현재 서비스 준비 중입니다. 잠시 후 다시 시도해주세요."
            return convert_to_openai_format(fallback_response)
        
        # 나비얌 챗봇 호출
        try:
            output = chatbot_instance.process_user_input(user_input)
            
            # OpenAI 형식으로 변환
            return convert_to_openai_format(
                naviyam_response=output.response.text,
                recommendations=output.response.recommendations,
                metadata=output.response.metadata
            )
            
        except Exception as e:
            logger.error(f"챗봇 처리 중 오류: {e}")
            error_response = "죄송합니다. 요청을 처리하는 중 오류가 발생했습니다."
            return convert_to_openai_format(error_response)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"OpenAI 어댑터 오류: {e}")
        raise HTTPException(
            status_code=500, 
            detail="내부 서버 오류가 발생했습니다"
        )


@router.get("/models")
async def list_models():
    """사용 가능한 모델 목록 (OpenAI API 호환)"""
    return {
        "object": "list",
        "data": [
            {
                "id": "naviyam-chatbot",
                "object": "model",
                "created": int(datetime.now().timestamp()),
                "owned_by": "naviyam",
                "permission": [],
                "root": "naviyam-chatbot",
                "parent": None
            }
        ]
    }


@router.get("/models/{model_id}")
async def get_model(model_id: str):
    """모델 정보 조회 (OpenAI API 호환)"""
    if model_id != "naviyam-chatbot":
        raise HTTPException(status_code=404, detail="모델을 찾을 수 없습니다")
    
    return {
        "id": "naviyam-chatbot",
        "object": "model",
        "created": int(datetime.now().timestamp()),
        "owned_by": "naviyam",
        "permission": [],
        "root": "naviyam-chatbot",
        "parent": None
    }