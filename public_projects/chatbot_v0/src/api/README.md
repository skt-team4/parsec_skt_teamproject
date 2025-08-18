# 나비얌 챗봇 API 서버

백엔드 담당자를 위한 FastAPI 기반 API 서버입니다.

## 🚀 빠른 시작

### 1. 서버 실행
```bash
# 개발 모드 (자동 리로드)
python -m uvicorn api.server:app --reload --host 0.0.0.0 --port 8000

# 또는 직접 실행
python api/server.py
```

### 2. API 문서 확인
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 📋 주요 엔드포인트

### 기본 정보
- `GET /` - 루트 페이지
- `GET /health` - 헬스체크
- `GET /metrics` - 성능 지표

### 채팅 API
- `POST /chat` - 메인 채팅 엔드포인트

### 사용자 관리
- `GET /users/{user_id}/profile` - 사용자 프로필 조회
- `GET /users/{user_id}/history` - 대화 기록 조회
- `DELETE /users/{user_id}/history` - 대화 기록 리셋

### 지식베이스
- `GET /knowledge/stats` - 지식베이스 통계

### 관리용 (개발)
- `POST /admin/reload` - 챗봇 재로드

## 📝 API 사용 예시

### 채팅 요청
```bash
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "치킨 먹고 싶어!",
       "user_id": "child_001",
       "session_id": "session_123"
     }'
```

### 응답 예시
```json
{
  "response": "치킨 좋아하는구나! 맛있는 치킨집을 찾아볼게! 🍗",
  "user_id": "child_001",
  "session_id": "session_123",
  "timestamp": "2025-07-29T10:30:45.123456",
  "recommendations": [
    {
      "shop_name": "맛있는치킨",
      "menu": "후라이드치킨",
      "price": 15000
    }
  ],
  "follow_up_questions": [
    "어떤 종류의 치킨을 좋아해?",
    "예산은 얼마나 생각하고 있어?"
  ],
  "intent": "FOOD_REQUEST",
  "confidence": 0.95,
  "metadata": {
    "generation_method": "template"
  }
}
```

## 🛠 개발 가이드

### 새 엔드포인트 추가
1. `api/server.py`에 새 함수 추가
2. 요청/응답 모델 정의 (Pydantic 사용)
3. 적절한 에러 핸들링 추가
4. 로깅 추가

### 미들웨어 추가
```python
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

class CustomMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # 미들웨어 로직
        response = await call_next(request)
        return response

app.add_middleware(CustomMiddleware)
```

### 의존성 주입
```python
from fastapi import Depends

def get_database():
    # 데이터베이스 연결 로직
    return db

@app.get("/data")
async def get_data(db = Depends(get_database)):
    # db 사용
    return data
```

## 🔧 설정

### 환경변수
- `API_HOST`: 서버 호스트 (기본값: 0.0.0.0)
- `API_PORT`: 서버 포트 (기본값: 8000)
- `LOG_LEVEL`: 로그 레벨 (기본값: info)

### CORS 설정
프로덕션에서는 `allow_origins`를 특정 도메인으로 제한:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

## 📊 모니터링

### 로그 확인
```bash
# 실시간 로그 확인
tail -f outputs/naviyam_chatbot.log

# 에러 로그만 확인
grep ERROR outputs/naviyam_chatbot.log
```

### 성능 지표
```bash
curl http://localhost:8000/metrics
```

## 🚨 에러 처리

### 표준 에러 응답
```json
{
  "error": "ERROR_CODE",
  "message": "사용자 친화적 에러 메시지",
  "timestamp": "2025-07-29T10:30:45.123456",
  "request_id": "optional_request_id"
}
```

### 주요 에러 코드
- `400 Bad Request`: 잘못된 요청
- `404 Not Found`: 리소스 없음
- `500 Internal Server Error`: 서버 오류
- `503 Service Unavailable`: 챗봇 초기화 안됨

## 🔄 배포

### Docker 배포 (예정)
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### systemd 서비스 (Linux)
```ini
[Unit]
Description=Naviyam Chatbot API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/aiyam_chatbot
ExecStart=/path/to/venv/bin/uvicorn api.server:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## 🧪 테스트

### 단위 테스트 실행
```bash
pytest tests/test_api.py -v
```

### API 테스트
```bash
# 헬스체크
curl http://localhost:8000/health

# 채팅 테스트
curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "안녕", "user_id": "test"}'
```

## 📚 추가 개발 항목

### 인증/인가 (예정)
- JWT 토큰 기반 인증
- 사용자 권한 관리
- API 키 관리

### 데이터베이스 연동 (예정)
- PostgreSQL/MySQL 연동
- 사용자 데이터 영구 저장
- 대화 기록 저장

### 캐싱 (예정)
- Redis 캐싱
- 응답 캐싱
- 세션 관리

### 비동기 처리 (예정)
- Celery 작업 큐
- 백그라운드 작업
- 알림 시스템