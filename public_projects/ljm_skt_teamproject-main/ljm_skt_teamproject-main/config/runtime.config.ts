// 런타임 환경 설정 (동적 로드)
export const RUNTIME_CONFIG = {
  // Cloudflare URLs - 실시간 업데이트 가능
  APP_URL: 'https://intend-territory-method-mirrors.trycloudflare.com',  // 19000 포트 터널 (앱)
  PROXY_URL: 'https://bedrooms-mem-costs-fish.trycloudflare.com', // 19001 포트 터널 (API/지도)
  USE_REMOTE_API: true,
};

// API URL 생성 함수
export const getRuntimeApiUrl = (port: number, path: string = ''): string => {
  if (RUNTIME_CONFIG.USE_REMOTE_API) {
    return `${RUNTIME_CONFIG.PROXY_URL}/api/${port}${path}`;
  }
  return `http://localhost:${port}${path}`;
};

// 지도 URL 
export const getMapUrl = (): string => {
  if (RUNTIME_CONFIG.USE_REMOTE_API) {
    return `${RUNTIME_CONFIG.PROXY_URL}/map`;
  }
  return 'http://localhost:19001/map';
};