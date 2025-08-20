// config/cloudflare.config.ts
// Cloudflare 터널과 Google OAuth 연동 설정

import { Platform } from 'react-native';

// Cloudflare 터널 URL (실제 URL로 교체 필요)
const CLOUDFLARE_URL = process.env.EXPO_PUBLIC_CLOUDFLARE_URL || 'https://your-app.trycloudflare.com';

export const cloudflareConfig = {
  // 앱 URL 설정
  getAppUrl: () => {
    if (Platform.OS === 'web') {
      // 웹에서 실행 중일 때
      if (typeof window !== 'undefined') {
        const currentUrl = window.location.origin;
        
        // Cloudflare 터널에서 실행 중인지 확인
        if (currentUrl.includes('trycloudflare.com') || currentUrl.includes('cloudflare')) {
          return currentUrl;
        }
        
        // 로컬 개발
        if (currentUrl.includes('localhost')) {
          return currentUrl;
        }
        
        // 기본값
        return CLOUDFLARE_URL;
      }
    }
    
    // 모바일 앱
    return 'http://localhost:19001';
  },
  
  // Google OAuth 리다이렉트 URI
  getGoogleRedirectUri: () => {
    const appUrl = cloudflareConfig.getAppUrl();
    return `${appUrl}/redirect`;
  },
  
  // API 엔드포인트 설정
  getApiUrl: (endpoint: string) => {
    const appUrl = cloudflareConfig.getAppUrl();
    
    // Cloudflare 터널 사용 시
    if (appUrl.includes('trycloudflare.com')) {
      switch (endpoint) {
        case 'chat':
          return `${appUrl.replace('19001', '8000')}/chat`;
        case 'food':
          return `${appUrl.replace('19001', '5001')}/analyze`;
        case 'nutrition':
          return `${appUrl.replace('19001', '5003')}/analyze-nutrition`;
        default:
          return `${appUrl.replace('19001', '8000')}/${endpoint}`;
      }
    }
    
    // 로컬 개발
    return `http://localhost:8000/${endpoint}`;
  },
  
  // 임시 터널 URL인지 확인
  isTempTunnel: () => {
    const appUrl = cloudflareConfig.getAppUrl();
    return appUrl.includes('trycloudflare.com');
  },
  
  // Google OAuth 가능 여부
  isGoogleOAuthAvailable: () => {
    // 임시 터널에서는 Google OAuth 불가
    if (cloudflareConfig.isTempTunnel()) {
      console.warn('⚠️ 임시 Cloudflare 터널에서는 Google OAuth를 사용할 수 없습니다.');
      console.warn('고정 도메인 설정이 필요합니다.');
      return false;
    }
    
    // 로컬호스트 또는 고정 도메인에서만 가능
    const appUrl = cloudflareConfig.getAppUrl();
    return appUrl.includes('localhost') || !appUrl.includes('trycloudflare.com');
  }
};

export default cloudflareConfig;