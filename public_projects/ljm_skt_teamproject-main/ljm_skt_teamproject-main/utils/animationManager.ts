// animationManager.ts - 애니메이션 관리 유틸리티
import AsyncStorage from '@react-native-async-storage/async-storage';

// 모든 애니메이션 GIF 매핑
export const ALL_ANIMATIONS: Record<string, any> = {
  // 기본 동작
  'Hi': require('../assets/Hi.gif'),
  'Sad': require('../assets/Sad.gif'),
  'Dance': require('../assets/Dance.gif'),
  'Jump': require('../assets/Jump.gif'),
  'Sunglass': require('../assets/Sunglass.gif'),
  'Gunchim': require('../assets/Gunchim.gif'),
  
  // Hi 조합
  'Hi_계란말이': require('../assets/Hi_계란말이.gif'),
  'Hi_김': require('../assets/Hi_김.gif'),
  'Hi_명란': require('../assets/Hi_명란.gif'),
  'Hi_베이컨': require('../assets/Hi_베이컨.gif'),
  'Hi_연어': require('../assets/Hi_연어.gif'),
  'Hi_후라이': require('../assets/Hi_후라이.gif'),
  'Hi_매우편중': require('../assets/Hi_매우편중.gif'),
  'Hi_편중식사': require('../assets/Hi_편중식사.gif'),
  
  // Dance 조합
  'Dance_계란말이': require('../assets/Dance_계란말이.gif'),
  'Dance_김': require('../assets/Dance_김.gif'),
  'Dance_명란': require('../assets/Dance_명란.gif'),
  'Dance_베이컨': require('../assets/Dance_베이컨.gif'),
  'Dance_연어': require('../assets/Dance_연어.gif'),
  'Dance_후라이': require('../assets/Dance_후라이.gif'),
  
  // Jump 조합
  'Jump_계란말이': require('../assets/Jump_계란말이.gif'),
  'Jump_김': require('../assets/Jump_김.gif'),
  'Jump_명란': require('../assets/Jump_명란.gif'),
  'Jump_베이컨': require('../assets/Jump_베이컨.gif'),
  'Jump_연어': require('../assets/Jump_연어.gif'),
  'Jump_후라이': require('../assets/Jump_후라이.gif'),
  
  // Sad 조합
  'Sad_계란말이': require('../assets/Sad_계란말이.gif'),
  'Sad_김': require('../assets/Sad_김.gif'),
  'Sad_명란': require('../assets/Sad_명란.gif'),
  'Sad_베이컨': require('../assets/Sad_베이컨.gif'),
  'Sad_연어': require('../assets/Sad_연어.gif'),
  'Sad_후라이': require('../assets/Sad_후라이.gif'),
  'Sad_매우편중': require('../assets/Sad_매우편중.gif'),
  'Sad_편중식사': require('../assets/Sad_편중식사.gif'),
};

// 현재 선택된 애니메이션 로드
export const loadCurrentAnimation = async (): Promise<string> => {
  try {
    const current = await AsyncStorage.getItem('shop_current_animation');
    return current || 'Hi';
  } catch (error) {
    console.error('Error loading current animation:', error);
    return 'Hi';
  }
};

// 애니메이션 설정 저장
export const saveCurrentAnimation = async (animationId: string): Promise<boolean> => {
  try {
    await AsyncStorage.setItem('shop_current_animation', animationId);
    console.log(`✅ Animation saved: ${animationId}`);
    return true;
  } catch (error) {
    console.error('Error saving animation:', error);
    return false;
  }
};

// 애니메이션 GIF 가져오기
export const getAnimationSource = (animationId: string) => {
  return ALL_ANIMATIONS[animationId] || ALL_ANIMATIONS['Hi'];
};

// 디버그 모드 설정
export const setDebugMode = async (enabled: boolean): Promise<void> => {
  try {
    await AsyncStorage.setItem('shop_debug_mode', JSON.stringify(enabled));
    console.log(`🐛 Debug mode: ${enabled ? 'ON' : 'OFF'}`);
  } catch (error) {
    console.error('Error setting debug mode:', error);
  }
};

// 디버그 모드 확인
export const getDebugMode = async (): Promise<boolean> => {
  try {
    const debug = await AsyncStorage.getItem('shop_debug_mode');
    return debug ? JSON.parse(debug) : false;
  } catch (error) {
    console.error('Error getting debug mode:', error);
    return false;
  }
};

// 테스트용: 모든 애니메이션 잠금 해제
export const unlockAllAnimationsForTesting = async (): Promise<void> => {
  try {
    const allActions = ['Hi', 'Sad', 'Dance', 'Jump', 'Sunglass', 'Gunchim'];
    const allIngredients = ['계란말이', '김', '명란', '베이컨', '연어', '후라이', '매우편중', '편중식사'];
    const allCombos = Object.keys(ALL_ANIMATIONS).filter(key => key.includes('_'));
    
    await AsyncStorage.setItem('shop_unlocked_actions', JSON.stringify(allActions));
    await AsyncStorage.setItem('shop_unlocked_ingredients', JSON.stringify(allIngredients));
    await AsyncStorage.setItem('shop_unlocked_combos', JSON.stringify(allCombos));
    
    console.log('🔓 All animations unlocked for testing!');
  } catch (error) {
    console.error('Error unlocking animations:', error);
  }
};

// 상점 데이터 초기화
export const resetShopData = async (): Promise<void> => {
  try {
    await AsyncStorage.multiRemove([
      'shop_unlocked_actions',
      'shop_unlocked_ingredients',
      'shop_unlocked_combos',
      'shop_current_animation',
    ]);
    
    // 기본값 설정
    await AsyncStorage.setItem('shop_unlocked_actions', JSON.stringify(['Hi']));
    await AsyncStorage.setItem('shop_current_animation', 'Hi');
    
    console.log('🔄 Shop data reset!');
  } catch (error) {
    console.error('Error resetting shop data:', error);
  }
};