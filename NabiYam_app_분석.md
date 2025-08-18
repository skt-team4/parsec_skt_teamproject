# 나비얌(NabiYam) 모바일 앱 분석

## 📋 프로젝트 개요

**NabiYam_chatbot_expo**는 어린이를 위한 급식 및 음식 추천 모바일 앱입니다. React Native와 Expo를 기반으로 개발되었으며, 인천시 급식카드 결제 시스템과 연동된 챗봇 기능을 제공합니다.

### 🎯 주요 기능
- 급식 메뉴 추천 챗봇 ("얌이")
- 인천시 급식카드 결제 연동
- 캠페인 및 혜택 정보
- 크로스 플랫폼 지원 (iOS/Android/Web)

## 🏗️ 프로젝트 구조

```
NabiYam_chatbot_expo/
├── 📱 앱 화면
│   ├── app/
│   │   ├── (tabs)/                  # 탭 네비게이션
│   │   │   ├── index.tsx           # 홈 화면 (메인)
│   │   │   ├── explore.tsx         # 탐색 화면
│   │   │   └── _layout.tsx         # 탭 레이아웃
│   │   ├── chat.tsx                # 챗봇 화면 (핵심 기능)
│   │   ├── _layout.tsx             # 루트 레이아웃
│   │   └── +not-found.tsx          # 404 화면
│   │
├── 🎨 UI 컴포넌트
│   ├── components/
│   │   ├── ThemedText.tsx          # 테마 텍스트
│   │   ├── ThemedView.tsx          # 테마 뷰
│   │   ├── ParallaxScrollView.tsx  # 패럴랙스 스크롤
│   │   └── ui/                     # UI 유틸리티
│   │
├── 🎭 에셋
│   ├── assets/
│   │   ├── images/                 # 앱 아이콘, 로고
│   │   └── fonts/                  # 커스텀 폰트
│   │
├── 🔧 설정
│   ├── constants/Colors.ts         # 색상 테마
│   ├── hooks/                      # 커스텀 훅
│   ├── app.json                    # Expo 설정
│   ├── package.json                # 의존성
│   └── tsconfig.json              # TypeScript 설정
```

## 📱 앱 화면 구조

### 1️⃣ 홈 화면 (`index.tsx`)
- **나비얌** 메인 브랜딩
- 인천시 급식카드 결제 안내 배너
- 캠페인 정보 ("도시락 한컵, 마음 한 숟갈")
- 인천광역시 전용 서비스 안내

### 2️⃣ 챗봇 화면 (`chat.tsx`)
- **"얌이"** 음식 도우미 챗봇
- 실시간 대화 인터페이스
- 키워드 기반 메뉴 추천 시스템
- 4가지 카테고리 지원:
  - `오늘 메뉴`: 일일 추천 급식
  - `건강 메뉴`: 영양 중심 추천  
  - `도시락`: 도시락 메뉴 추천
  - `알레르기`: 알레르기 안내

### 3️⃣ 탐색 화면 (`explore.tsx`)
- 추가 기능 및 정보 탐색

## 🤖 챗봇 기능 분석

### 대화 흐름
```typescript
사용자 입력 → analyzeInput() → generateResponse() → UI 업데이트
```

### 지원하는 키워드
- **"오늘", "추천"** → 오늘의 급식 메뉴
- **"건강", "영양"** → 건강한 메뉴 추천
- **"도시락"** → 도시락 메뉴 추천
- **"알레르기", "주의"** → 알레르기 안내

### 샘플 메뉴 데이터
```typescript
// 오늘 메뉴 예시
{ name: '비빔밥', description: '색깔 야채가 가득한 영양 만점 급식!', emoji: '🍚' }
{ name: '된장찌개', description: '따뜻하고 건강한 한식 메뉴!', emoji: '🍲' }
{ name: '잡채', description: '쫄깃한 당면과 야채의 조화!', emoji: '🍜' }
```

## 🧪 테스트 방법

### 1️⃣ 개발 환경 설정

```bash
# 프로젝트 디렉토리로 이동
cd /Volumes/samsd/skt_teamproject/publicproject/NabiYam_app/NabiYam_app-main/NabiYam_chatbot_expo

# Node.js 및 npm 버전 확인
node --version  # v22.17.1
npm --version   # 10.9.2

# 의존성 설치
npm install
```

### 2️⃣ 앱 실행

```bash
# 개발 서버 시작
npx expo start

# 또는 직접 스크립트 실행
npm start
```

### 3️⃣ 플랫폼별 실행

| 플랫폼 | 명령어 | 설명 |
|--------|--------|------|
| **웹** | `w` 키 또는 `npm run web` | 브라우저에서 실행 |
| **iOS** | `i` 키 또는 `npm run ios` | iOS 시뮬레이터 |
| **Android** | `a` 키 또는 `npm run android` | Android 에뮬레이터 |
| **Expo Go** | QR 코드 스캔 | 실제 디바이스 테스트 |

### 4️⃣ 개발 도구

```bash
# 코드 품질 검사
npm run lint

# 프로젝트 초기화 (필요시)
npm run reset-project
```

## 🔧 기술 스택

### 프레임워크
- **React Native 0.79.5**: 크로스 플랫폼 앱 개발
- **Expo ~53.0.20**: 개발 및 배포 플랫폼
- **TypeScript 5.8.3**: 정적 타입 검사

### 네비게이션
- **Expo Router 5.1.4**: 파일 기반 라우팅
- **React Navigation**: 화면 네비게이션

### UI/UX
- **Expo Linear Gradient**: 그라데이션 효과
- **React Native Safe Area Context**: 안전 영역 처리
- **Expo Symbols**: 시스템 아이콘

### 개발 도구
- **ESLint**: 코드 품질 관리
- **Babel**: JavaScript 트랜스파일링

## 🎨 디자인 시스템

### 색상 팔레트
- **주요 색상**: `#FFBF00` (나비얌 옐로우)
- **그라데이션**: `#4A90E2` → `#7B68EE` (블루 투 퍼플)
- **배경**: `#FFFBF0` (따뜻한 화이트)

### 레이아웃 특징
- 모달 기반 챗봇 UI (화면의 75% 높이)
- 안전 영역 고려한 반응형 디자인
- 키보드 회피 레이아웃

## 📡 API 연동 가능성

현재는 로컬 데이터 기반이지만, 다음과 같은 API 연동이 가능합니다:

```typescript
// chat_bot_proto와 연동 예시
const chatAPI = 'http://localhost:8000/chat';
const response = await fetch(chatAPI, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: inputText, user_id: 'mobile_user' })
});
```

## 🚀 배포 준비사항

### Expo 빌드
```bash
# 프로덕션 빌드
npx expo build:android
npx expo build:ios

# 또는 EAS Build 사용
npx eas build --platform android
npx eas build --platform ios
```

### 앱스토어 준비
- **iOS**: App Store Connect 설정
- **Android**: Google Play Console 설정
- **Web**: 정적 사이트 배포

## 💡 개선 제안사항

### 1. 백엔드 연동
- chat_bot_proto API와 실시간 통신
- 사용자 인증 및 개인화

### 2. 기능 확장
- 위치 기반 맛집 추천
- 실시간 급식 메뉴 업데이트
- 푸시 알림

### 3. UX 개선
- 음성 인식 챗봇
- 이미지 기반 메뉴 추천
- 오프라인 모드 지원

## 📈 개발 상태

### ✅ 완료된 기능
- [x] 기본 Expo 앱 구조
- [x] 챗봇 UI/UX
- [x] 키워드 기반 메뉴 추천
- [x] 크로스 플랫폼 지원
- [x] 타입스크립트 적용

### 🚧 개선 필요사항
- [ ] 실제 API 연동
- [ ] 사용자 인증
- [ ] 실시간 데이터 동기화
- [ ] 성능 최적화
- [ ] 접근성 개선

---

**나비얌 앱은 어린이 친화적인 급식 도우미로서 큰 잠재력을 가지고 있습니다! 🍱✨**