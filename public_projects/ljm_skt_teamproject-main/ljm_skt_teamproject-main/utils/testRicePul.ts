// testRicePul.ts - 밥풀 시스템 테스트
import AsyncStorage from '@react-native-async-storage/async-storage';

// 모든 스토리지 키 출력
export const debugAllStorage = async () => {
  console.log('🔍 === 전체 스토리지 디버깅 ===');
  try {
    const allKeys = await AsyncStorage.getAllKeys();
    console.log('모든 키:', allKeys);
    
    for (const key of allKeys) {
      const value = await AsyncStorage.getItem(key);
      console.log(`${key}: ${value?.substring(0, 100)}`);
    }
  } catch (error) {
    console.error('스토리지 디버깅 실패:', error);
  }
};

// 밥풀 직접 설정 테스트
export const testSetRicePul = async (amount: number) => {
  console.log(`💰 테스트: 밥풀을 ${amount}개로 설정`);
  
  try {
    // 1. 직접 RICE_PUL_KEY에 저장
    await AsyncStorage.setItem('user_rice_pul', amount.toString());
    console.log('✅ user_rice_pul 저장 완료');
    
    // 2. 프로필에도 저장
    const profileJson = await AsyncStorage.getItem('user_profile');
    let profile = profileJson ? JSON.parse(profileJson) : {
      name: '사용자',
      ricePul: 0,
      totalEarnedRicePul: 0,
      totalSpentRicePul: 0,
      totalMealSpent: 0,
      joinDate: Date.now()
    };
    
    profile.ricePul = amount;
    profile.totalEarnedRicePul = amount;
    
    await AsyncStorage.setItem('user_profile', JSON.stringify(profile));
    console.log('✅ user_profile 저장 완료');
    
    // 3. 레벨 정보도 저장
    const level = {
      level: 1,
      currentExp: amount,
      expToNext: Math.max(0, 100 - amount),
      title: "밥풀 새싹",
      benefits: ["기본 추천 기능"]
    };
    await AsyncStorage.setItem('user_rice_pul_level', JSON.stringify(level));
    console.log('✅ user_rice_pul_level 저장 완료');
    
    // 4. 저장된 값 확인
    const savedRicePul = await AsyncStorage.getItem('user_rice_pul');
    const savedProfile = await AsyncStorage.getItem('user_profile');
    const parsedProfile = savedProfile ? JSON.parse(savedProfile) : null;
    
    console.log('📊 저장 결과:');
    console.log('  - user_rice_pul:', savedRicePul);
    console.log('  - profile.ricePul:', parsedProfile?.ricePul);
    
    return true;
  } catch (error) {
    console.error('❌ 테스트 실패:', error);
    return false;
  }
};

// 밥풀 로드 테스트
export const testLoadRicePul = async () => {
  console.log('📖 밥풀 로드 테스트');
  
  try {
    const ricePul = await AsyncStorage.getItem('user_rice_pul');
    const profile = await AsyncStorage.getItem('user_profile');
    const level = await AsyncStorage.getItem('user_rice_pul_level');
    
    console.log('1. user_rice_pul:', ricePul);
    console.log('2. user_profile:', profile ? JSON.parse(profile) : null);
    console.log('3. user_rice_pul_level:', level ? JSON.parse(level) : null);
    
    return {
      ricePul: ricePul ? parseInt(ricePul) : 0,
      profileRicePul: profile ? JSON.parse(profile).ricePul : 0
    };
  } catch (error) {
    console.error('로드 실패:', error);
    return null;
  }
};