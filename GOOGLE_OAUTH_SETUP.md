# Google OAuth + Cloudflare 설정 가이드

## 🎯 핵심: IP 주소가 아닌 도메인 등록!

### Step 1: Google Cloud Console 설정

1. [Google Cloud Console](https://console.cloud.google.com) 접속
2. APIs & Services → Credentials → OAuth 2.0 Client IDs 선택
3. **Authorized JavaScript origins** 추가:
   ```
   https://yumai.yourdomain.com
   http://localhost:19000
   http://localhost:19001
   ```

4. **Authorized redirect URIs** 추가:
   ```
   https://yumai.yourdomain.com/redirect
   https://yumai.yourdomain.com/auth/google/callback
   http://localhost:19000/redirect
   http://localhost:19001/redirect
   ```

### Step 2: 환경 변수 설정

`.env` 파일 수정:
```env
EXPO_PUBLIC_GOOGLE_CLIENT_ID=실제_클라이언트_ID
EXPO_PUBLIC_GOOGLE_CLIENT_SECRET=실제_시크릿_키
EXPO_PUBLIC_APP_URL=https://yumai.yourdomain.com
EXPO_PUBLIC_USE_REMOTE_API=true
```

### Step 3: 앱 설정 수정

`config/auth.config.ts` 수정:
```typescript
export const authConfig = {
  googleClientId: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID,
  redirectUri: process.env.EXPO_PUBLIC_APP_URL 
    ? `${process.env.EXPO_PUBLIC_APP_URL}/redirect`
    : 'http://localhost:19001/redirect'
};
```

## 📝 중요 사항

### ✅ 해야 할 것:
- **고정 도메인 사용** (Cloudflare Tunnel 또는 실제 도메인)
- **HTTPS 필수** (Cloudflare가 자동 제공)
- **도메인을 Google Console에 등록**

### ❌ 하지 말아야 할 것:
- **모든 IP 허용 불가** (Google이 허용하지 않음)
- **와일드카드 도메인 사용 불가** (*.loca.lt 등)
- **동적 URL 사용 불가** (localtunnel 등)

## 🚀 빠른 해결책

### 옵션 1: Cloudflare 무료 터널 (추천)
```bash
# 1. Cloudflare 계정 생성
# 2. Zero Trust → Access → Tunnels
# 3. Create Tunnel → 이름 입력 → Save
# 4. Public Hostname 추가:
#    - Subdomain: yumai
#    - Domain: 선택 또는 구매
#    - Service: http://localhost:19001

# 5. 터널 실행
cloudflared tunnel run yumai-app
```

### 옵션 2: ngrok 유료 플랜
```bash
# ngrok 유료 계정으로 고정 도메인 받기
ngrok http 19001 --domain=yumai.ngrok.app
```

### 옵션 3: 실제 도메인 구매 + Cloudflare
1. 도메인 구매 (예: yumai.app)
2. Cloudflare DNS 설정
3. Cloudflare Tunnel 연결

## 🔧 디버깅

Google OAuth 에러 발생 시:
1. Console → APIs & Services → OAuth consent screen
2. Authorized domains에 도메인 추가 확인
3. Test users에 테스트 계정 추가 (개발 중)

## 💡 팁

- **개발용**: localhost 유지
- **테스트용**: Cloudflare 터널 + 고정 도메인
- **프로덕션**: 실제 서버 + 도메인 + SSL

## 📱 모바일 테스트

Expo Go 앱에서 테스트 시:
```javascript
// app.json
{
  "expo": {
    "scheme": "yumai",
    "web": {
      "bundler": "metro",
      "redirect": {
        "google": "https://yumai.yourdomain.com/redirect"
      }
    }
  }
}
```