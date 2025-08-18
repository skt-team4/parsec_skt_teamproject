#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
나비얌 챗봇 API 서버 - 페르소나 기반 완전한 AI 모델 버전
"""

import sys
import os
import json
import logging
import warnings
from datetime import datetime
from typing import Optional, List, Dict, Any

warnings.filterwarnings('ignore')

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

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
    title="나비얌 챗봇 API - 페르소나 버전",
    description="아동 대상 음식 추천 AI 챗봇 API (A.X 모델 기반)",
    version="2.0.0"
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
    persona_id: Optional[str] = "minho"  # 기본값: 민호
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    weather: Optional[Dict[str, Any]] = None  # 날씨 정보 추가

class ChatResponse(BaseModel):
    response: str
    recommendations: List[Dict[str, Any]] = []
    intent: Optional[str] = None
    confidence: float = 0.0
    session_id: Optional[str] = None
    persona_info: Optional[Dict[str, Any]] = None

# 전역 변수
pipeline = None
personas_data = None
conversation_managers = {}  # user_id별 대화 관리자
user_profiles = {}  # user_id별 프로필
model_loading_status = {"status": "idle", "progress": 0, "message": "준비 중"}  # 모델 로딩 상태

def load_personas():
    """페르소나 데이터 로드"""
    global personas_data
    try:
        with open('data/personas.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        personas_data = {p['id']: p for p in data['personas']}
        logger.info(f"페르소나 데이터 로드: {list(personas_data.keys())}")
        return personas_data
    except Exception as e:
        logger.error(f"페르소나 데이터 로드 실패: {e}")
        return {}

def initialize_pipeline():
    """AI 파이프라인 초기화"""
    global pipeline, model_loading_status
    
    try:
        logger.info("AI 파이프라인 초기화 시작...")
        model_loading_status = {"status": "loading", "progress": 10, "message": "데이터베이스 로딩 중..."}
        
        # 1. 데이터 로드 (10-30%)
        from src.data.data_loader import DataLoader
        loader = DataLoader()
        knowledge = loader.load_all_data()
        logger.info(f"지식베이스 로드: {len(knowledge.shops)}개 가게")
        model_loading_status = {"status": "loading", "progress": 30, "message": "NLU 모델 로딩 중..."}
        
        # 2. NLU 모델 (30-40%)
        nlu_model = None
        try:
            from models.ax_encoder_nlu import AXEncoderNLU
            nlu_model = AXEncoderNLU('models/ax_encoder_nlu_trained')
            logger.info("NLU 모델 로드 완료")
        except:
            logger.warning("NLU 모델 로드 실패, 규칙 기반 사용")
        model_loading_status = {"status": "loading", "progress": 40, "message": "AI 모델 로딩 중... (약 1분 소요)"}
        
        # 3. NLG 모델 (40-90%)
        from models.ax_model import AXModel
        ax_model = AXModel(use_4bit=True)
        logger.info("A.X 모델 로딩 시작... (1-2분 소요)")
        model_loading_status = {"status": "loading", "progress": 50, "message": "AI 모델 다운로드 중... (50%)"}
        ax_model.load_model()
        logger.info("A.X 모델 로드 완료")
        model_loading_status = {"status": "loading", "progress": 90, "message": "파이프라인 구성 중..."}
        
        # 4. 파이프라인 구성 (90-100%)
        from src.inference.integrated_pipeline import IntegratedPipeline
        pipeline = IntegratedPipeline(
            knowledge=knowledge,
            llm_generator=ax_model,
            use_rag=True
        )
        if nlu_model:
            pipeline.ax_nlu = nlu_model
        
        model_loading_status = {"status": "ready", "progress": 100, "message": "AI 모델 준비 완료!"}
        logger.info("AI 파이프라인 초기화 완료")
        return pipeline
        
    except Exception as e:
        logger.error(f"파이프라인 초기화 실패: {e}")
        # 실패 시 간단한 폴백 모드
        return None

def get_or_create_conversation_manager(user_id: str):
    """사용자별 대화 관리자 가져오기/생성"""
    if user_id not in conversation_managers:
        from src.inference.conversation_manager import ConversationManager
        conversation_managers[user_id] = ConversationManager()
    return conversation_managers[user_id]

def load_persona_profile(persona_id: str):
    """페르소나 프로필 로드"""
    try:
        profile_path = f'data/persona_{persona_id}_profile.json'
        with open(profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        logger.warning(f"페르소나 프로필 로드 실패: {persona_id}")
        return None

def process_with_pipeline(message: str, user_id: str, persona_id: str, weather_info: Optional[Dict] = None, metadata: Optional[Dict] = None):
    """AI 파이프라인으로 메시지 처리"""
    global pipeline
    
    if pipeline is None:
        # 폴백: 로딩 상태 정보 포함
        loading_info = model_loading_status
        if loading_info["status"] == "loading":
            wait_time = "약 {} 초".format(max(10, 120 - loading_info["progress"]))
            return {
                "response": f"AI 모델 로딩 중... ({loading_info['progress']}%)\n{loading_info['message']}\n예상 대기 시간: {wait_time}",
                "recommendations": [],
                "intent": "system_loading",
                "confidence": 0.0,
                "loading_status": loading_info
            }
        else:
            return {
                "response": "죄송해요, AI 모델이 아직 준비 중이에요. 잠시 후 다시 시도해주세요.",
                "recommendations": [],
                "intent": "system_error",
                "confidence": 0.0
            }
    
    try:
        # 페르소나 정보 가져오기
        persona = personas_data.get(persona_id)
        if not persona:
            persona = personas_data.get('minho')  # 기본값
        
        # 대화 관리자
        conv_manager = get_or_create_conversation_manager(user_id)
        
        # 날씨 정보 처리 - 실제 날씨 API 사용
        if weather_info:
            weather = weather_info
        else:
            # 날씨 서비스에서 실시간 날씨 가져오기
            from src.utils.simple_weather_service import get_weather_service
            weather_service = get_weather_service()
            weather_data = weather_service.get_weather()
            weather = {
                'condition': weather_data['description'],
                'temperature': weather_data['temperature']
            }
        
        # 컨텍스트 구성
        context = {
            'user_id': user_id,
            'persona': persona,
            'timestamp': datetime.now().isoformat(),
            'weather': weather,
            'meal_card_balance': persona['meal_card_info']['balance'],
            'location': metadata.get('location') if metadata else None,
            'user_preferences': metadata.get('preferredCategories') if metadata else None,
            'user_allergies': metadata.get('allergies') if metadata else None
        }
        
        # 간결하고 명확한 시스템 프롬프트 구성
        system_prompt = f"""당신은 '그르시'입니다. YUM:AI 서비스의 AI 음식 추천 도우미 캐릭터입니다.

[그르시 소개]
• 이름: 그르시 (YUM:AI의 마스코트)
• 역할: 청소년들에게 맛있는 음식을 추천해주는 친구
• 특징: 친근하고 재미있는 음식 전문가

[대화 중인 사용자]
• 이름: {persona['name']} ({persona['age']}세)
• 급식카드 잔액: {persona['meal_card_info']['balance']:,}원
• 좋아하는 음식: {', '.join(persona['preferences']['liked_foods'][:2])}"""
        
        # 페르소나별 특별 정보 (간결하게)
        if persona_id == 'myeong_bin':
            dietary = persona['teen_personalizer_features'].get('dietary_restrictions', ['땅콩', '새우'])
            system_prompt += f"\n• ⚠️ 알레르기: {', '.join(dietary[:2])}"
        elif persona_id == 'min_ho':
            if persona['meal_card_info']['balance'] < 10000:
                system_prompt += f"\n• ⚠️ 잔액 부족 (1만원 미만)"
        elif persona_id == 'tae_hoon':
            system_prompt += f"\n• 선호: 편의점, 간편식"
        
        # 사용자 설정 알레르기 (중요!)
        if context.get('user_allergies'):
            system_prompt += f"\n• ⚠️ 설정된 알레르기: {', '.join(context['user_allergies'])}"
        
        # 날씨 정보 (간단히)
        if weather:
            system_prompt += f"\n\n[현재 상황]"
            system_prompt += f"\n• 날씨: {weather.get('condition', '맑음')}, {weather.get('temperature', 20)}°C"
        
        # 위치 정보 (간단히)
        if context.get('location') and context['location'].get('address'):
            system_prompt += f"\n• 위치: {context['location']['address']}"
        
        # 대화 규칙 (핵심만)
        system_prompt += f"""

[대화 규칙]
1. 자기소개 질문("넌 누구야?", "너 뭐야?" 등)에는 "나는 그르시야! YUM:AI의 음식 추천 도우미지"라고 답하기
2. 짧고 친근하게 대답하기 (2-3문장)
3. 인사는 한 번만, 중복하지 않기
4. 사용자 메시지를 그대로 반복하지 않기
5. 음식 추천시 급식카드 잔액 고려
6. 알레르기 음식은 절대 추천하지 않기"""
        
        # 대화 이력 확인 (중복 인사 방지)
        recent_messages = conv_manager.get_recent_messages(user_id, count=5) if hasattr(conv_manager, 'get_recent_messages') else []
        is_first_greeting = len(recent_messages) == 0
        
        # AI 모델에 전체 컨텍스트와 함께 메시지 전달
        # 파이프라인에는 사용자 메시지만 전달 (위치 추출용)
        # 시스템 프롬프트는 user_profile에 포함
        result = pipeline.process(
            user_input=message,  # 사용자 메시지만 전달 (위치 추출용)
            user_profile={
                'user_id': user_id, 
                'persona': persona,
                'age': persona['age'],
                'balance': persona['meal_card_info']['balance'],
                'preferred_categories': persona['teen_personalizer_features']['preferred_categories'],
                'dietary_restrictions': persona['teen_personalizer_features'].get('dietary_restrictions', []),
                'system_context': system_prompt,  # 시스템 프롬프트를 프로필에 포함
                'is_first_greeting': is_first_greeting  # 첫 인사 여부
            },
            user_id=user_id
        )
        
        # 결과 포맷팅
        recommendations = []
        if hasattr(result, 'metadata') and result.metadata:
            recs = result.metadata.get('recommendations', [])
            for rec in recs[:3]:  # 최대 3개
                recommendations.append({
                    'id': rec.get('id', ''),
                    'name': rec.get('shop_name', rec.get('name', '')),
                    'category': rec.get('category', ''),
                    'address': rec.get('address', ''),
                    'rating': rec.get('rating', 0.0),
                    'price': rec.get('price', 0)
                })
        
        # 응답 텍스트 정제 (중복 제거)
        response_text = result.text if hasattr(result, 'text') else str(result)
        
        # 응답 안정화: 너무 긴 응답 자르기
        if len(response_text) > 300:
            response_text = response_text[:297] + "..."
        
        # 대화 이력 저장
        conv_manager.add_message(user_id, 'user', message)
        conv_manager.add_message(user_id, 'assistant', response_text)
        
        return {
            "response": response_text,
            "recommendations": recommendations,
            "intent": result.metadata.get('intent', 'general') if hasattr(result, 'metadata') else "general",
            "confidence": result.metadata.get('confidence', 0.85) if hasattr(result, 'metadata') else 0.85,
            "persona_info": {
                "name": persona['name'],
                "age": persona['age'],
                "balance": persona['meal_card_info']['balance']
            }
        }
        
    except Exception as e:
        logger.error(f"파이프라인 처리 오류: {e}")
        # 에러 시 간단한 응답 (첫 인사만)
        greeting = "안녕하세요! " if len(conversation_managers.get(user_id, [])) == 0 else ""
        return {
            "response": f"{greeting}무엇을 도와드릴까요? {persona['name']}님께 맛있는 음식을 추천해드릴게요!",
            "recommendations": [],
            "intent": "greeting",
            "confidence": 0.5,
            "persona_info": {
                "name": persona['name'],
                "age": persona['age'],
                "balance": persona['meal_card_info']['balance']
            }
        }

# === API 엔드포인트 ===

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기화"""
    logger.info("서버 시작, 데이터 로딩 중...")
    load_personas()
    # AI 모델 로딩은 비동기로 진행 (첫 요청 시 로드)
    logger.info("서버 준비 완료")

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "나비얌 챗봇 API - 페르소나 버전",
        "version": "2.0.0",
        "status": "running",
        "model": "A.X 3.1 Lite",
        "available_personas": list(personas_data.keys()) if personas_data else [],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """헬스체크"""
    return {
        "status": "healthy",
        "pipeline_ready": pipeline is not None,
        "model_loading": model_loading_status,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """채팅 엔드포인트"""
    global pipeline
    
    try:
        logger.info(f"채팅 요청: user={request.user_id}, persona={request.persona_id}, message={request.message[:50]}...")
        
        # 파이프라인 초기화 (첫 요청 시)
        if pipeline is None:
            logger.info("첫 요청 - AI 모델 로딩 시작...")
            pipeline = initialize_pipeline()
        
        # 메타데이터 로깅
        if request.metadata:
            logger.info(f"메타데이터 수신: {request.metadata}")
        
        # 메시지 처리
        result = process_with_pipeline(
            request.message,
            request.user_id,
            request.persona_id or "minho",
            request.weather,  # 날씨 정보 전달
            request.metadata  # 메타데이터(위치 정보 포함) 전달
        )
        
        # 응답 생성
        response = ChatResponse(
            response=result["response"],
            recommendations=result["recommendations"],
            intent=result["intent"],
            confidence=result["confidence"],
            session_id=request.session_id or f"session_{request.user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            persona_info=result.get("persona_info")
        )
        
        logger.info(f"채팅 응답: intent={result['intent']}, recommendations={len(result['recommendations'])}")
        return response
        
    except Exception as e:
        logger.error(f"채팅 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/personas")
async def get_personas():
    """사용 가능한 페르소나 목록"""
    if not personas_data:
        load_personas()
    
    return {
        "personas": [
            {
                "id": p_id,
                "name": p["name"],
                "age": p["age"],
                "description": p["description"],
                "balance": p["meal_card_info"]["balance"]
            }
            for p_id, p in personas_data.items()
        ]
    }

@app.get("/users/{user_id}/profile")
async def get_user_profile(user_id: str):
    """사용자 프로필 조회"""
    # 실제 구현 시 데이터베이스에서 조회
    return {
        "user_id": user_id,
        "interaction_count": len(conversation_managers.get(user_id, [])),
        "preferred_categories": [],
        "average_budget": 8000,
        "last_interaction": datetime.now().isoformat(),
        "data_completeness": 0.7
    }

@app.get("/users/{user_id}/history")
async def get_conversation_history(user_id: str, count: int = 10):
    """대화 기록 조회"""
    conv_manager = conversation_managers.get(user_id)
    if not conv_manager:
        return {
            "user_id": user_id,
            "conversation_count": 0,
            "conversations": []
        }
    
    # 실제 구현 필요
    return {
        "user_id": user_id,
        "conversation_count": 0,
        "conversations": []
    }

if __name__ == "__main__":
    print("NaviYam Chatbot API Server (Persona Version) Starting...")
    print("Address: http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")
    print("Chat Endpoint: POST http://localhost:8000/chat")
    print("Note: First request will take 1-2 minutes to load AI models")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )