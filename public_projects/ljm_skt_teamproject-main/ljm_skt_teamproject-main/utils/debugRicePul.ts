// debugRicePul.ts - 밥풀 디버깅 유틸리티
import AsyncStorage from '@react-native-async-storage/async-storage';

// 모든 밥풀 관련 스토리지 키 확인
export const debugRicePulStorage = async () => {
  try {
    console.log('🔍 === 밥풀 스토리지 디버깅 시작 ===');
    
    // 개별 키 확인
    const ricePul = await AsyncStorage.getItem('user_rice_pul');
    console.log('1. user_rice_pul:', ricePul);
    
    const ricePulLevel = await AsyncStorage.getItem('user_rice_pul_level');
    console.log('2. user_rice_pul_level:', ricePulLevel ? JSON.parse(ricePulLevel) : null);
    
    const userProfile = await AsyncStorage.getItem('user_profile');
    console.log('3. user_profile:', userProfile ? JSON.parse(userProfile) : null);
    
    const mealCard = await AsyncStorage.getItem('meal_card_balance');
    console.log('4. meal_card_balance:', mealCard ? JSON.parse(mealCard) : null);
    
    const transactions = await AsyncStorage.getItem('integrated_transaction_history');
    const txHistory = transactions ? JSON.parse(transactions) : [];
    console.log('5. 최근 거래 5개:', txHistory.slice(0, 5));
    
    // 모든 키 확인
    const allKeys = await AsyncStorage.getAllKeys();
    console.log('6. 모든 스토리지 키:', allKeys.filter(key => 
      key.includes('rice') || key.includes('meal') || key.includes('profile')
    ));
    
    console.log('🔍 === 디버깅 종료 ===');
    
    return {
      ricePul: ricePul ? parseInt(ricePul) : 0,
      profile: userProfile ? JSON.parse(userProfile) : null,
      level: ricePulLevel ? JSON.parse(ricePulLevel) : null,
      mealCard: mealCard ? JSON.parse(mealCard) : null,
      recentTransactions: txHistory.slice(0, 5)
    };
  } catch (error) {
    console.error('❌ 디버깅 실패:', error);
    return null;
  }
};

// 밥풀 직접 설정 (테스트용)
export const setRicePulDirectly = async (amount: number) => {
  try {
    console.log(`💰 밥풀을 ${amount}개로 직접 설정`);
    
    // 개별 키 업데이트
    await AsyncStorage.setItem('user_rice_pul', amount.toString());
    
    // 프로필도 업데이트
    const profileJson = await AsyncStorage.getItem('user_profile');
    if (profileJson) {
      const profile = JSON.parse(profileJson);
      profile.ricePul = amount;
      await AsyncStorage.setItem('user_profile', JSON.stringify(profile));
    }
    
    console.log('✅ 밥풀 설정 완료');
    return true;
  } catch (error) {
    console.error('❌ 밥풀 설정 실패:', error);
    return false;
  }
};

// 스토리지 동기화 확인
export const checkStorageSync = async () => {
  try {
    const ricePulKey = await AsyncStorage.getItem('user_rice_pul');
    const profileJson = await AsyncStorage.getItem('user_profile');
    
    const ricePulFromKey = ricePulKey ? parseInt(ricePulKey) : 0;
    const ricePulFromProfile = profileJson ? JSON.parse(profileJson).ricePul : 0;
    
    const isSynced = ricePulFromKey === ricePulFromProfile;
    
    console.log('🔄 동기화 상태:', {
      'user_rice_pul 키': ricePulFromKey,
      'user_profile의 ricePul': ricePulFromProfile,
      '동기화됨': isSynced ? '✅' : '❌'
    });
    
    return {
      ricePulKey: ricePulFromKey,
      ricePulProfile: ricePulFromProfile,
      isSynced
    };
  } catch (error) {
    console.error('동기화 확인 실패:', error);
    return null;
  }
};