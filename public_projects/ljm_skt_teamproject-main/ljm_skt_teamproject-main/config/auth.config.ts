import { Platform } from 'react-native';
import { makeRedirectUri } from 'expo-auth-session';

// 환경별 설정
// ngrok URL 또는 localhost 사용
const getDevRedirectUri = () => {
  // ngrok URL이 설정되어 있으면 사용
  if (process.env.EXPO_PUBLIC_APP_URL) {
    return `${process.env.EXPO_PUBLIC_APP_URL}/redirect`;
  }
  
  if (Platform.OS === 'web') {
    return 'http://localhost:19001/redirect';
  }
  return makeRedirectUri({
    scheme: undefined,
    preferLocalhost: true,
    path: 'redirect'
  });
};

const ENV = {
  dev: {
    apiUrl: 'http://localhost:8000',
    redirectUri: getDevRedirectUri()
  },
  staging: {
    apiUrl: 'https://staging-api.your-domain.com',
    redirectUri: 'https://staging.your-domain.com/redirect'
  },
  prod: {
    apiUrl: 'https://api.your-domain.com',
    redirectUri: 'https://your-domain.com/redirect'
  }
};

// 현재 환경 감지
const getEnvironment = () => {
  // 환경 변수로 환경 설정
  if (process.env.EXPO_PUBLIC_ENV === 'production') {
    return 'prod';
  } else if (process.env.EXPO_PUBLIC_ENV === 'staging') {
    return 'staging';
  }
  
  // 개발 환경 기본값
  return 'dev';
};

const currentEnv = getEnvironment();

export const authConfig = {
  googleClientId: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID || '571027176154-rbn3v218tr53ncv0memk7m9tqkp34e1i.apps.googleusercontent.com',
  apiUrl: ENV[currentEnv].apiUrl,
  redirectUri: ENV[currentEnv].redirectUri,
  
  // 플랫폼별 Client ID (선택사항)
  googleIosClientId: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID,
  googleAndroidClientId: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID,
  googleWebClientId: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID,
};

// 디버깅용
console.log('Auth Config:', {
  environment: currentEnv,
  redirectUri: authConfig.redirectUri,
  apiUrl: authConfig.apiUrl
});

export default authConfig;