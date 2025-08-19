// components/ChatHeader.tsx
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import React, { useState, useEffect, useRef } from 'react';
import { Text, TouchableOpacity, View, Alert, Animated } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { isSmallScreen, styles } from '../styles/chatStyles';
import { getUserProfile, refreshUserProfile, awardRicePul } from '../utils/ricePulManager';

export const ChatHeader = () => {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [ricePul, setRicePul] = useState(0);
  const [lastClickTime, setLastClickTime] = useState<number>(0);
  const scaleAnim = useRef(new Animated.Value(1)).current;

  // 밥풀 정보 로드
  const loadRicePul = async () => {
    try {
      const profile = await getUserProfile();
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
      // 밥풀 50개 지급
      await awardRicePul(50, '밥풀 클릭 보너스');
      setLastClickTime(now);
      
      // 즉시 UI 업데이트
      const profile = await getUserProfile();
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
          
          <TouchableOpacity onPress={() => router.back()} style={styles.closeButtonContainer}>
            <Text style={styles.closeButton}>✕</Text>
          </TouchableOpacity>
        </View>
      </View>
    </LinearGradient>
  );
};