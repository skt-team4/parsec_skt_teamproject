#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
나비얌 챗봇 간단한 API 서버
"""

import sys
import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="나비얌 챗봇 API",
    description="아동 대상 음식 추천 AI 챗봇 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 출처 허용 (프로덕션에서는 특정 도메인만 허용)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 요청/응답 모델
class ChatRequest(BaseModel):
    message: str
    user_id: str = "guest"
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    recommendations: List[Dict[str, Any]] = []
    intent: Optional[str] = None
    confidence: float = 0.0
    session_id: Optional[str] = None

# 간단한 챗봇 응답 (UnifiedChatbotV2를 사용하지 않고 직접 구현)
class SimpleChatbot:
    def __init__(self):
        self.restaurants = self.load_restaurants()
        logger.info(f"SimpleChatbot 초기화: {len(self.restaurants)} 개 레스토랑 로드")
    
    def load_restaurants(self):
        """레스토랑 데이터 로드"""
        try:
            restaurants_path = os.path.join("src", "data", "restaurants_real.json")
            if os.path.exists(restaurants_path):
                with open(restaurants_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('shops', [])
        except Exception as e:
            logger.error(f"레스토랑 데이터 로드 실패: {e}")
        return []
    
    def process(self, message: str, user_id: str = "guest") -> Dict[str, Any]:
        """메시지 처리"""
        # 간단한 키워드 기반 응답
        message_lower = message.lower()
        
        # 의도 분석
        intent = "general"
        recommendations = []
        
        if "치킨" in message or "chicken" in message_lower:
            intent = "food_chicken"
            response = "🍗 치킨 좋아하시는군요! 오늘은 바삭한 치킨 어떠세요? 근처에 맛있는 치킨집이 많아요!"
            # 치킨 레스토랑 추천
            recommendations = [r for r in self.restaurants if r.get('category') == '치킨' or '치킨' in r.get('name', '')][:3]
            
        elif "피자" in message or "pizza" in message_lower:
            intent = "food_pizza"
            response = "🍕 피자 먹고 싶으시군요! 치즈가 쭉쭉 늘어나는 맛있는 피자 추천해드릴게요!"
            recommendations = [r for r in self.restaurants if r.get('category') == '피자' or '피자' in r.get('name', '')][:3]
            
        elif "햄버거" in message or "burger" in message_lower:
            intent = "food_burger"
            response = "🍔 햄버거 좋아하시는군요! 육즙이 가득한 수제버거 어떠세요?"
            recommendations = [r for r in self.restaurants if r.get('category') == '햄버거' or '버거' in r.get('name', '')][:3]
            
        elif "한식" in message or "김치" in message or "된장" in message:
            intent = "food_korean"
            response = "🍚 한식이 최고죠! 오늘은 따뜻한 집밥 같은 한식 어떠세요?"
            recommendations = [r for r in self.restaurants if r.get('category') == '한식'][:3]
            
        elif "중식" in message or "짜장" in message or "짬뽕" in message:
            intent = "food_chinese"
            response = "🥟 중식 좋아하시는군요! 짜장면, 짬뽕, 탕수육... 뭐든 맛있어요!"
            recommendations = [r for r in self.restaurants if r.get('category') == '중식'][:3]
            
        elif "안녕" in message or "하이" in message or "hello" in message_lower:
            intent = "greeting"
            response = "안녕하세요! 🙋 나비얌이에요~ 오늘 뭐 먹을지 고민되시나요? 제가 맛있는 음식 추천해드릴게요!"
            
        elif "추천" in message or "뭐 먹" in message:
            intent = "recommendation"
            response = "🍽️ 오늘은 이런 음식 어떠세요? 치킨, 피자, 햄버거, 한식, 중식... 뭐든 좋아요! 어떤 음식이 끌리시나요?"
            # 랜덤 추천
            import random
            recommendations = random.sample(self.restaurants, min(3, len(self.restaurants)))
            
        else:
            response = "네, 무엇을 도와드릴까요? 😊 맛있는 음식을 추천해드릴 수 있어요!"
        
        return {
            "response": response,
            "recommendations": [
                {
                    "id": r.get("id", ""),
                    "name": r.get("name", ""),
                    "category": r.get("category", ""),
                    "address": r.get("address", ""),
                    "rating": r.get("rating", 0.0)
                } for r in recommendations
            ],
            "intent": intent,
            "confidence": 0.85
        }

# 챗봇 인스턴스
chatbot = SimpleChatbot()

# === API 엔드포인트 ===

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "나비얌 챗봇 API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """헬스체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """채팅 엔드포인트"""
    try:
        logger.info(f"채팅 요청: user={request.user_id}, message={request.message[:50]}...")
        
        # 챗봇 처리
        result = chatbot.process(request.message, request.user_id)
        
        # 응답 생성
        response = ChatResponse(
            response=result["response"],
            recommendations=result["recommendations"],
            intent=result["intent"],
            confidence=result["confidence"],
            session_id=request.session_id or f"session_{request.user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        
        logger.info(f"채팅 응답: intent={result['intent']}, recommendations={len(result['recommendations'])}")
        return response
        
    except Exception as e:
        logger.error(f"채팅 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/profile")
async def get_user_profile(user_id: str):
    """사용자 프로필 조회 (더미 구현)"""
    return {
        "user_id": user_id,
        "interaction_count": 0,
        "preferred_categories": [],
        "average_budget": 15000,
        "last_interaction": datetime.now().isoformat(),
        "data_completeness": 0.5
    }

@app.get("/users/{user_id}/history")
async def get_conversation_history(user_id: str, count: int = 10):
    """대화 기록 조회 (더미 구현)"""
    return {
        "user_id": user_id,
        "conversation_count": 0,
        "conversations": []
    }

@app.get("/docs")
async def custom_swagger_ui_html():
    """API 문서 리다이렉트"""
    return {"message": "API 문서는 /docs 에서 확인하실 수 있습니다."}

if __name__ == "__main__":
    print("NaviYam Chatbot API Server Starting...")
    print("Address: http://localhost:8080")
    print("API Docs: http://localhost:8080/docs")
    print("Chat Endpoint: POST http://localhost:8080/chat")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info"
    )