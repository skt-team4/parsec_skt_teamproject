# Google OAuth + ngrok 설정

## 1. ngrok 도메인 확인
생성된 도메인: `[your-domain].ngrok-free.app`

## 2. Google Cloud Console 설정

### 접속
https://console.cloud.google.com/apis/credentials

### OAuth 2.0 Client ID 수정

#### Authorized JavaScript origins 추가:
```
https://[your-domain].ngrok-free.app
http://localhost:19001
http://localhost:19000
```

#### Authorized redirect URIs 추가:
```
https://[your-domain].ngrok-free.app/redirect
https://[your-domain].ngrok-free.app/auth/google/callback
http://localhost:19001/redirect
http://localhost:19000/redirect
```

## 3. 앱 환경변수 설정

`.env` 파일:
```env
EXPO_PUBLIC_GOOGLE_CLIENT_ID=[실제 클라이언트 ID]
EXPO_PUBLIC_GOOGLE_CLIENT_SECRET=[실제 시크릿]
EXPO_PUBLIC_APP_URL=https://[your-domain].ngrok-free.app
```

## 4. 실행

```cmd
# ngrok 터널 시작
ngrok.exe http 19001 --domain=[your-domain].ngrok-free.app

# 브라우저에서 접속
https://[your-domain].ngrok-free.app
```

## 5. 테스트
1. 앱 접속
2. Google 로그인 버튼 클릭
3. Google 계정으로 로그인
4. 성공!