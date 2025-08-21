import { LinearGradient } from 'expo-linear-gradient';
import * as Notifications from 'expo-notifications';
import { useRouter } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import React, { useEffect, useState } from 'react';
import { Alert, Platform, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { API_ENDPOINTS } from '../../config/api.config';
import { getMapUrl } from '../../config/runtime.config';

// Local Notification 설정
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export default function HomeScreen() {
  const router = useRouter();
  const [hasUnreadNotifications, setHasUnreadNotifications] = useState(false);
  const [notificationsEnabled, setNotificationsEnabled] = useState(false);
  const [selectedRankingPeriod, setSelectedRankingPeriod] = useState('weekly'); // 'weekly' or 'monthly'

  // 더미 랭킹 데이터
  const rankingData = {
    weekly: [
      { rank: 1, name: '김밥풀이', meals: 18, badge: '🏆', score: 95 },
      { rank: 2, name: '박든든', meals: 16, badge: '🥈', score: 88 },
      { rank: 3, name: '이맛나', meals: 15, badge: '🥉', score: 85 },
      { rank: 4, name: '정건강', meals: 14, badge: '🌟', score: 82 },
      { rank: 5, name: '최영양', meals: 13, badge: '⭐', score: 79 },
    ],
    monthly: [
      { rank: 1, name: '김밥풀이', meals: 78, badge: '🏆', score: 98 },
      { rank: 2, name: '이맛나', meals: 72, badge: '🥈', score: 91 },
      { rank: 3, name: '박든든', meals: 69, badge: '🥉', score: 89 },
      { rank: 4, name: '정건강', meals: 65, badge: '🌟', score: 86 },
      { rank: 5, name: '최영양', meals: 62, badge: '⭐', score: 83 },
    ]
  };

  useEffect(() => {
    // 웹 환경에서는 3초 후 자동으로 알림 권한 요청 및 테스트 알림
    const webNotificationTimer = setTimeout(async () => {
      if (Platform.OS === 'web' && 'Notification' in window) {
        console.log('🌐 웹 환경 감지 - 알림 권한 확인');
        
        // 알림 권한이 없으면 요청
        if (Notification.permission === 'default') {
          const permission = await Notification.requestPermission();
          if (permission === 'granted') {
            console.log('✅ 알림 권한 승인됨');
            // 권한 승인 후 환영 알림 표시
            setTimeout(async () => {
              try {
                if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
                  const registration = await navigator.serviceWorker.ready;
                  await registration.showNotification('🍚 밥풀레이스에 오신 것을 환영합니다!', {
                    body: '오늘도 맛있는 하루 되세요! 알림 아이콘을 클릭해서 설정을 변경할 수 있습니다.',
                    icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="75" font-size="75">🍚</text></svg>',
                    tag: 'welcome-notification'
                  });
                } else if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
                  // Fallback for development environment
                  try {
                    new Notification('🍚 밥풀레이스에 오신 것을 환영합니다!', {
                      body: '오늘도 맛있는 하루 되세요! 알림 아이콘을 클릭해서 설정을 변경할 수 있습니다.',
                      icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="75" font-size="75">🍚</text></svg>',
                      tag: 'welcome-notification'
                    });
                  } catch (e) {
                    console.log('알림 표시 실패 - Service Worker 없음');
                  }
                }
              } catch (error) {
                console.log('알림 표시 중 오류:', error);
              }
            }, 1000);
            setNotificationsEnabled(true);
          }
        } else if (Notification.permission === 'granted') {
          // 이미 권한이 있으면 환영 알림만 표시
          try {
            if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
              navigator.serviceWorker.ready.then((registration) => {
                registration.showNotification('🍚 밥풀레이스', {
                  body: '환영합니다! 오늘의 추천 메뉴를 확인해보세요.',
                  icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="75" font-size="75">🍚</text></svg>',
                  tag: 'welcome-notification'
                });
              });
            } else {
              // Fallback for development
              try {
                new Notification('🍚 밥풀레이스', {
                  body: '환영합니다! 오늘의 추천 메뉴를 확인해보세요.',
                  icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="75" font-size="75">🍚</text></svg>',
                  tag: 'welcome-notification'
                });
              } catch (e) {
                console.log('알림 표시 실패');
              }
            }
          } catch (error) {
            console.log('알림 오류:', error);
          }
          setNotificationsEnabled(true);
        }
      }
    }, 3000);
    
    initializeLocalNotifications();
    
    // 알림 리스너 설정
    const notificationListener = Notifications.addNotificationReceivedListener(notification => {
      console.log('📱 로컬 알림 수신:', notification);
      setHasUnreadNotifications(true);
    });

    const responseListener = Notifications.addNotificationResponseReceivedListener(response => {
      console.log('👆 알림 탭됨:', response);
      handleNotificationResponse(response);
    });

    return () => {
      clearTimeout(webNotificationTimer);
      if (notificationListener) {
        Notifications.removeNotificationSubscription(notificationListener);
      }
      if (responseListener) {
        Notifications.removeNotificationSubscription(responseListener);
      }
    };
  }, []);

  const initializeLocalNotifications = async () => {
    try {
      console.log('🔔 로컬 알림 초기화 시작...');
      
      // 알림 권한 요청
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;
      
      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }
      
      if (finalStatus !== 'granted') {
        console.log('❌ 알림 권한이 거부되었습니다.');
        Alert.alert(
          '알림 권한', 
          '식사 리마인더를 받으려면 설정에서 알림 권한을 허용해주세요.',
          [
            { text: '나중에', style: 'cancel' },
            { text: '확인', style: 'default' }
          ]
        );
        return;
      }

      console.log('✅ 알림 권한 승인됨');
      await setupMealReminders();
      setNotificationsEnabled(true);
      
    } catch (error) {
      console.error('❌ 로컬 알림 초기화 실패:', error);
      setNotificationsEnabled(false);
    }
  };

  const setupMealReminders = async () => {
    try {
      // 기존 스케줄된 알림 취소
      await Notifications.cancelAllScheduledNotificationsAsync();
      console.log('🗑️ 기존 알림 취소됨');

      // 저녁 알림 (20시) - 원래 코드와 동일하게
      await Notifications.scheduleNotificationAsync({
        content: {
          title: '🍽️ 밥풀레이스',
          body: '오늘 잘 드셨나요? 식사 기록을 남겨보세요!',
          data: { type: 'daily_check' },
          sound: true,
        },
        trigger: {
          hour: 20,
          minute: 0,
          repeats: true,
        },
      });

      console.log('📅 저녁 알림이 설정되었습니다!');
      
    } catch (error) {
      console.error('❌ 알림 설정 오류:', error);
    }
  };

  const handleNotificationResponse = (response: any) => {
    try {
      const notificationType = response.notification.request.content.data?.type;
      console.log('🎯 알림 응답 처리:', notificationType);
      
      if (notificationType === 'daily_check') {
        console.log('🍽️ 저녁 알림 탭 - 영양소 리포트로 이동');
        // router.push('/nutrition'); // 필요시 활성화
      }
      
      setHasUnreadNotifications(false);
    } catch (error) {
      console.error('알림 응답 처리 오류:', error);
    }
  };

  const handleNotificationIconPress = () => {
    console.log('🔔 알림 아이콘 클릭됨!');
    setHasUnreadNotifications(false);
    
    // 웹 환경에서는 window.confirm 사용
    if (Platform.OS === 'web') {
      if (!notificationsEnabled) {
        const result = window.confirm('저녁 식사 리마인더 알림이 비활성화되어 있습니다. 설정하시겠어요?');
        if (result) {
          initializeLocalNotifications();
        }
      } else {
        const options = [
          '1. 테스트 알림 보내기',
          '2. 알림 끄기',
          '3. 취소'
        ].join('\n');
        
        const choice = window.prompt(`밥풀레이스 알림 설정\n\n${options}\n\n번호를 입력하세요:`);
        
        if (choice === '1') {
          sendTestNotification();
        } else if (choice === '2') {
          turnOffNotifications();
        }
      }
    } else {
      // 네이티브 환경에서는 Alert.alert 사용
      if (!notificationsEnabled) {
        Alert.alert(
          '🔔 알림 설정',
          '저녁 식사 리마인더 알림이 비활성화되어 있습니다. 설정하시겠어요?',
          [
            { text: '취소', style: 'cancel' },
            { text: '설정하기', onPress: () => initializeLocalNotifications() }
          ]
        );
      } else {
        Alert.alert(
          '🔔 저녁 알림 설정',
          '밥풀레이스에서 식사 기록 알림을 보내드려요!',
          [
            { text: '알림 끄기', onPress: () => turnOffNotifications(), style: 'destructive' },
            { text: '테스트 알림', onPress: () => sendTestNotification() },
            { text: '확인', style: 'default' }
          ]
        );
      }
    }
  };

  const turnOffNotifications = async () => {
    try {
      await Notifications.cancelAllScheduledNotificationsAsync();
      console.log('🔕 모든 알림이 취소됨');
      setNotificationsEnabled(false);
      
      if (Platform.OS === 'web') {
        window.alert('저녁 알림이 해제되었습니다.');
      } else {
        Alert.alert('알림 해제', '저녁 알림이 해제되었습니다.');
      }
    } catch (error) {
      console.error('알림 해제 오류:', error);
      if (Platform.OS === 'web') {
        window.alert('알림 해제 중 문제가 발생했습니다.');
      } else {
        Alert.alert('오류', '알림 해제 중 문제가 발생했습니다.');
      }
    }
  };

  const sendTestNotification = async () => {
    try {
      console.log('🧪 테스트 알림 전송 시작...');
      
      if (Platform.OS === 'web') {
        // 웹에서는 브라우저 Notification API 사용
        if ('Notification' in window) {
          // 권한 확인
          if (Notification.permission === 'default') {
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') {
              window.alert('알림 권한이 거부되었습니다. 브라우저 설정에서 알림을 허용해주세요.');
              return;
            }
          } else if (Notification.permission === 'denied') {
            window.alert('알림 권한이 거부되었습니다. 브라우저 설정에서 알림을 허용해주세요.');
            return;
          }
          
          // 알림 생성
          setTimeout(() => {
            const notification = new Notification('🧪 밥풀레이스 테스트 알림', {
              body: '알림이 정상적으로 작동합니다! 오늘도 맛있는 하루 되세요 🍽️',
              icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="75" font-size="75">🍚</text></svg>',
              badge: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="75" font-size="75">🍚</text></svg>',
              tag: 'test-notification',
              requireInteraction: false
            });
            
            notification.onclick = () => {
              window.focus();
              notification.close();
              console.log('알림 클릭됨');
            };
          }, 2000);
          
          window.alert('테스트 알림이 2초 후 표시됩니다!');
        } else {
          window.alert('이 브라우저는 알림을 지원하지 않습니다.');
        }
      } else {
        // 네이티브 환경에서는 expo-notifications 사용
        await Notifications.scheduleNotificationAsync({
          content: {
            title: '🧪 테스트 알림',
            body: '로컬 알림이 정상적으로 작동합니다!',
            data: { type: 'test' },
          },
          trigger: { seconds: 2 },
        });
        Alert.alert('테스트 알림', '2초 후 테스트 알림이 도착합니다!');
      }
      
      console.log('🧪 테스트 알림 전송 완료');
    } catch (error) {
      console.error('테스트 알림 오류:', error);
      if (Platform.OS === 'web') {
        window.alert('테스트 알림 설정 중 오류가 발생했습니다.');
      } else {
        Alert.alert('오류', '테스트 알림 전송에 실패했습니다.');
      }
    }
  };

  // 가맹점 지도 열기 함수
  const openStoreMap = async () => {
    try {
      // 지도 HTML 파일을 직접 열기
      const mapUrl = '/maps/tmap_folium_map.html';
      
      if (Platform.OS === 'web') {
        // 웹에서는 새 창으로 열기
        window.open(mapUrl, '_blank', 'width=1200,height=800');
        console.log('🗺️ 가맹점 지도 열기 (웹) - 파일 직접:', mapUrl);
      } else {
        // 모바일에서는 WebBrowser 사용
        console.log('🗺️ 가맹점 지도 열기 (모바일):', mapUrl);
        await WebBrowser.openBrowserAsync(mapUrl);
      }
    } catch (error) {
      console.error('❌ 지도 열기 실패:', error);
      Alert.alert('오류', '지도를 열 수 없습니다. 잠시 후 다시 시도해주세요.');
    }
  };

  const getRankBadgeColor = (rank: number) => {
    switch (rank) {
      case 1: return '#FFD700'; // 금색
      case 2: return '#C0C0C0'; // 은색
      case 3: return '#CD7F32'; // 동색
      default: return '#f8f9fa'; // 기본색
    }
  };

  const currentRankingData = rankingData[selectedRankingPeriod];

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* 깔끔한 헤더 */}
        <View style={styles.appHeader}>
          <View>
            <Text style={styles.appTitle}>밥풀레이스</Text>
            <Text style={styles.appSubtitle}>오늘도 맛있는 하루 되세요!</Text>
          </View>
          
          {/* 알림 아이콘 */}
          <TouchableOpacity 
            style={styles.notificationContainer}
            onPress={() => {
              console.log('🔔 알림 버튼 클릭됨!');
              handleNotificationIconPress();
            }}
            activeOpacity={0.7}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          >
            <View style={[
              styles.notificationIcon,
              !notificationsEnabled && styles.notificationIconDisabled
            ]}>
              <Text style={styles.notificationEmoji}>
                {notificationsEnabled ? '🔔' : '🔕'}
              </Text>
              {hasUnreadNotifications && notificationsEnabled && (
                <View style={styles.notificationBadge}>
                  <View style={styles.notificationDot} />
                </View>
              )}
            </View>
          </TouchableOpacity>
        </View>

        {/* 메인 배너 */}
        <LinearGradient 
          colors={['#FFBF00', '#FDD046']} 
          style={styles.bannerSection}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
        >
          <View style={styles.bannerContent}>
            <View style={styles.bannerTextContainer}>
              <Text style={styles.bannerSubtext}>🍽️ 맛있는 식사의 시작</Text>
              <Text style={styles.bannerTitle}>서울시 강남구{'\n'}급식카드 결제 서비스 OPEN</Text>
              <TouchableOpacity 
                style={styles.bannerButton}
                onPress={openStoreMap}
                activeOpacity={0.7}
              >
                <Text style={styles.bannerButtonText}>가맹점 찾아보기</Text>
              </TouchableOpacity>
            </View>
            <View style={styles.bannerImageContainer}>
            </View>
          </View>
        </LinearGradient>

        {/* 밥풀 순위 섹션 */}
        <View style={styles.contentSection}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>🏆 밥풀 순위</Text>
          </View>
          <Text style={styles.sectionSubtitle}>꾸준한 식사 기록으로 건강한 습관을 만들어보세요</Text>
          
          {/* 기간 선택 탭 */}
          <View style={styles.periodTabContainer}>
            <TouchableOpacity 
              style={[
                styles.periodTab,
                selectedRankingPeriod === 'weekly' && styles.periodTabActive
              ]}
              onPress={() => setSelectedRankingPeriod('weekly')}
              activeOpacity={0.7}
            >
              <Text style={[
                styles.periodTabText,
                selectedRankingPeriod === 'weekly' && styles.periodTabTextActive
              ]}>주간</Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={[
                styles.periodTab,
                selectedRankingPeriod === 'monthly' && styles.periodTabActive
              ]}
              onPress={() => setSelectedRankingPeriod('monthly')}
              activeOpacity={0.7}
            >
              <Text style={[
                styles.periodTabText,
                selectedRankingPeriod === 'monthly' && styles.periodTabTextActive
              ]}>월간</Text>
            </TouchableOpacity>
          </View>

          {/* 순위 리스트 */}
          <View style={styles.rankingContainer}>
            {currentRankingData.map((user, index) => (
              <View key={index} style={[
                styles.rankingItem,
                index === currentRankingData.length - 1 && { borderBottomWidth: 0 }
              ]}>
                <View style={styles.rankingLeft}>
                  <View style={[
                    styles.rankBadge,
                    { backgroundColor: getRankBadgeColor(user.rank) }
                  ]}>
                    <Text style={styles.rankBadgeText}>{user.badge}</Text>
                  </View>
                  <View style={styles.userInfo}>
                    <Text style={styles.userName}>{user.name}</Text>
                    <Text style={styles.userMeals}>
                      {selectedRankingPeriod === 'weekly' ? '이번 주' : '이번 달'} {user.meals}끼
                    </Text>
                  </View>
                </View>
                <View style={styles.rankingRight}>
                  <View style={styles.scoreContainer}>
                    <Text style={styles.scoreText}>{user.score}점</Text>
                  </View>
                  <Text style={styles.rankText}>#{user.rank}</Text>
                </View>
              </View>
            ))}
          </View>

          {/* 내 순위 카드 */}
          <View style={styles.myRankCard}>
            <View style={styles.myRankHeader}>
              <Text style={styles.myRankTitle}>내 순위</Text>
              <Text style={styles.myRankBadge}>🔥</Text>
            </View>
            <View style={styles.myRankContent}>
              <View style={styles.myRankInfo}>
                <Text style={styles.myRankPosition}>#12</Text>
                <Text style={styles.myRankMeals}>
                  {selectedRankingPeriod === 'weekly' ? '이번 주' : '이번 달'} 9끼
                </Text>
              </View>
              <View style={styles.myRankScore}>
                <Text style={styles.myScoreText}>64점</Text>
                <Text style={styles.myRankMessage}>조금만 더 화이팅! 💪</Text>
              </View>
            </View>
          </View>
        </View>

        {/* 인기 식당 섹션 */}
        <View style={[styles.contentSection, { paddingBottom: 40 }]}>
          <Text style={styles.sectionTitle}>오늘의 인기 식당</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.popularRestaurants}>
            {[
              { name: '맘스터치', rating: '4.8', image: '🍔' },
              { name: '본죽&비빔밥', rating: '4.7', image: '🍲' },
              { name: '파스타팩토리', rating: '4.6', image: '🍝' },
              { name: '피자헛', rating: '4.9', image: '🍕' },
            ].map((restaurant, index) => (
              <TouchableOpacity key={index} style={styles.popularRestaurantItem}>
                <View style={styles.popularRestaurantImage}>
                  <Text style={styles.popularRestaurantEmoji}>{restaurant.image}</Text>
                </View>
                <Text style={styles.popularRestaurantName}>{restaurant.name}</Text>
                <View style={styles.ratingContainer}>
                  <Text style={styles.ratingText}>⭐ {restaurant.rating}</Text>
                </View>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { 
    flex: 1, 
    backgroundColor: '#fafafa' 
  },
  
  // 헤더 스타일
  appHeader: { 
    flexDirection: 'row', 
    justifyContent: 'space-between', 
    alignItems: 'center', 
    padding: 20,
    paddingBottom: 15,
    backgroundColor: 'white',
  },
  appTitle: { 
    fontSize: 28, 
    fontWeight: '800',
    color: '#FFBF00',
    letterSpacing: 0.5,
  },
  appSubtitle: {
    fontSize: 14,
    color: '#666',
    marginTop: 2,
  },
  
  // 알림 아이콘 스타일
  notificationContainer: {
    position: 'relative',
  },
  notificationIcon: {
    width: 44,
    height: 44,
    borderRadius: 23,
    borderColor: 'white',
    backgroundColor: 'white',
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 3,
  },
  notificationIconDisabled: {
    backgroundColor: '#e9ecef',
    opacity: 0.6,
  },
  notificationEmoji: {
    fontSize: 20,
    color: '#666',
  },
  notificationBadge: {
    position: 'absolute',
    top: 2,
    right: 2,
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#FF6B6B',
    alignItems: 'center',
    justifyContent: 'center',
  },
  notificationDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: 'white',
  },

  // 배너 스타일
  bannerSection: { 
    marginHorizontal: 20,
    marginTop: 10,
    marginBottom: 30,
    borderRadius: 20,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 6,
  },
  bannerContent: {
    flexDirection: 'row',
    padding: 24,
    alignItems: 'center',
  },
  bannerTextContainer: {
    flex: 1,
  },
  bannerSubtext: { 
    fontSize: 14, 
    color: '#333', 
    marginBottom: 8,
    opacity: 0.8,
  },
  bannerTitle: { 
    fontSize: 20, 
    fontWeight: '700', 
    color: '#333',
    lineHeight: 26,
    marginBottom: 16,
  },
  bannerButton: {
    backgroundColor: 'rgba(255, 255, 255, 0.9)',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
    alignSelf: 'flex-start',
  },
  bannerButtonText: {
    color: '#333',
    fontSize: 14,
    fontWeight: '600',
  },
  bannerImageContainer: {
    marginLeft: 16,
  },

  // 섹션 공통 스타일
  contentSection: { 
    padding: 20,
    paddingTop: 10,
    marginBottom: 20,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  sectionTitle: { 
    fontSize: 20, 
    fontWeight: '700', 
    color: '#333',
  },
  sectionSubtitle: { 
    fontSize: 14, 
    color: '#666', 
    marginBottom: 16,
    lineHeight: 20,
  },

  // 밥풀 순위 스타일
  periodTabContainer: {
    flexDirection: 'row',
    backgroundColor: '#f8f9fa',
    borderRadius: 12,
    padding: 4,
    marginBottom: 20,
  },
  periodTab: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  periodTabActive: {
    backgroundColor: 'white',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  periodTabText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#666',
  },
  periodTabTextActive: {
    color: '#FFBF00',
  },
  
  rankingContainer: {
    backgroundColor: 'white',
    borderRadius: 16,
    paddingVertical: 8,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
  },
  rankingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f8f9fa',
  },
  rankingLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  rankBadge: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  rankBadgeText: {
    fontSize: 20,
  },
  userInfo: {
    flex: 1,
  },
  userName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 2,
  },
  userMeals: {
    fontSize: 13,
    color: '#666',
  },
  rankingRight: {
    alignItems: 'flex-end',
  },
  scoreContainer: {
    backgroundColor: '#f8f9fa',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    marginBottom: 4,
  },
  scoreText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFBF00',
  },
  rankText: {
    fontSize: 12,
    color: '#999',
    fontWeight: '500',
  },

  // 내 순위 카드 스타일
  myRankCard: {
    backgroundColor: 'white',
    borderRadius: 16,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
    borderWidth: 2,
    borderColor: '#FFBF00',
  },
  myRankHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  myRankTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#333',
  },
  myRankBadge: {
    fontSize: 20,
  },
  myRankContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  myRankInfo: {
    flex: 1,
  },
  myRankPosition: {
    fontSize: 24,
    fontWeight: '800',
    color: '#FFBF00',
    marginBottom: 4,
  },
  myRankMeals: {
    fontSize: 14,
    color: '#666',
  },
  myRankScore: {
    alignItems: 'flex-end',
  },
  myScoreText: {
    fontSize: 18,
    fontWeight: '700',
    color: '#333',
    marginBottom: 4,
  },
  myRankMessage: {
    fontSize: 12,
    color: '#FFBF00',
    fontWeight: '600',
  },

  // 인기 식당 스타일
  popularRestaurants: {
    marginTop: 12,
  },
  popularRestaurantItem: {
    backgroundColor: 'white',
    borderRadius: 16,
    padding: 16,
    marginRight: 12,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    width: 120,
  },
  popularRestaurantImage: {
    width: 60,
    height: 60,
    backgroundColor: '#f8f9fa',
    borderRadius: 30,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  popularRestaurantEmoji: {
    fontSize: 30,
  },
  popularRestaurantName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
    textAlign: 'center',
  },
  ratingContainer: {
    backgroundColor: '#f8f9fa',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  ratingText: {
    fontSize: 12,
    color: '#666',
    fontWeight: '500',
  },
});