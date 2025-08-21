// Import runtime config for dynamic URL loading
import { RUNTIME_CONFIG } from './runtime.config';

// API URL 동적 설정 - runtime config 사용
export const getApiUrl = (port: number, path: string = '') => {
  // 원격 API 사용 시 Cloudflare 프록시 서버 사용
  if (RUNTIME_CONFIG.USE_REMOTE_API) {
    // Runtime config에서 Cloudflare 프록시 서버 URL 가져오기
    return `${RUNTIME_CONFIG.PROXY_URL}/api/${port}${path}`;
  }
  
  // 로컬 개발 환경
  return `http://localhost:${port}${path}`;
};

// API 엔드포인트 설정
export const API_ENDPOINTS = {
  // 메인 챗봇 API (포트 8000)
  chat: () => getApiUrl(8000, '/chat'),
  personas: () => getApiUrl(8000, '/personas'),
  health: () => getApiUrl(8000, '/health'),
  
  // 음식 인식 API (포트 5001)
  foodRecognition: () => getApiUrl(5001, '/analyze'),
  foodList: () => getApiUrl(5001, '/foods'),
  
  // 영양 정보 API (포트 5002)
  nutritionStatic: (foodName: string) => getApiUrl(5002, `/nutrition/${foodName}`),
  
  // LogMeal 영양 분석 API (포트 5003)
  nutritionAnalyze: () => getApiUrl(5003, '/analyze-nutrition'),
  
  // 영양 기록 API (포트 5004)
  nutritionHistory: () => getApiUrl(5004, '/api/get-history'),
  nutritionSave: () => getApiUrl(5004, '/api/save-nutrition'),
  nutritionStats: () => getApiUrl(5004, '/api/get-statistics'),
  nutritionDelete: (recordId: string) => getApiUrl(5004, `/api/delete-record/${recordId}`),
  
  // 지도 서버 API (포트 5007)
  mapServer: () => getApiUrl(5007, ''),
};

// T-Map API 설정 (외부 API, ngrok 영향 없음)
export const TMAP_API_KEY = 'F1YRiyhnpe2JhzqhlotAu8LF56DUKeQD9cA4Uxxb';

// OpenWeatherMap API 설정 (외부 API, ngrok 영향 없음)
export const WEATHER_API_KEY = '72cade2afd8d0b233391812e15fda078';