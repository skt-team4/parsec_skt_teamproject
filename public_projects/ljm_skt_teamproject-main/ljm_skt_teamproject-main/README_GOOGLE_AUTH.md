# Google OAuth 설정 가이드

## 포트 설정 보장 방법

### 문제점
다른 환경에서 파일을 실행할 때 포트 19000이 이미 사용 중이면 Expo가 다른 포트를 선택할 수 있습니다.

### 해결 방법

#### 1. **스크립트 사용 (권장)**

**Windows:**
```bash
start-web.bat
```

**Mac/Linux:**
```bash
chmod +x start-web.sh
./start-web.sh
```

이 스크립트는:
- 포트 19000이 사용 중인지 확인
- 사용 중이면 해당 프로세스 종료
- 항상 포트 19000으로 Expo 실행

#### 2. **package.json 스크립트 사용**
```bash
npm run web
```
- `--port 19000` 옵션이 설정되어 있음
- 포트가 사용 중이면 에러 발생 (의도적)

#### 3. **수동으로 포트 확인**
```bash
# Windows
netstat -ano | findstr :19000

# Mac/Linux  
lsof -i :19000
```

## Google Cloud Console 설정

### 필수 Redirect URI (한 번만 등록)
```
http://localhost:19000
http://localhost:19000/redirect
```

### 설정 방법
1. https://console.cloud.google.com 접속
2. APIs & Services → Credentials
3. OAuth 2.0 Client ID 선택
4. Authorized redirect URIs에 위 URI 추가
5. Save

## 다른 환경에서 실행 시

### 방법 1: 스크립트 사용 (권장)
```bash
# Windows
start-web.bat

# Mac/Linux
./start-web.sh
```

### 방법 2: 강제 포트 지정
```bash
npx expo start --web --port 19000 --clear
```

### 방법 3: 포트 충돌 시 해결
```bash
# 포트 19000 사용 중인 프로세스 확인
netstat -ano | findstr :19000

# 프로세스 종료 후 재실행
taskkill /F /PID [프로세스ID]
npm run web
```

## 환경 변수 설정

`.env` 파일:
```env
EXPO_PUBLIC_GOOGLE_CLIENT_ID=571027176154-rbn3v218tr53ncv0memk7m9tqkp34e1i.apps.googleusercontent.com
EXPO_PUBLIC_API_URL=http://localhost:8000
```

## 트러블슈팅

### "redirect_uri_mismatch" 오류
- 브라우저 콘솔에서 실제 Redirect URI 확인
- Google Console에 정확히 같은 URI 등록
- 5분 정도 기다린 후 재시도

### 포트 충돌
- `start-web.bat` 또는 `start-web.sh` 사용
- 수동으로 기존 프로세스 종료

### 다른 포트로 실행되는 경우
- `.expo/settings.json`에 `"port": 19000` 설정 확인
- 스크립트 사용으로 강제 실행

## 배포 시 추가 설정

프로덕션 환경에서는 실제 도메인 추가:
```
https://your-domain.com/redirect
https://www.your-domain.com/redirect
```