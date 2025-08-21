// services/apiService.ts
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_ENDPOINTS, WEATHER_API_KEY } from '../config/api.config';

export type MealCategory = 'distance' | 'cost' | 'preference' | 'allergy';

// OpenWeatherMap API로 날씨 정보 가져오기
async function getWeatherInfo(latitude?: number, longitude?: number) {
  try {
    // API 키 사용
    const API_KEY = WEATHER_API_KEY;
    
    // 위치 정보가 없으면 저장된 위치 또는 서울 기본값 사용
    let lat = latitude || 37.5665;
    let lon = longitude || 126.9780;
    
    if (!latitude || !longitude) {
      // AsyncStorage에서 위치 정보 확인
      try {
        const savedAddress = await AsyncStorage.getItem('userAddress');
        if (savedAddress) {
          const addressInfo = JSON.parse(savedAddress);
          lat = addressInfo.latitude || lat;
          lon = addressInfo.longitude || lon;
        } else {
          const savedLocation = await AsyncStorage.getItem('userLocation');
          if (savedLocation) {
            const coords = JSON.parse(savedLocation);
            lat = coords.latitude || lat;
            lon = coords.longitude || lon;
          }
        }
      } catch (error) {
        console.log('저장된 위치 정보 로드 실패');
      }
    }
    
    const url = `https://api.openweathermap.org/data/2.5/weather?lat=${lat}&lon=${lon}&appid=${API_KEY}&units=metric&lang=kr`;
    
    const response = await fetch(url);
    if (response.ok) {
      const data = await response.json();
      
      // 날씨 상태 매핑
      const main = data.weather[0].main.toLowerCase();
      let condition = '맑음';
      
      if (main.includes('rain')) condition = '비';
      else if (main.includes('snow')) condition = '눈';  
      else if (main.includes('cloud')) condition = '흐림';
      else if (main.includes('clear')) condition = '맑음';
      
      return {
        condition: condition,
        temperature: Math.round(data.main.temp),
        description: data.weather[0].description,
        city: data.name || '현재 위치'
      };
    }
  } catch (error) {
    console.log('날씨 정보 가져오기 실패, 기본값 사용');
  }
  
  // 기본값 반환
  return {
    condition: '맑음',
    temperature: 20,
    city: '서울'
  };
}

export type ApiResponse = {
  success: boolean;
  message: string;
  data?: {
    recommendations?: any[];
    category?: string;
    usage?: any;
  };
  error?: string;
};

export type Message = {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: Date;
  category?: string;
};

// 페르소나 기반 챗봇 API 설정
const API_CONFIG = {
  defaultPersona: 'min_ho', // 기본 페르소나: 김민호 (17세)
  timeout: parseInt(process.env.EXPO_PUBLIC_API_TIMEOUT || '30000'), // 30초 (첫 요청 시 모델 로딩)
};

// 현재 선택된 페르소나 (앱 전체에서 사용)
let currentPersona = API_CONFIG.defaultPersona;

// 카테고리별 시스템 프롬프트 생성
const getCategoryPrompt = (category?: MealCategory) => {
  const basePrompt = `당신은 "얌이"라는 이름의 친근하고 귀여운 음식 추천 및 길 안내 AI입니다. 
어린이들이 좋아할 만한 톤으로 대화합니다.
응답은 한국어로 하며, 200자 이내로 간결하게 답변해주세요.
이모지를 적절히 사용해서 친근하게 답변해주세요.`;

  const categoryPrompts = {
    distance: `${basePrompt}\n지금은 "거리/접근성" 관련 급식 추천을 요청받았습니다. 현재 위치 주변에서 먹을 수 있는 메뉴를 추천해주세요.`,
    cost: `${basePrompt}\n지금은 "가격/영양" 관련 음식 추천을 요청받았습니다. 경제적이면서도 영양가 높은 메뉴를 추천해주세요.`,
    preference: `${basePrompt}\n지금은 "선호도" 관련 급식 추천을 요청받았습니다. 평소에 뭐 좋아하는지 물어보고 그에 맞는 음식 및 음식점 추천해주세요.`,
    allergy: `${basePrompt}\n지금은 "알레르기" 관련 정보를 요청받았습니다. 사용자의 알레르기 정보를 물어보고 안전한 식사에 대해 안내해주세요.`
  };

  return category ? categoryPrompts[category] : basePrompt;
};


// 페르소나 기반 챗봇 메시지 전송
export async function sendChatMessage(message: string, category?: MealCategory): Promise<ApiResponse> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.timeout);

    // 위치 정보 가져오기 - userAddress와 userLocation 둘 다 체크
    let locationData = null;
    try {
      // 먼저 상세 주소 정보 확인
      const savedAddress = await AsyncStorage.getItem('userAddress');
      if (savedAddress) {
        const addressInfo = JSON.parse(savedAddress);
        locationData = {
          address: addressInfo.address,
          latitude: addressInfo.latitude,
          longitude: addressInfo.longitude,
          detailAddress: addressInfo.detailAddress
        };
      } else {
        // 주소가 없으면 위치 좌표만이라도 확인
        const savedLocation = await AsyncStorage.getItem('userLocation');
        if (savedLocation) {
          const coords = JSON.parse(savedLocation);
          locationData = {
            latitude: coords.latitude,
            longitude: coords.longitude,
            address: `위도: ${coords.latitude}, 경도: ${coords.longitude}`
          };
        }
      }
    } catch (error) {
      console.log('위치 정보 로드 오류:', error);
    }
    
    // 추가 설정 정보 가져오기
    let additionalSettings = {};
    try {
      // 선호 카테고리
      const categories = await AsyncStorage.getItem('selectedCategories');
      if (categories) {
        additionalSettings.preferredCategories = JSON.parse(categories);
      }
      
      // 알레르기 정보
      const allergies = await AsyncStorage.getItem('selectedAllergies');
      if (allergies) {
        additionalSettings.allergies = JSON.parse(allergies);
      }
      
      // 애니메이션 설정 (사용자 접근성 선호도)
      const animationEnabled = await AsyncStorage.getItem('animationEnabled');
      if (animationEnabled !== null) {
        additionalSettings.animationEnabled = JSON.parse(animationEnabled);
      }
    } catch (error) {
      console.log('추가 설정 로드 오류:', error);
    }

    const response = await fetch(API_ENDPOINTS.chat(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: message.trim(),
        user_id: 'mobile_user',
        persona_id: currentPersona,
        metadata: {
          category: category,
          prompt_context: getCategoryPrompt(category),
          location: locationData,  // 상세 위치 정보 추가
          ...additionalSettings  // 추가 설정 정보 (알레르기, 선호 카테고리 등)
        },
        weather: await getWeatherInfo()  // 날씨 정보 추가
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(`Chatbot API error: ${response.status} - ${errorData.detail || 'Unknown error'}`);
    }

    const data = await response.json();
    
    // 페르소나 정보 포함 응답 처리
    let responseMessage = data.response;
    if (data.persona_info) {
      // 페르소나 정보를 응답에 자연스럽게 포함 (선택적)
      const balance = data.persona_info.balance;
      if (balance && data.recommendations && data.recommendations.length > 0) {
        // 잔액 정보를 포함한 추천
        responseMessage += `\n💰 현재 급식카드 잔액: ${balance.toLocaleString()}원`;
      }
    }

    return {
      success: true,
      message: responseMessage,
      data: {
        recommendations: data.recommendations || [],
        category: data.intent || category,
        persona_info: data.persona_info,
      }
    };
  } catch (error) {
    console.error('Chatbot API 호출 오류:', error);
    
    // 타임아웃 오류 - 로딩 상태 확인
    if (error instanceof Error && error.name === 'AbortError') {
      // 헬스체크로 로딩 상태 확인
      try {
        const healthResponse = await fetch(API_ENDPOINTS.health());
        if (healthResponse.ok) {
          const health = await healthResponse.json();
          if (health.model_loading && health.model_loading.status === 'loading') {
            const progress = health.model_loading.progress;
            const message = health.model_loading.message;
            const waitTime = Math.max(10, 120 - progress); // 예상 대기 시간 (초)
            
            return {
              success: false,
              message: `⏰ AI 모델 로딩 중... (${progress}%)\n${message}\n예상 대기 시간: 약 ${waitTime}초`,
              error: 'Model loading',
            };
          }
        }
      } catch (e) {
        // 헬스체크 실패 시 기본 메시지
      }
      
      return {
        success: false,
        message: '⏰ 응답 시간이 초과되었어요. AI 모델을 로딩 중일 수 있으니 잠시 후 다시 시도해주세요.',
        error: 'Request timeout',
      };
    }
    
    // 서버 연결 오류
    if (error instanceof Error && (error.message.includes('fetch') || error.message.includes('Failed'))) {
      return {
        success: false,
        message: '⚠️ 챗봇 서버에 연결할 수 없어요. 서버가 실행 중인지 확인해주세요.',
        error: 'Server connection failed',
      };
    }

    return {
      success: false,
      message: '죄송해요, 일시적으로 응답할 수 없어요. 잠시 후 다시 시도해 주세요. 🥺',
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

// 페르소나 타입 정의
export type Persona = {
  id: string;
  name: string;
  age: number;
  description: string;
  balance: number;
};

// 페르소나 목록 가져오기
export async function getPersonas(): Promise<Persona[]> {
  try {
    // 타임아웃 설정 (5초)
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    
    const response = await fetch(API_ENDPOINTS.personas(), {
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    
    if (!response.ok) {
      throw new Error('Failed to fetch personas');
    }
    const data = await response.json();
    return data.personas || [];
  } catch (error) {
    console.error('페르소나 목록 조회 실패:', error);
    console.log('기본 페르소나 목록 사용');
    // 기본 페르소나 반환 (서버 연결 실패 시)
    return [
      { id: 'min_ho', name: '김민호', age: 17, description: '17세 고등학생', balance: 20000 },
      { id: 'myeong_bin', name: '김명빈', age: 14, description: '14세 중학생', balance: 100000 },
      { id: 'tae_hoon', name: '강태훈', age: 12, description: '12세 초등학생', balance: 50000 },
    ];
  }
}

// 현재 페르소나 설정
export function setCurrentPersona(personaId: string) {
  currentPersona = personaId;
  console.log(`페르소나 변경: ${personaId}`);
}

// 현재 페르소나 가져오기
export function getCurrentPersona(): string {
  return currentPersona;
}

// 카테고리별 추천 메시지
const categoryQuestions = {
  distance: '학교 근처에서 쉽게 구할 수 있는 재료로 만든 오늘의 급식 메뉴를 추천해주세요',
  cost: '경제적이면서도 영양가 높은 급식 메뉴를 추천해주세요',
  preference: '아이들이 가장 좋아하는 인기 급식 메뉴를 추천해주세요',
  allergy: '급식의 알레르기 주의사항과 안전한 식사 방법에 대해 알려주세요'
};

// 카테고리별 추천
export async function getCategoryRecommendation(category: MealCategory): Promise<ApiResponse> {
  try {
    return await sendChatMessage(categoryQuestions[category], category);
  } catch (error) {
    console.error('카테고리 추천 오류:', error);
    return {
      success: false,
      message: '추천 메뉴를 불러오는 중 오류가 발생했어요. 다시 시도해 주세요. 😅',
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}