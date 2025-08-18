#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
간단한 Mock API 서버 - 빠른 응답 테스트용
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn
import random

app = FastAPI(
    title="Simple Mock Chatbot API",
    description="빠른 응답 테스트용 Mock API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 요청/응답 모델
class ChatRequest(BaseModel):
    message: str
    user_id: str = "guest"
    persona_id: Optional[str] = "min_ho"
    metadata: Optional[Dict[str, Any]] = None
    weather: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    recommendations: List[Dict[str, Any]] = []
    intent: Optional[str] = None
    confidence: float = 0.0
    session_id: Optional[str] = None
    persona_info: Optional[Dict[str, Any]] = None

# 페르소나 데이터
personas = {
    "min_ho": {"name": "김민호", "age": 17, "balance": 20000},
    "myeong_bin": {"name": "김명빈", "age": 14, "balance": 100000},
    "tae_hoon": {"name": "강태훈", "age": 12, "balance": 50000}
}

# Mock 응답 생성
def generate_mock_response(message: str, persona_id: str):
    persona = personas.get(persona_id, personas["min_ho"])
    
    # 간단한 패턴 매칭
    if "이름" in message:
        return f"안녕하세요! {persona['name']}님! 😊"
    elif "나이" in message:
        return f"{persona['age']}살이시네요!"
    elif "잔액" in message or "돈" in message:
        return f"급식카드 잔액은 {persona['balance']:,}원이에요!"
    elif "치킨" in message:
        return "🍗 치킨 좋아하시는구나! 근처에 맛있는 치킨집이 있어요!"
    elif "피자" in message:
        return "🍕 피자 먹고 싶으시군요! 도미노피자랑 피자헛 중에 어디가 좋으세요?"
    elif "날씨" in message:
        return "🌤️ 오늘 날씨 좋네요! 밖에서 먹는 것도 좋을 것 같아요!"
    else:
        responses = [
            "맛있는 음식 추천해드릴게요! 😋",
            "오늘은 뭐 드시고 싶으세요?",
            "제가 맛있는 곳 알아요!",
            f"{persona['name']}님, 배고프신가요?",
        ]
        return random.choice(responses)

@app.get("/")
async def root():
    return {
        "service": "Mock Chatbot API",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Mock 응답 생성
        response_text = generate_mock_response(request.message, request.persona_id or "min_ho")
        persona = personas.get(request.persona_id or "min_ho")
        
        return ChatResponse(
            response=response_text,
            recommendations=[],
            intent="general",
            confidence=0.95,
            session_id=f"session_{request.user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            persona_info=persona
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/personas")
async def get_personas():
    return {
        "personas": [
            {"id": k, "name": v["name"], "age": v["age"], "balance": v["balance"]}
            for k, v in personas.items()
        ]
    }

if __name__ == "__main__":
    print("Starting Mock Chatbot API Server...")
    print("Address: http://localhost:8000")
    print("Chat Endpoint: POST http://localhost:8000/chat")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )