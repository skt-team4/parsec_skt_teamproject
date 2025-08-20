# Cloudflare 고정 도메인 설정 가이드

## 🔐 Google OAuth를 위한 필수 설정

### 현재 상황
- ✅ Cloudflare 터널 실행 중 (3개 프로세스 확인)
- ❌ 임시 URL (*.trycloudflare.com)은 Google OAuth 불가

### 해결 방법: Cloudflare Zero Trust 고정 도메인

## Step 1: Cloudflare Zero Trust 설정

1. **Cloudflare 대시보드 접속**
   - https://one.dash.cloudflare.com/
   - 계정 생성/로그인

2. **Zero Trust → Access → Tunnels**
   - "Create a tunnel" 클릭
   - 터널 이름: `yumai-app`

3. **터널 설치 및 실행**
   ```cmd
   # 기존 cloudflared 중지
   taskkill /F /IM cloudflared.exe
   
   # 터널 설치 토큰 (Cloudflare 대시보드에서 복사)
   cloudflared service install [YOUR-TOKEN]
   ```

4. **Public Hostname 설정**
   - Subdomain: `yumai` (원하는 이름)
   - Domain: 선택 또는 추가
   - Type: HTTP
   - URL: `localhost:19001`

## Step 2: 추가 서비스 라우팅

같은 도메인으로 모든 서비스 접근:

| Path | Service | URL |
|------|---------|-----|
| `/` | 웹 앱 | localhost:19001 |
| `/api/chat` | 챗봇 | localhost:8000 |
| `/api/food` | 음식 인식 | localhost:5001 |
| `/api/nutrition` | 영양 분석 | localhost:5003 |

## Step 3: Google Cloud Console 설정

1. **OAuth 2.0 Client 수정**
   - https://console.cloud.google.com/apis/credentials

2. **Authorized JavaScript origins 추가:**
   ```
   https://yumai.[your-domain].com
   http://localhost:19001
   http://localhost:19000
   ```

3. **Authorized redirect URIs 추가:**
   ```
   https://yumai.[your-domain].com/redirect
   https://yumai.[your-domain].com/auth/google/callback
   http://localhost:19001/redirect
   ```

## Step 4: 앱 설정 업데이트

**.env 파일:**
```env
EXPO_PUBLIC_CLOUDFLARE_URL=https://yumai.[your-domain].com
EXPO_PUBLIC_GOOGLE_CLIENT_ID=[실제 클라이언트 ID]
EXPO_PUBLIC_USE_CLOUDFLARE=true
```

## Step 5: 실행

```cmd
# 1. 모든 서비스 시작
cd public_projects\ljm_skt_teamproject-main\ljm_skt_teamproject-main
npm run web

# 2. Cloudflare 터널 시작 (이미 실행 중이면 스킵)
cloudflared tunnel run yumai-app

# 3. 접속
# https://yumai.[your-domain].com
```

## 📝 중요 사항

### ✅ 작동하는 것:
- 고정 도메인 (yumai.example.com)
- 로컬호스트 개발

### ❌ 작동하지 않는 것:
- 임시 터널 (*.trycloudflare.com)
- 동적 URL (localtunnel 등)

## 🎯 빠른 테스트 (Google OAuth 없이)

임시 터널로도 기본 기능은 테스트 가능:
1. 로그인 화면에서 "건너뛰기" 사용
2. 카메라, 챗봇 등 기능 테스트
3. Google 로그인만 불가

## 💡 대안: ngrok 사용

ngrok은 무료로 고정 도메인 제공:
```cmd
# ngrok 설치 후
ngrok config add-authtoken [YOUR-TOKEN]
ngrok http 19001 --domain=yumai.ngrok-free.app
```

Google Console에 `yumai.ngrok-free.app` 등록