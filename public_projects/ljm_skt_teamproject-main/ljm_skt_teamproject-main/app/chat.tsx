// chat.tsx - 캐릭터 상점 연동 버전 (밥풀 시스템 적용)
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useFocusEffect } from '@react-navigation/native';
import { Image } from 'expo-image';
import { StatusBar } from 'expo-status-bar';
import React, { useCallback, useEffect, useState } from 'react';
import {
  Animated,
  ScrollView,
  Text,
  TouchableOpacity,
  View
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

// 분리된 파일들 import
import CharacterShopModal from '../components/CharacterShopModal'; // 상점 모달 import
import { ChatHeader } from '../components/ChatHeader';
import { ChatInput } from '../components/ChatInput';
import { SpeechBubble } from '../components/SpeechBubble';
import useChatLogic from '../hooks/useChatLogic'; // 기본 import로 변경
import { isSmallScreen, SCREEN_HEIGHT, styles } from '../styles/chatStyles';
import { awardRicePul, clearProfileCache } from '../utils/ricePulManager'; // 밥풀 매니저 import
import { 
  loadCurrentAnimation, 
  getAnimationSource, 
  ALL_ANIMATIONS,
  getDebugMode,
  setDebugMode,
  unlockAllAnimationsForTesting 
} from '../utils/animationManager'; // 애니메이션 매니저 import
import { 
  generateDailyNutritionReport, 
  getCharacterAnimationByNutrition 
} from '../utils/nutritionAnalyzer'; // 영양 분석 import
import { globalEventEmitter, EVENTS } from '../utils/eventEmitter'; // 이벤트 시스템 import


// Expo Router 옵션
export const options = {
  gestureEnabled: false,
  swipeEnabled: false,
  presentation: 'card',
};

export default function ChatScreen() {
  const insets = useSafeAreaInsets();
  
  // 로딩 애니메이션 상태
  const [showLoading, setShowLoading] = useState(true);
  const [showMessage, setShowMessage] = useState(false);
  
  // 애니메이션 설정 상태
  const [isAnimationEnabled, setIsAnimationEnabled] = useState(true);
  const [currentAnimationId, setCurrentAnimationId] = useState('Hi');
  const [currentAnimationSource, setCurrentAnimationSource] = useState(ALL_ANIMATIONS['Hi']);
  
  // 상점 모달 상태
  const [showShopModal, setShowShopModal] = useState(false);
  
  // 디버그 모드
  const [debugMode, setDebugModeState] = useState(false);
  
  // 애니메이션 값들 (초기 로딩용)
  const [animValues] = useState([
    new Animated.Value(0),
    new Animated.Value(0),
    new Animated.Value(0),
  ]);

  // API 로딩 애니메이션 값들 - SpeechBubble로 전달
  const [apiLoadingAnimValues] = useState([
    new Animated.Value(0),
    new Animated.Value(0),
    new Animated.Value(0),
  ]);

  // 커스텀 훅에서 로직 가져오기 (handleGifClick, awardCoins 제외)
  const {
    inputText,
    setInputText,
    currentResponse,
    showResponse,
    isKeyboardVisible,
    keyboardHeight,
    currentGifIndex,
    setCurrentGifIndex, // GIF 변경을 위한 setter 추가
    isLoading,
    apiError,
    handleSendMessage,
    handleBackToMenu,
    handleRetry,
    handleGifChange, // 상점용 GIF 변경 핸들러 (훅에서 가져옴)
    // handleGifClick과 awardCoins는 여기서 덮어쓸 예정이므로 가져오지 않음
  } = useChatLogic(); // 기본 import 사용

  // 화면이 포커스될 때마다 애니메이션 설정 다시 로드
  useFocusEffect(
    useCallback(() => {
      loadAnimationSettings();
      loadSelectedAnimation();
      loadDebugMode();
    }, [])
  );

  // 영양 상태 강제 재검사 함수 (외부에서 호출 가능)
  const recheckNutritionStatus = useCallback(async () => {
    console.log('🔄 영양 상태 강제 재검사 시작...');
    await loadSelectedAnimation();
  }, []);

  // 음식 기록 이벤트 리스너 등록
  useEffect(() => {
    const handleFoodRecorded = () => {
      console.log('🍽️ 음식 기록 이벤트 수신 - 영양 상태 재검사');
      recheckNutritionStatus();
    };

    globalEventEmitter.on(EVENTS.FOOD_RECORDED, handleFoodRecorded);

    return () => {
      globalEventEmitter.off(EVENTS.FOOD_RECORDED, handleFoodRecorded);
    };
  }, [recheckNutritionStatus]);


  const loadAnimationSettings = async () => {
    try {
      const saved = await AsyncStorage.getItem('animationEnabled');
      console.log('🎬 애니메이션 설정 로드:', saved);
      if (saved !== null) {
        const enabled = JSON.parse(saved);
        console.log('🎬 애니메이션 활성화 상태:', enabled);
        setIsAnimationEnabled(enabled);
      }
    } catch (error) {
      console.error('애니메이션 설정 불러오기 실패:', error);
    }
  };
  
  // 선택된 애니메이션 로드 (영양 상태 체크 포함)
  const loadSelectedAnimation = async () => {
    try {
      // 먼저 영양 상태 체크
      const nutritionReport = await generateDailyNutritionReport();
      console.log('🥗 오늘의 영양 상태:', nutritionReport.balance);
      
      // 영양 상태가 좋지 않으면 특별 애니메이션 적용
      if (nutritionReport.balance.level !== 'good') {
        const nutritionAnimation = await getCharacterAnimationByNutrition();
        console.log('⚠️ 영양 불균형 감지! 애니메이션 변경:', nutritionAnimation);
        setCurrentAnimationId(nutritionAnimation);
        setCurrentAnimationSource(getAnimationSource(nutritionAnimation));
        
        // 사용자에게 알림
        if (nutritionReport.balance.level === 'critical') {
          console.log('🚨 심각한 영양 불균형! 균형잡힌 식사가 필요해요.');
        } else if (nutritionReport.balance.level === 'warning') {
          console.log('⚠️ 영양 균형에 주의가 필요해요.');
        }
      } else {
        // 영양 상태가 좋으면 일반 애니메이션 로드
        const animationId = await loadCurrentAnimation();
        console.log('🎬 현재 선택된 애니메이션:', animationId);
        setCurrentAnimationId(animationId);
        setCurrentAnimationSource(getAnimationSource(animationId));
      }
    } catch (error) {
      console.error('선택된 애니메이션 로드 실패:', error);
      // 에러 시 기본 애니메이션 사용
      const animationId = await loadCurrentAnimation();
      setCurrentAnimationId(animationId);
      setCurrentAnimationSource(getAnimationSource(animationId));
    }
  };
  
  // 디버그 모드 로드
  const loadDebugMode = async () => {
    try {
      const debug = await getDebugMode();
      setDebugModeState(debug);
      console.log('🐛 디버그 모드:', debug ? 'ON' : 'OFF');
    } catch (error) {
      console.error('디버그 모드 로드 실패:', error);
    }
  };

  // GIF 클릭 핸들러 - 상점 모달 열기
  const handleGifClick = () => {
    console.log('GIF 클릭됨, 현재 애니메이션:', currentAnimationId);
    setShowShopModal(true);
  };
  
  // 상점에서 애니메이션 변경 시
  const handleAnimationChange = async (animationId: string) => {
    console.log(`[애니메이션 변경] ${currentAnimationId} -> ${animationId}`);
    setCurrentAnimationId(animationId);
    setCurrentAnimationSource(getAnimationSource(animationId));
  };


  // 애니메이션 설정 로드 (컴포넌트 마운트 시)
  useEffect(() => {
    loadAnimationSettings();
  }, []);

  // 화면 포커스 시 애니메이션 설정 다시 로드
  useFocusEffect(
    useCallback(() => {
      console.log('🎬 화면 포커스 - 애니메이션 설정 다시 로드');
      loadAnimationSettings();
    }, [])
  );

  // currentGifIndex 변경 감지 (디버깅용)
  useEffect(() => {
    console.log(`[Chat] currentGifIndex 변경됨: ${currentGifIndex}`);
  }, [currentGifIndex]);

  // 메시지 전송시 밥풀 보상
  const handleSendMessageWithReward = async (message: string) => {
    handleSendMessage(message);
    // 밥풀 10개 지급
    await awardRicePul(10, '음식 추천 요청');
  };

  // 점 애니메이션 생성 함수
  const createBounceAnimation = (animValues: Animated.Value[], shouldLoop = true) => {
    // 애니메이션이 비활성화되면 애니메이션 실행하지 않음
    if (!isAnimationEnabled) {
      return animValues.map(() => ({ start: () => {}, stop: () => {} }));
    }

    const createSingleBounceAnimation = (animValue: Animated.Value, delay: number) => {
      const animation = Animated.sequence([
        Animated.delay(delay),
        Animated.timing(animValue, {
          toValue: -10,
          duration: 400,
          useNativeDriver: true,
        }),
        Animated.timing(animValue, {
          toValue: 0,
          duration: 400,
          useNativeDriver: true,
        }),
      ]);

      return shouldLoop ? Animated.loop(animation) : animation;
    };

    return animValues.map((animValue, index) => 
      createSingleBounceAnimation(animValue, index * 150)
    );
  };

  // 초기 로딩 애니메이션
  useEffect(() => {
    if (showLoading && isAnimationEnabled) {
      const animations = createBounceAnimation(animValues, true);
      animations.forEach(anim => anim.start());

      // 1.5초 후 로딩 숨기고 메시지 표시
      const timer = setTimeout(() => {
        animations.forEach(anim => anim.stop());
        setShowLoading(false);
        setShowMessage(true);
      }, 1500);

      return () => {
        clearTimeout(timer);
        animations.forEach(anim => anim.stop());
      };
    } else if (showLoading && !isAnimationEnabled) {
      // 애니메이션 비활성화 시 즉시 메시지 표시
      const timer = setTimeout(() => {
        setShowLoading(false);
        setShowMessage(true);
      }, 300); // 짧은 딜레이만 적용

      return () => clearTimeout(timer);
    }
  }, [showLoading, animValues, isAnimationEnabled]);

  // API 로딩 애니메이션 - 말풍선이 보이고 로딩중일 때만 실행
  useEffect(() => {
    if (isLoading && showResponse && isAnimationEnabled) {
      const animations = createBounceAnimation(apiLoadingAnimValues, true);
      animations.forEach(anim => anim.start());

      return () => {
        animations.forEach(anim => anim.stop());
      };
    } else {
      // 로딩이 끝나면 애니메이션 정지 및 초기화
      apiLoadingAnimValues.forEach(animValue => {
        animValue.stopAnimation();
        animValue.setValue(0);
      });
    }
  }, [isLoading, showResponse, apiLoadingAnimValues, isAnimationEnabled]);

  // 점 애니메이션 컴포넌트 (초기 로딩용)
  const LoadingDots = ({ animationValues, loadingText }: { 
    animationValues: Animated.Value[], 
    loadingText: string 
  }) => (
    <View style={{ alignItems: 'center' }}>
      {/* 애니메이션이 활성화된 경우에만 점 애니메이션 표시 */}
      {isAnimationEnabled ? (
        <View style={{ 
          flexDirection: 'row', 
          alignItems: 'center',
          marginBottom: 10 
        }}>
          {animationValues.map((animValue, index) => (
            <Animated.View
              key={index}
              style={[
                {
                  width: 12,
                  height: 12,
                  borderRadius: 6,
                  backgroundColor: '#FFBF00',
                  marginHorizontal: 4,
                  transform: [{ translateY: animValue }]
                }
              ]}
            />
          ))}
        </View>
      ) : (
        <View style={{ 
          flexDirection: 'row', 
          alignItems: 'center',
          marginBottom: 10 
        }}>
          {/* 정적인 점들 */}
          {[0, 1, 2].map((index) => (
            <View
              key={index}
              style={{
                width: 12,
                height: 12,
                borderRadius: 6,
                backgroundColor: '#FFBF00',
                marginHorizontal: 4,
              }}
            />
          ))}
        </View>
      )}
      
      <Text style={[
        dynamicStyles.welcomeText,
        { fontSize: 14, color: '#999', textAlign: 'center' }
      ]}>
        {loadingText}
      </Text>
    </View>
  );

  // 반응형 스타일 계산
  const dynamicStyles = {
    welcomeText: {
      ...styles.welcomeText,
      fontSize: isSmallScreen ? 18 : 22,
    },
    characterGif: {
      ...styles.characterGif,
      width: isSmallScreen ? 300 : 350, 
      height: isSmallScreen ? 300 : 350,
    },
  };

  return (
    <View style={styles.container}>
      <StatusBar style="light" />
      
      {/* 헤더 컴포넌트 */}
      <ChatHeader />

      {/* 메인 컨텐츠 */}
      <View style={styles.mainContainer}>
        {/* 말풍선 컴포넌트 - 로딩 애니메이션 props 추가 */}
        <SpeechBubble
          isVisible={showResponse}
          isKeyboardVisible={isKeyboardVisible}
          currentResponse={currentResponse}
          isLoading={isLoading}
          apiError={apiError}
          onClose={handleBackToMenu}
          onRetry={handleRetry}
          // 로딩 애니메이션을 위한 추가 props
          apiLoadingAnimValues={apiLoadingAnimValues}
          isAnimationEnabled={isAnimationEnabled}
        />

        <ScrollView 
          style={styles.scrollContainer}
          contentContainerStyle={[
            styles.scrollContent,
            { 
              paddingBottom: 120, // 입력창 공간 확보
              minHeight: SCREEN_HEIGHT * 0.6,
            }
          ]}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {/* 환영 메시지 */}
          <View style={[
            styles.welcomeContainer, 
            { 
              marginTop: isSmallScreen ? 15 : 30,
              marginBottom: isSmallScreen ? 15 : 30,
              minHeight: isSmallScreen ? 80 : 100,
            }
          ]}>
            {!showResponse && (
              <>
                <Text style={dynamicStyles.welcomeText}>안녕하세요!!</Text>
                
                {/* 초기 로딩만 여기서 표시, API 로딩은 말풍선으로 이동 */}
                <View style={{ 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  minHeight: 60 
                }}>
                  {showLoading ? (
                    <LoadingDots 
                      animationValues={animValues} 
                      loadingText="추천을 준비중..."
                    />
                  ) : (
                    <Text style={[
                      dynamicStyles.welcomeText,
                      { 
                        opacity: showMessage ? 1 : 0,
                        color: showMessage ? '#333' : '#999',
                        textAlign: 'center'
                      }
                    ]}>
                      오늘은 "치킨" 어때요? 
                    </Text>
                  )}
                </View>
              </>
            )}
          </View>

          {/* 캐릭터 애니메이션 */}
          <View style={[
            styles.characterContainer,
            { 
              minHeight: isSmallScreen ? 150 : 200,
              marginTop: 30,
            }
          ]}>
            {/* 캐릭터 클릭 안내 텍스트 - GIF 바로 위 */}
            <View style={styles.characterGuideContainer}>
              <Text style={styles.characterGuideText}>
               캐릭터를 클릭해서 꾸며보세요!
              </Text>
            </View>

            <TouchableOpacity 
              onPress={handleGifClick} 
              activeOpacity={0.8}
              style={{ cursor: 'pointer' }} // 웹에서 클릭 가능하도록 커서 추가
            >
              {isAnimationEnabled ? (
                <Image
                  source={currentAnimationSource}
                  style={dynamicStyles.characterGif}
                  contentFit="contain"
                  transition={1000}
                />
              ) : null}
            </TouchableOpacity>
            
            {/* 디버그 버튼 (웹에서만) */}
            {debugMode && (
              <View style={{ marginTop: 20, alignItems: 'center' }}>
                <TouchableOpacity
                  style={{
                    backgroundColor: '#FF69B4',
                    padding: 10,
                    borderRadius: 20,
                  }}
                  onPress={async () => {
                    await unlockAllAnimationsForTesting();
                    alert('🔓 모든 애니메이션 잠금 해제!');
                  }}
                >
                  <Text style={{ color: 'white', fontWeight: 'bold' }}>
                    🐛 모두 잠금해제 (디버그)
                  </Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        </ScrollView>
      </View>

      {/* 하단 입력창 - 고정 위치 */}
      <ChatInput
        inputText={inputText}
        setInputText={setInputText}
        isLoading={isLoading}
        isKeyboardVisible={isKeyboardVisible}
        keyboardHeight={keyboardHeight}
        onSendMessage={handleSendMessageWithReward} // 밥풀 보상이 포함된 핸들러 사용
      />

      {/* 캐릭터 상점 모달 */}
      <CharacterShopModal
        visible={showShopModal}
        onClose={() => {
          setShowShopModal(false);
          loadSelectedAnimation(); // 닫을 때 선택된 애니메이션 다시 로드
        }}
        currentGifIndex={currentGifIndex}
        onGifChange={handleAnimationChange} // 새로운 핸들러 사용
        isAnimationEnabled={isAnimationEnabled}
      />
    </View>
  );
}