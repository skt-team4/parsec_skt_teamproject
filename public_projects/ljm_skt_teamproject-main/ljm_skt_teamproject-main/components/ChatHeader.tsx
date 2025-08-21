// components/ChatHeader.tsx
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import React, { useState, useEffect, useRef } from 'react';
import { Text, TouchableOpacity, View, Alert, Animated } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { isSmallScreen, styles } from '../styles/chatStyles';
import { getUserProfile, refreshUserProfile, awardRicePul, clearProfileCache } from '../utils/ricePulManager';
import { debugRicePulStorage, checkStorageSync } from '../utils/debugRicePul';
import { globalEventEmitter, EVENTS } from '../utils/eventEmitter';

export const ChatHeader = () => {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [ricePul, setRicePul] = useState(0);
  const [lastClickTime, setLastClickTime] = useState<number>(0);
  const scaleAnim = useRef(new Animated.Value(1)).current;

  // 밥풀 정보 로드
  const loadRicePul = async () => {
    try {
      const profile = await refreshUserProfile();
      setRicePul(profile.ricePul);
    } catch (error) {
      console.error('밥풀 정보 로드 실패:', error);
    }
  };

  // 클릭 애니메이션 실행
  const runClickAnimation = () => {
    Animated.sequence([
      Animated.timing(scaleAnim, {
        toValue: 1.3,
        duration: 150,
        useNativeDriver: true,
      }),
      Animated.timing(scaleAnim, {
        toValue: 0.9,
        duration: 150,
        useNativeDriver: true,
      }),
      Animated.timing(scaleAnim, {
        toValue: 1,
        duration: 150,
        useNativeDriver: true,
      }),
    ]).start();
  };

  // 밥풀 클릭 핸들러 - 50개 지급
  const handleRicePulClick = async () => {
    const now = Date.now();
    const COOLDOWN_TIME = 5000; // 5초 쿨다운
    
    // 쿨다운 체크
    if (now - lastClickTime < COOLDOWN_TIME) {
      const remainingTime = Math.ceil((COOLDOWN_TIME - (now - lastClickTime)) / 1000);
      Alert.alert('잠시만 기다려주세요', `${remainingTime}초 후에 다시 받을 수 있어요!`);
      return;
    }
    
    // 애니메이션 실행
    runClickAnimation();
    
    try {
      // 디버깅: 지급 전 상태 확인
      console.log('📝 === 밥풀 지급 시작 ===');
      await debugRicePulStorage();
      
      // 밥풀 50개 지급
      const result = await awardRicePul(50, '밥풀 클릭 보너스');
      setLastClickTime(now);
      
      // 디버깅: 지급 후 상태 확인
      console.log('📝 === 밥풀 지급 후 ===');
      await debugRicePulStorage();
      await checkStorageSync();
      
      // 캐시 무효화 후 새로 로드
      clearProfileCache();
      
      // 즉시 UI 업데이트 (캐시 무시하고 강제 새로고침)
      const profile = await refreshUserProfile();
      console.log('🍚 헤더 UI 업데이트, 새 밥풀:', profile.ricePul);
      setRicePul(profile.ricePul);
      
      // 성공 메시지
      Alert.alert('밥풀 획득!', '🍚 50밥풀을 받았어요!', [
        { text: '확인', style: 'default' }
      ]);
    } catch (error) {
      console.error('밥풀 지급 실패:', error);
      Alert.alert('오류', '밥풀 지급에 실패했습니다.');
    }
  };

  // 컴포넌트가 마운트되거나 포커스될 때 밥풀 정보 로드
  useEffect(() => {
    loadRicePul();
    
    // 밥풀 업데이트 이벤트 리스너
    const handleRicePulUpdated = (data: any) => {
      console.log('💰 ChatHeader: 밥풀 업데이트 이벤트 수신', data);
      if (data?.ricePul !== undefined) {
        setRicePul(data.ricePul);
      } else {
        // 데이터가 없으면 다시 로드
        loadRicePul();
      }
    };
    
    globalEventEmitter.on(EVENTS.RICE_PUL_UPDATED, handleRicePulUpdated);
    
    return () => {
      globalEventEmitter.off(EVENTS.RICE_PUL_UPDATED, handleRicePulUpdated);
    };
  }, []);

  useFocusEffect(
    React.useCallback(() => {
      loadRicePul();
    }, [])
  );

  return (
    <LinearGradient
      colors={['#FFBF00', '#FDD046']}
      style={[styles.header, { paddingTop: insets.top + 10 }]}
    >
      <View style={styles.headerContent}>
        <View style={styles.leftSection}>
          <Text style={[styles.headerTitle, { fontSize: isSmallScreen ? 24 : 28 }]}>
            YUM:AI
          </Text>
        </View>
        
        <View style={styles.centerSection}>
          {/* 빈 공간 */}
        </View>
        
        <View style={styles.rightSection}>
          <TouchableOpacity 
            onPress={handleRicePulClick}
            style={styles.ricePulContainer}
            activeOpacity={0.7}
          >
            <Animated.View style={{ transform: [{ scale: scaleAnim }] }}>
              <Text style={styles.ricePulIcon}>🍚</Text>
            </Animated.View>
            <Text style={styles.ricePulText}>{ricePul.toLocaleString()}</Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            onPress={() => {
              console.log('X 버튼 클릭 - 메인 화면으로 이동');
              router.replace('/(tabs)');
            }} 
            style={styles.closeButtonContainer}
          >
            <Text style={styles.closeButton}>✕</Text>
          </TouchableOpacity>
        </View>
      </View>
    </LinearGradient>
  );
};