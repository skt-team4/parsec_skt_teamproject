// API Configuration
const isProduction = process.env.NODE_ENV === 'production';

// 개발 환경에서는 localhost, 프로덕션에서는 터널 URL 사용
export const API_CONFIG = {
  // 로컬 개발용
  LOCAL: {
    FOOD_RECOGNITION: 'http://localhost:5001',
    NUTRITION: 'http://localhost:5003',
    NUTRITION_HISTORY: 'http://localhost:5004',
    CHATBOT: 'http://localhost:8000',
  },
  
  // 외부 접속용 (Cloudflare Tunnel)
  REMOTE: {
    FOOD_RECOGNITION: 'https://buying-polymer-tricks-kai.trycloudflare.com',
    NUTRITION: 'https://queensland-brick-loved-briefly.trycloudflare.com',
    NUTRITION_HISTORY: 'http://192.168.50.2:5004',
    CHATBOT: 'http://192.168.50.2:8000',
  }
};

// 환경 변수나 플래그로 전환
export const useRemoteAPI = process.env.EXPO_PUBLIC_USE_REMOTE_API === 'true';

export const getAPIUrl = (service: keyof typeof API_CONFIG.LOCAL) => {
  return useRemoteAPI ? API_CONFIG.REMOTE[service] : API_CONFIG.LOCAL[service];
};