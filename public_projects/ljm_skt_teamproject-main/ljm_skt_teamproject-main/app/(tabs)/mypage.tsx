import AsyncStorage from '@react-native-async-storage/async-storage';
import { LinearGradient } from 'expo-linear-gradient';
import { useFocusEffect, useRouter } from 'expo-router';
import React, { useCallback, useState } from 'react';
import {
  Alert,
  Image,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import tmapService from '../../services/tmapService';
import StorageService from '../../utils/storage';
import {
  deleteMealCard,
  getTransactionHistory,
  getUserProfile,
  registerMealCard,
  type MealCardInfo,
  type RicePulLevel,
  type Transaction
} from '../../utils/ricePulManager';
import { getPersonas, setCurrentPersona, getCurrentPersona, type Persona } from '../../services/apiService';
import { Switch, Platform } from 'react-native';

interface UserProfile {
  name: string;
  email: string;
  phone: string;
  avatar: string;
  membershipLevel: string;
  points: number;
  card: {
    number: string;
    expiryDate: string;
    holderName: string;
    region: string;
  };
}

// 주소 및 날씨 관련 인터페이스
interface AddressInfo {
  address: string;
  latitude?: number;
  longitude?: number;
  detailAddress?: string;
}

interface WeatherInfo {
  temperature: number;
  condition: string;
  description?: string;
}

interface SearchResult {
  id: string;
  name: string;
  address: string;
  fullAddress: string;
  lat: number;
  lng: number;
}

// 추천 카테고리 타입 정의
interface RecommendationCategory {
  id: string;
  name: string;
  emoji: string;
  description: string;
}

// 알러지 항목 타입 정의
interface AllergyItem {
  id: string;
  name: string;
  emoji: string;
  description: string;
}

// 사용 가능한 추천 카테고리들
const AVAILABLE_CATEGORIES: RecommendationCategory[] = [
  { id: 'korean', name: '한식', emoji: '🍚', description: '김치찌개, 비빔밥, 불고기 등' },
  { id: 'chinese', name: '중식', emoji: '🥢', description: '짜장면, 탕수육, 마라탕 등' },
  { id: 'japanese', name: '일식', emoji: '🍣', description: '초밥, 라멘, 돈가스 등' },
  { id: 'western', name: '양식', emoji: '🍝', description: '파스타, 스테이크, 피자 등' },
  { id: 'fastfood', name: '패스트푸드', emoji: '🍔', description: '햄버거, 치킨, 피자 등' },
  { id: 'cafe', name: '카페/디저트', emoji: '☕', description: '커피, 케이크, 브런치 등' },
  { id: 'healthy', name: '건강식', emoji: '🥗', description: '샐러드, 포케볼, 수프 등' },
  { id: 'spicy', name: '매운음식', emoji: '🌶️', description: '떡볶이, 매운탕, 마라탕 등' },
  { id: 'sweet', name: '단맛', emoji: '🍰', description: '케이크, 아이스크림, 과자 등' },
  { id: 'vegetarian', name: '채식', emoji: '🌱', description: '샐러드, 두부요리, 나물 등' },
];

// 사용 가능한 알러지 항목들
const AVAILABLE_ALLERGIES: AllergyItem[] = [
  { id: 'nuts', name: '견과류', emoji: '🥜', description: '아몬드, 호두, 땅콩, 캐슈넛 등' },
  { id: 'shellfish', name: '갑각류', emoji: '🦐', description: '새우, 게, 바닷가재 등' },
  { id: 'eggs', name: '계란', emoji: '🥚', description: '달걀, 메추리알 등' },
  { id: 'dairy', name: '유제품', emoji: '🥛', description: '우유, 치즈, 버터, 요거트 등' },
  { id: 'soy', name: '대두', emoji: '🌱', description: '콩, 두부, 된장, 간장 등' },
  { id: 'wheat', name: '밀/글루텐', emoji: '🌾', description: '밀가루, 빵, 파스타, 라면 등' },
  { id: 'fish', name: '생선', emoji: '🐟', description: '고등어, 연어, 참치 등' },
  { id: 'mollusks', name: '조개류', emoji: '🐚', description: '조개, 굴, 전복, 오징어 등' },
  { id: 'sesame', name: '참깨', emoji: '🍃', description: '참깨, 들깨, 참기름 등' },
  { id: 'peach', name: '복숭아', emoji: '🍑', description: '복숭아, 자두, 살구 등' },
  { id: 'tomato', name: '토마토', emoji: '🍅', description: '토마토, 토마토 소스 등' },
  { id: 'sulfites', name: '아황산염', emoji: '⚗️', description: '와인, 건포도, 가공식품 등' },
];

export default function MyPageScreen() {
  const router = useRouter();
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [isEditingCard, setIsEditingCard] = useState(false);
  const [currentRicePul, setCurrentRicePul] = useState(0);
  const [currentLevel, setCurrentLevel] = useState<RicePulLevel | null>(null);
  const [mealCardInfo, setMealCardInfo] = useState<MealCardInfo | null>(null);
  const [showRicePulModal, setShowRicePulModal] = useState(false);
  const [transactionHistory, setTransactionHistory] = useState<Transaction[]>([]);

  // 주소 및 날씨 관련 상태
  const [address, setAddress] = useState<string>('');
  const [detailAddress, setDetailAddress] = useState<string>('');
  const [savedAddress, setSavedAddress] = useState<AddressInfo | null>(null);
  const [isEditingAddress, setIsEditingAddress] = useState<boolean>(false);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [showSearchResults, setShowSearchResults] = useState<boolean>(false);
  const [weather, setWeather] = useState<WeatherInfo | null>(null);
  const [showAddressModal, setShowAddressModal] = useState<boolean>(false);
  
  // 추천 카테고리 관련 상태
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [showCategoryModal, setShowCategoryModal] = useState<boolean>(false);

  // 알러지 관련 상태
  const [selectedAllergies, setSelectedAllergies] = useState<string[]>([]);
  const [showAllergyModal, setShowAllergyModal] = useState<boolean>(false);

  // 앱 설정 관련 상태
  const [isAnimationEnabled, setIsAnimationEnabled] = useState<boolean>(true);
  
  // 페르소나 관련 상태
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selectedPersona, setSelectedPersona] = useState<string>('');
  const [showPersonaModal, setShowPersonaModal] = useState<boolean>(false);

  const [profile, setProfile] = useState<UserProfile>({
    name: '',
    email: 'user@example.com',
    phone: '010-1234-5678',
    avatar: 'https://via.placeholder.com/120x120/FFBF00/FFFFFF?text=U',
    membershipLevel: 'GOLD',
    points: currentRicePul,
    card: {
      number: '',
      expiryDate: '',
      holderName: '',
      region: '',
    },
  });

  const [tempProfile, setTempProfile] = useState<UserProfile>(profile);
  const [tempCard, setTempCard] = useState(profile.card);

  // 지역 목록
  const regions = [
    '서울특별시', '부산광역시', '대구광역시', '인천광역시',
    '광주광역시', '대전광역시', '울산광역시', '세종특별자치시',
    '경기도', '강원도', '충청북도', '충청남도',
    '전라북도', '전라남도', '경상북도', '경상남도', '제주특별자치도',
  ];

  // 화면이 포커스될 때마다 통합 데이터 로드
  useFocusEffect(
    useCallback(() => {
      loadIntegratedData();
      loadSavedAddress();
      loadWeatherInfo();
      loadSelectedCategories();
      loadSelectedAllergies();
      loadAnimationSettings();
      loadPersonas();
    }, [])
  );

  // 저장된 주소 불러오기
  const loadSavedAddress = async () => {
    try {
      const saved = await AsyncStorage.getItem('userAddress');
      if (saved) {
        const addressInfo: AddressInfo = JSON.parse(saved);
        setSavedAddress(addressInfo);
        setAddress(addressInfo.address);
        setDetailAddress(addressInfo.detailAddress || '');
      }
    } catch (error) {
      console.error('주소 불러오기 실패:', error);
    }
  };

  // 날씨 정보 불러오기
  const loadWeatherInfo = async (customLat?: number, customLon?: number) => {
    try {
      const API_KEY = '72cade2afd8d0b233391812e15fda078';
      let lat = customLat || 37.5665;
      let lon = customLon || 126.9780;
      
      if (!customLat || !customLon) {
        const savedLocation = await AsyncStorage.getItem('userLocation');
        if (savedLocation) {
          const location = JSON.parse(savedLocation);
          lat = location.latitude;
          lon = location.longitude;
        }
      }
      
      const url = `https://api.openweathermap.org/data/2.5/weather?lat=${lat}&lon=${lon}&appid=${API_KEY}&units=metric&lang=kr`;
      const response = await fetch(url);
      
      if (response.ok) {
        const data = await response.json();
        const main = data.weather[0].main.toLowerCase();
        let condition = '맑음';
        
        if (main.includes('rain')) condition = '비';
        else if (main.includes('snow')) condition = '눈';
        else if (main.includes('cloud')) condition = '흐림';
        else if (main.includes('clear')) condition = '맑음';
        
        setWeather({
          temperature: Math.round(data.main.temp),
          condition: condition,
          description: data.weather[0].description
        });
      }
    } catch (error) {
      console.error('날씨 정보 로드 실패:', error);
    }
  };

  // 주소 검색
  const searchAddress = async () => {
    if (!address.trim()) {
      Alert.alert('알림', '검색할 주소를 입력해주세요.');
      return;
    }

    setIsSearching(true);
    try {
      const result: any = await tmapService.searchAddress(address);
      if (result.success && result.results && result.results.length > 0) {
        setSearchResults(result.results);
        setShowSearchResults(true);
      } else {
        Alert.alert('검색 결과 없음', '입력한 주소를 찾을 수 없습니다.');
      }
    } catch (error) {
      console.error('주소 검색 실패:', error);
      Alert.alert('오류', '주소 검색에 실패했습니다.');
    } finally {
      setIsSearching(false);
    }
  };

  // 검색 결과 선택
  const selectSearchResult = async (result: SearchResult) => {
    let displayAddress = result.name || '';
    if (result.address) {
      const addressParts = result.address.trim().split(' ');
      const importantParts = addressParts.filter(part => 
        !part.includes('대한민국') && !part.includes('KR') && part.trim() !== ''
      );
      displayAddress = importantParts.join(' ');
    }
    
    const addressInfo: AddressInfo = {
      address: displayAddress || result.fullAddress,
      latitude: result.lat,
      longitude: result.lng,
      detailAddress: detailAddress.trim(),
    };

    await AsyncStorage.setItem('userAddress', JSON.stringify(addressInfo));
    await AsyncStorage.setItem('userLocation', JSON.stringify({ 
      latitude: result.lat, 
      longitude: result.lng 
    }));
    
    setSavedAddress(addressInfo);
    setAddress(displayAddress || result.fullAddress);
    setShowSearchResults(false);
    setSearchResults([]);
    setIsEditingAddress(false);
    
    loadWeatherInfo(result.lat, result.lng);
    Alert.alert('성공', '주소가 설정되었습니다. 날씨 정보가 업데이트되었습니다.');
  };

  const getCurrentLocation = async () => {
    try {
      if (typeof navigator !== 'undefined' && navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          async (position) => {
            const { latitude, longitude } = position.coords;
            
            try {
              const result: any = await tmapService.reverseGeocode(latitude, longitude);
              if (result.success) {
                const addressInfo: AddressInfo = {
                  address: result.fullAddress || `위도: ${latitude}, 경도: ${longitude}`,
                  latitude,
                  longitude,
                  detailAddress: '',
                };
                
                setAddress(addressInfo.address);
                setSavedAddress(addressInfo);
                await AsyncStorage.setItem('userAddress', JSON.stringify(addressInfo));
                await AsyncStorage.setItem('userLocation', JSON.stringify({ latitude, longitude }));
                
                loadWeatherInfo(latitude, longitude);
                Alert.alert('성공', '현재 위치가 설정되었습니다.');
                setIsEditingAddress(false);
              }
            } catch (error) {
              const addressInfo: AddressInfo = {
                address: `서울특별시 (위도: ${latitude.toFixed(4)}, 경도: ${longitude.toFixed(4)})`,
                latitude,
                longitude,
                detailAddress: '',
              };
              
              setAddress(addressInfo.address);
              setSavedAddress(addressInfo);
              await AsyncStorage.setItem('userAddress', JSON.stringify(addressInfo));
              await AsyncStorage.setItem('userLocation', JSON.stringify({ latitude, longitude }));
              
              loadWeatherInfo(latitude, longitude);
              Alert.alert('성공', '현재 위치가 설정되었습니다.');
              setIsEditingAddress(false);
            }
          },
          (error) => {
            if (error.code === 1) {
              Alert.alert('위치 권한', '위치 접근 권한이 필요합니다.');
            } else {
              Alert.alert('오류', '현재 위치를 가져올 수 없습니다.');
            }
          }
        );
      }
    } catch (error) {
      Alert.alert('오류', '위치를 가져오는 중 오류가 발생했습니다.');
    }
  };

  const clearAddress = () => {
    Alert.alert(
      '주소 삭제',
      '저장된 주소를 삭제하시겠습니까?',
      [
        { text: '취소', style: 'cancel' },
        {
          text: '삭제',
          style: 'destructive',
          onPress: async () => {
            try {
              await AsyncStorage.removeItem('userAddress');
              setSavedAddress(null);
              setAddress('');
              setDetailAddress('');
              setIsEditingAddress(false);
            } catch (error) {
              console.error('주소 삭제 실패:', error);
            }
          },
        },
      ]
    );
  };

  // 통합 데이터 로드 함수
  const loadIntegratedData = async () => {
    try {
      const userProfile = await getUserProfile();
      const transactions = await getTransactionHistory(20);
      
      // 페르소나 데이터 가져오기
      const personaData = await StorageService.getPersona();
      let mealCardBalance = userProfile.mealCard?.balance || 0;
      
      // 페르소나에 따른 급식카드 잔액 설정
      if (personaData?.name) {
        switch(personaData.name) {
          case '민호':
            mealCardBalance = 25000;
            break;
          case '명빈':
            mealCardBalance = 50000;
            break;
          case '태훈':
            mealCardBalance = 15000;
            break;
          default:
            mealCardBalance = 10000;
        }
      }
      
      setCurrentRicePul(userProfile.ricePul);
      setCurrentLevel(userProfile.level);
      setMealCardInfo(userProfile.mealCard ? {
        ...userProfile.mealCard,
        balance: mealCardBalance
      } : null);
      setTransactionHistory(transactions);
      
      setProfile(prev => ({
        ...prev,
        name: personaData?.name || userProfile.name,
        points: userProfile.ricePul
      }));
    } catch (error) {
      console.error('❌ 통합 데이터 로드 실패:', error);
    }
  };

  // 프로필 관련 함수들
  const handleProfileEdit = () => {
    setTempProfile(profile);
    setIsEditingProfile(true);
  };

  const handleProfileSave = () => {
    setProfile(tempProfile);
    setIsEditingProfile(false);
  };

  const handleProfileCancel = () => {
    setTempProfile(profile);
    setIsEditingProfile(false);
  };

  // 급식카드 관련 함수들
  const handleCardEdit = () => {
    setTempCard(profile.card);
    setIsEditingCard(true);
  };

  const handleCardSave = async () => {
    try {
      const newMealCardInfo = await registerMealCard(tempCard.number, 50000);
      setProfile({ ...profile, card: tempCard });
      setMealCardInfo(newMealCardInfo);
      setIsEditingCard(false);
      Alert.alert('등록 완료', '급식카드가 성공적으로 등록되었습니다!');
      await loadIntegratedData();
    } catch (error) {
      Alert.alert('등록 실패', '급식카드 등록 중 오류가 발생했습니다.');
    }
  };

  const handleCardCancel = () => {
    setTempCard(profile.card);
    setIsEditingCard(false);
  };

  const handleCardDelete = () => {
    Alert.alert(
      '급식카드 삭제',
      '등록된 급식카드를 삭제하시겠습니까?',
      [
        { text: '취소', style: 'cancel' },
        {
          text: '삭제',
          style: 'destructive',
          onPress: async () => {
            try {
              await deleteMealCard();
              setMealCardInfo(null);
              setProfile(prev => ({
                ...prev,
                card: { number: '', expiryDate: '', holderName: '', region: '' }
              }));
              Alert.alert('삭제 완료', '급식카드가 삭제되었습니다.');
              await loadIntegratedData();
            } catch (error) {
              Alert.alert('삭제 실패', '급식카드 삭제 중 오류가 발생했습니다.');
            }
          }
        }
      ]
    );
  };

  // 카드 입력 포맷팅 함수들
  const formatCardNumberInput = (value: string) => {
    const numbers = value.replace(/\D/g, '');
    return numbers.replace(/(\d{4})(?=\d)/g, '$1-');
  };

  const formatExpiryDateInput = (value: string) => {
    const numbers = value.replace(/\D/g, '');
    if (numbers.length >= 2) {
      return numbers.slice(0, 2) + '/' + numbers.slice(2, 4);
    }
    return numbers;
  };

  // 레벨 진행률 계산
  const getLevelProgress = () => {
    if (!currentLevel) return 0;
    const total = currentLevel.currentExp + currentLevel.expToNext;
    return total > 0 ? (currentLevel.currentExp / total) * 100 : 0;
  };

  // 저장된 추천 카테고리 불러오기
  const loadSelectedCategories = async () => {
    try {
      const saved = await AsyncStorage.getItem('selectedCategories');
      if (saved) {
        const categories: string[] = JSON.parse(saved);
        setSelectedCategories(categories);
      }
    } catch (error) {
      console.error('추천 카테고리 불러오기 실패:', error);
    }
  };

  // 저장된 알러지 정보 불러오기
  const loadSelectedAllergies = async () => {
    try {
      const saved = await AsyncStorage.getItem('selectedAllergies');
      if (saved) {
        const allergies: string[] = JSON.parse(saved);
        setSelectedAllergies(allergies);
      }
    } catch (error) {
      console.error('알러지 정보 불러오기 실패:', error);
    }
  };

  // 저장된 애니메이션 설정 불러오기
  const loadAnimationSettings = async () => {
    try {
      const saved = await AsyncStorage.getItem('animationEnabled');
      if (saved !== null) {
        const enabled: boolean = JSON.parse(saved);
        setIsAnimationEnabled(enabled);
      }
    } catch (error) {
      console.error('애니메이션 설정 불러오기 실패:', error);
    }
  };

  // 페르소나 목록 불러오기
  const loadPersonas = async () => {
    try {
      // 항상 기본 페르소나 목록 사용
      const defaultPersonas = [
        { id: 'min_ho', name: '김민호', age: 17, description: '17세 고등학생', balance: 25000 },
        { id: 'myeong_bin', name: '김명빈', age: 14, description: '14세 중학생', balance: 50000 },
        { id: 'tae_hoon', name: '강태훈', age: 12, description: '12세 초등학생', balance: 15000 },
      ];
      setPersonas(defaultPersonas);
      
      // 저장된 페르소나 불러오기
      const savedPersona = await AsyncStorage.getItem('selectedPersona');
      if (savedPersona) {
        setSelectedPersona(savedPersona);
        setCurrentPersona(savedPersona);
        // 페르소나에 따른 기본 설정 적용
        await applyPersonaDefaults(savedPersona);
      } else {
        // 기본값으로 민호 설정
        setSelectedPersona('min_ho');
        setCurrentPersona('min_ho');
        await applyPersonaDefaults('min_ho');
      }
    } catch (error) {
      console.error('페르소나 불러오기 실패:', error);
      // 오류 시에도 기본 페르소나 설정
      const defaultPersonas = [
        { id: 'min_ho', name: '김민호', age: 17, description: '17세 고등학생', balance: 25000 },
        { id: 'myeong_bin', name: '김명빈', age: 14, description: '14세 중학생', balance: 50000 },
        { id: 'tae_hoon', name: '강태훈', age: 12, description: '12세 초등학생', balance: 15000 },
      ];
      setPersonas(defaultPersonas);
      setSelectedPersona('min_ho');
      await applyPersonaDefaults('min_ho');
    }
  };

  // 페르소나별 기본 설정 적용
  const applyPersonaDefaults = async (personaId: string) => {
    let categories: string[] = [];
    let allergies: string[] = [];
    let mealCardBalance = 10000;
    let hasCard = false;
    
    switch(personaId) {
      case 'min_ho':
        // 민호 (17세 고등학생) - 급식카드 잔액 25,000원
        categories = ['korean', 'fastfood', 'spicy'];
        allergies = [];
        mealCardBalance = 25000;
        hasCard = true;
        break;
      case 'myeong_bin':
        // 명빈 (14세 중학생) - 급식카드 잔액 50,000원
        categories = ['western', 'cafe', 'sweet'];
        allergies = ['nuts'];
        mealCardBalance = 50000;
        hasCard = true;
        break;
      case 'tae_hoon':
        // 태훈 (12세 초등학생) - 급식카드 잔액 15,000원
        categories = ['korean', 'chinese', 'sweet'];
        allergies = ['shellfish', 'eggs'];
        mealCardBalance = 15000;
        hasCard = true;
        break;
    }
    
    // 카테고리와 알러지 설정 저장
    setSelectedCategories(categories);
    setSelectedAllergies(allergies);
    await AsyncStorage.setItem('selectedCategories', JSON.stringify(categories));
    await AsyncStorage.setItem('selectedAllergies', JSON.stringify(allergies));
    
    // 급식카드 자동 설정
    if (hasCard) {
      const cardInfo: MealCardInfo = {
        cardNumber: `****-****-****-${Math.floor(Math.random() * 10000).toString().padStart(4, '0')}`,
        balance: mealCardBalance,
        lastUsed: new Date().toISOString(),
      };
      setMealCardInfo(cardInfo);
    } else {
      setMealCardInfo(null);
    }
  };

  // 페르소나 선택 저장
  const saveSelectedPersona = async (personaId: string) => {
    // 이미 선택된 페르소나면 모달만 닫기
    if (selectedPersona === personaId) {
      setShowPersonaModal(false);
      return;
    }
    
    // 웹 환경에서는 confirm 사용
    if (Platform.OS === 'web') {
      const confirmed = window.confirm('페르소나를 변경하면 현재 대화 내용이 모두 초기화됩니다. 계속하시겠습니까?');
      if (confirmed) {
        try {
          // 대화 기록 삭제
          await AsyncStorage.removeItem('chatHistory');
          await AsyncStorage.removeItem('conversationContext');
          
          // 새 페르소나 저장
          await AsyncStorage.setItem('selectedPersona', personaId);
          setSelectedPersona(personaId);
          setCurrentPersona(personaId);
          
          // 페르소나별 기본 설정 적용
          await applyPersonaDefaults(personaId);
          
          // 데이터 다시 로드
          await loadIntegratedData();
          
          setShowPersonaModal(false);
          
          // 웹에서는 간단한 alert 사용
          window.alert('새로운 페르소나로 변경되었습니다. 대화가 초기화되었습니다.');
        } catch (error) {
          console.error('페르소나 저장 실패:', error);
          window.alert('페르소나 저장에 실패했습니다.');
        }
      }
    } else {
      // 네이티브 환경에서는 Alert.alert 사용
      Alert.alert(
        '페르소나 변경',
        '페르소나를 변경하면 현재 대화 내용이 모두 초기화됩니다. 계속하시겠습니까?',
        [
          {
            text: '취소',
            style: 'cancel',
          },
          {
            text: '변경',
            style: 'destructive',
            onPress: async () => {
              try {
                // 대화 기록 삭제
                await AsyncStorage.removeItem('chatHistory');
                await AsyncStorage.removeItem('conversationContext');
                
                // 새 페르소나 저장
                await AsyncStorage.setItem('selectedPersona', personaId);
                setSelectedPersona(personaId);
                setCurrentPersona(personaId);
                
                // 페르소나별 기본 설정 적용
                await applyPersonaDefaults(personaId);
                
                // 데이터 다시 로드
                await loadIntegratedData();
                
                setShowPersonaModal(false);
                
                Alert.alert(
                  '페르소나 변경 완료', 
                  '새로운 페르소나로 변경되었습니다. 대화가 초기화되었습니다.',
                  [{ text: '확인' }]
                );
              } catch (error) {
                console.error('페르소나 저장 실패:', error);
                Alert.alert('오류', '페르소나 저장에 실패했습니다.');
              }
            },
          },
        ],
      );
    }
  };

  // 추천 카테고리 저장
  const saveSelectedCategories = async (categories: string[]) => {
    try {
      await AsyncStorage.setItem('selectedCategories', JSON.stringify(categories));
      setSelectedCategories(categories);
    } catch (error) {
      console.error('추천 카테고리 저장 실패:', error);
      Alert.alert('오류', '추천 카테고리 저장에 실패했습니다.');
    }
  };

  // 알러지 정보 저장
  const saveSelectedAllergies = async (allergies: string[]) => {
    try {
      await AsyncStorage.setItem('selectedAllergies', JSON.stringify(allergies));
      setSelectedAllergies(allergies);
    } catch (error) {
      console.error('알러지 정보 저장 실패:', error);
      Alert.alert('오류', '알러지 정보 저장에 실패했습니다.');
    }
  };

  // 애니메이션 설정 저장
  const saveAnimationSettings = async (enabled: boolean) => {
    try {
      await AsyncStorage.setItem('animationEnabled', JSON.stringify(enabled));
      setIsAnimationEnabled(enabled);
    } catch (error) {
      console.error('애니메이션 설정 저장 실패:', error);
      Alert.alert('오류', '애니메이션 설정 저장에 실패했습니다.');
    }
  };

  // 카테고리 선택/해제 토글
  const toggleCategory = (categoryId: string) => {
    setSelectedCategories(prev => {
      if (prev.includes(categoryId)) {
        return prev.filter(id => id !== categoryId);
      } else {
        return [...prev, categoryId];
      }
    });
  };

  // 알러지 선택/해제 토글
  const toggleAllergy = (allergyId: string) => {
    setSelectedAllergies(prev => {
      if (prev.includes(allergyId)) {
        return prev.filter(id => id !== allergyId);
      } else {
        return [...prev, allergyId];
      }
    });
  };

  // 애니메이션 설정 토글
  const toggleAnimation = (enabled: boolean) => {
    saveAnimationSettings(enabled);
  };

  // 카테고리 모달 닫기 및 저장
  const closeCategoryModal = () => {
    setShowCategoryModal(false);
    saveSelectedCategories(selectedCategories);
  };

  // 알러지 모달 닫기 및 저장
  const closeAllergyModal = () => {
    setShowAllergyModal(false);
    saveSelectedAllergies(selectedAllergies);
  };

  // 선택된 카테고리 이름들 가져오기
  const getSelectedCategoryNames = () => {
    return selectedCategories
      .map(id => AVAILABLE_CATEGORIES.find(cat => cat.id === id)?.name)
      .filter(Boolean)
      .join(', ');
  };

  // 선택된 알러지 이름들 가져오기
  const getSelectedAllergyNames = () => {
    return selectedAllergies
      .map(id => AVAILABLE_ALLERGIES.find(allergy => allergy.id === id)?.name)
      .filter(Boolean)
      .join(', ');
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* 헤더 */}
        <View style={styles.appHeader}>
          <Text style={styles.appTitle}>마이페이지</Text>
        </View>

        {/* 프로필 배너 */}
        <LinearGradient 
          colors={['#FFBF00', '#FDD046']} 
          style={styles.profileBanner}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
        >
          <View style={styles.profileContent}>
            <View style={styles.profileRow}>
              <Image source={{ uri: profile.avatar }} style={styles.profileAvatar} />
              <View style={styles.profileInfo}>
                <Text style={styles.profileName}>{profile.name}</Text>
                <Text style={styles.profilePhone}>{profile.phone}</Text>
                
                {/* 레벨 정보 */}
                {currentLevel && (
                  <View style={styles.levelContainer}>
                    <Text style={styles.levelText}>
                      Lv.{currentLevel.level} {currentLevel.title}
                    </Text>
                    <View style={styles.levelProgress}>
                      <View 
                        style={[styles.levelProgressFill, { width: `${getLevelProgress()}%` }]} 
                      />
                    </View>
                    <Text style={styles.levelExpText}>
                      {currentLevel.expToNext > 0 
                        ? `다음 레벨까지 ${currentLevel.expToNext}밥풀` 
                        : '최고 레벨!'
                      }
                    </Text>
                  </View>
                )}
                
                {/* 밥풀 정보 */}
                <TouchableOpacity 
                  style={styles.pointsContainer}
                  onPress={loadIntegratedData}
                  activeOpacity={0.7}
                >
                  <Image source={require('../../assets/rice.png')} style={styles.riceIcon} />
                  <Text style={styles.pointsText}>
                    {currentRicePul.toLocaleString()}밥풀
                  </Text>
                </TouchableOpacity>
              </View>
              {!isEditingProfile && (
                <TouchableOpacity style={styles.editProfileButton} onPress={handleProfileEdit}>
                  <Text style={styles.editProfileButtonText}>수정</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        </LinearGradient>

        {/* 페르소나 설정 섹션 - 프로필 바로 아래로 이동 */}
        <View style={styles.contentSection}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>👤 사용자 프로필</Text>
          </View>
          <Text style={styles.sectionSubtitle}>
            프로필을 선택하면 급식카드, 추천 카테고리, 알러지 정보가 자동으로 설정됩니다.
          </Text>
          
          <View style={styles.cardInfoCard}>
            <TouchableOpacity 
              style={styles.cardContentItem}
              onPress={() => {
                if (personas.length === 0) {
                  loadPersonas();
                }
                setShowPersonaModal(true);
              }}
              activeOpacity={0.7}
            >
              <View style={styles.cardContentInfo}>
                <Text style={styles.cardContentLabel}>현재 프로필</Text>
                <Text style={styles.cardContentValue}>
                  {personas.find(p => p.id === selectedPersona)?.name || '선택안함'}
                </Text>
                {selectedPersona && personas.find(p => p.id === selectedPersona) && (
                  <Text style={styles.cardContentDescription}>
                    {(() => {
                      const persona = personas.find(p => p.id === selectedPersona);
                      return persona ? `${persona.age}세 • 급식카드 ${persona.balance.toLocaleString()}원` : '';
                    })()}
                  </Text>
                )}
              </View>
              <Text style={styles.cardArrow}>›</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* 프로필 수정 섹션 */}
        {isEditingProfile && (
          <View style={styles.contentSection}>
            <Text style={styles.sectionTitle}>개인정보 수정</Text>
            <View style={styles.editCard}>
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>이름</Text>
                <TextInput
                  style={styles.input}
                  value={tempProfile.name}
                  onChangeText={(text) => setTempProfile({ ...tempProfile, name: text })}
                  placeholder="이름을 입력하세요"
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>전화번호</Text>
                <TextInput
                  style={styles.input}
                  value={tempProfile.phone}
                  onChangeText={(text) => setTempProfile({ ...tempProfile, phone: text })}
                  placeholder="전화번호를 입력하세요"
                  keyboardType="phone-pad"
                />
              </View>

              <View style={styles.buttonRow}>
                <TouchableOpacity style={styles.saveButton} onPress={handleProfileSave}>
                  <Text style={styles.saveButtonText}>저장</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.cancelButton} onPress={handleProfileCancel}>
                  <Text style={styles.cancelButtonText}>취소</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        )}

        {/* 급식카드 등록 섹션 */}
        <View style={styles.contentSection}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>급식카드</Text>
            {!isEditingCard && (
              <TouchableOpacity onPress={handleCardEdit}>
                <Text style={styles.seeAllText}>
                  {mealCardInfo ? '수정' : '등록'}
                </Text>
              </TouchableOpacity>
            )}
          </View>
          <Text style={styles.sectionSubtitle}>급식카드를 등록하여 편리하게 결제하세요</Text>

          <View style={styles.cardInfoCard}>
            {!isEditingCard ? (
              <View>
                {mealCardInfo ? (
                  <View style={styles.mealCardContainer}>
                    <View style={styles.mealCardHeader}>
                      <Text style={styles.mealCardTitle}>💳 급식카드</Text>
                      <View style={styles.registeredBadge}>
                        <Text style={styles.registeredBadgeText}>등록완료</Text>
                      </View>
                    </View>
                    
                    <View style={styles.mealCardBalance}>
                      <Text style={styles.balanceLabel}>현재 잔액</Text>
                      <Text style={styles.balanceAmount}>
                        {mealCardInfo.balance.toLocaleString()}원
                      </Text>
                    </View>
                    
                    <View style={styles.mealCardInfo}>
                      <Text style={styles.cardNumberText}>
                        카드번호: {mealCardInfo.cardNumber}
                      </Text>
                      {mealCardInfo.lastUsed && (
                        <Text style={styles.lastUsedText}>
                          최근 사용: {new Date(mealCardInfo.lastUsed).toLocaleDateString()}
                        </Text>
                      )}
                    </View>
                    
                    {/* 레벨별 할인 혜택 표시 */}
                    {currentLevel && currentLevel.level >= 5 && (
                      <View style={styles.discountBadge}>
                        <Text style={styles.discountText}>
                          🎉 레벨 {currentLevel.level} 혜택: {
                            currentLevel.level >= 7 ? '15%' :
                            currentLevel.level >= 6 ? '10%' : '5%'
                          } 할인!
                        </Text>
                      </View>
                    )}

                    {/* 카드 삭제 버튼 */}
                    <View style={styles.cardActions}>
                      <TouchableOpacity
                        style={styles.deleteCardButton}
                        onPress={handleCardDelete}
                      >
                        <Text style={styles.deleteCardButtonText}>카드 삭제</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ) : (
                  <View style={styles.noCardContainer}>
                    <Text style={styles.noCardText}>급식카드를 등록해주세요</Text>
                  </View>
                )}
              </View>
            ) : (
              <View>
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>카드번호</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="예: 1234-5678-9012-3456"
                    value={formatCardNumberInput(tempCard.number)}
                    onChangeText={(text) => {
                      const numbers = text.replace(/\D/g, '');
                      if (numbers.length <= 16) {
                        setTempCard({ ...tempCard, number: numbers });
                      }
                    }}
                    keyboardType="numeric"
                    maxLength={19}
                  />
                </View>

                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>유효기간</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="MM/YY"
                    value={formatExpiryDateInput(tempCard.expiryDate)}
                    onChangeText={(text) => {
                      const numbers = text.replace(/\D/g, '');
                      if (numbers.length <= 4) {
                        setTempCard({ ...tempCard, expiryDate: numbers });
                      }
                    }}
                    keyboardType="numeric"
                    maxLength={5}
                  />
                </View>

                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>카드 소유자 이름</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="예: 홍길동"
                    value={tempCard.holderName}
                    onChangeText={(text) => setTempCard({ ...tempCard, holderName: text })}
                  />
                </View>

                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>지역 선택</Text>
                  <View style={styles.regionGrid}>
                    {regions.map((region) => (
                      <TouchableOpacity
                        key={region}
                        style={[
                          styles.regionButton,
                          tempCard.region === region && styles.regionButtonSelected
                        ]}
                        onPress={() => setTempCard({ ...tempCard, region })}
                      >
                        <Text style={[
                          styles.regionButtonText,
                          tempCard.region === region && styles.regionButtonTextSelected
                        ]}>
                          {region}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>

                <View style={styles.buttonRow}>
                  <TouchableOpacity style={styles.saveButton} onPress={handleCardSave}>
                    <Text style={styles.saveButtonText}>등록</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.cancelButton} onPress={handleCardCancel}>
                    <Text style={styles.cancelButtonText}>취소</Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}
          </View>
        </View>

        {/* 밥풀 현황 섹션 */}
        <View style={styles.contentSection}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>🌾 밥풀 현황</Text>
          </View>
          <Text style={styles.sectionSubtitle}>밥풀을 모아서 레벨을 올려보세요</Text>
          
          <View style={styles.cardInfoCard}>
            <TouchableOpacity 
              style={styles.cardContentItem}
              onPress={() => setShowRicePulModal(true)}
              activeOpacity={0.7}
            >
              <View style={styles.cardContentInfo}>
                <Text style={styles.ricePulAmount}>{currentRicePul.toLocaleString()}</Text>
                <Text style={styles.cardContentLabel}>보유 밥풀</Text>
                {currentLevel && (
                  <View style={styles.levelInfoContainer}>
                    <Text style={styles.levelInfoText}>
                      Lv.{currentLevel.level} {currentLevel.title}
                    </Text>
                    <View style={styles.levelProgressMini}>
                      <View 
                        style={[styles.levelProgressFillMini, { width: `${getLevelProgress()}%` }]} 
                      />
                    </View>
                  </View>
                )}
              </View>
              <Text style={styles.cardArrow}>→</Text>
            </TouchableOpacity>
          </View>
        </View>


        {/* 추천 카테고리 설정 섹션 */}
        <View style={styles.contentSection}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>🍽️ 추천 카테고리</Text>
          </View>
          <Text style={styles.sectionSubtitle}>
            선호하는 음식 카테고리를 선택하면 더 정확한 추천을 받을 수 있어요
          </Text>
          
          <View style={styles.cardInfoCard}>
            <TouchableOpacity 
              style={styles.cardContentItem}
              onPress={() => setShowCategoryModal(true)}
              activeOpacity={0.7}
            >
              <View style={styles.cardContentInfo}>
                <Text style={styles.cardContentLabel}>선호 카테고리</Text>
                <Text style={styles.cardContentValue}>
                  {selectedCategories.length > 0 ? `${selectedCategories.length}개 선택됨` : '선택 안함'}
                </Text>
                {selectedCategories.length > 0 && (
                  <Text style={styles.cardContentDescription}>
                    {getSelectedCategoryNames()}
                  </Text>
                )}
              </View>
              <Text style={styles.cardArrow}>›</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* 알러지 설정 섹션 */}
        <View style={styles.contentSection}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>⚠️ 알러지 정보</Text>
          </View>
          <Text style={styles.sectionSubtitle}>
            알러지가 있는 식품을 선택하면 해당 식품이 포함된 음식점은 제외하고 추천해드려요
          </Text>
          
          <View style={styles.cardInfoCard}>
            <TouchableOpacity 
              style={styles.cardContentItem}
              onPress={() => setShowAllergyModal(true)}
              activeOpacity={0.7}
            >
              <View style={styles.cardContentInfo}>
                <Text style={styles.cardContentLabel}>알러지 항목</Text>
                <Text style={[styles.cardContentValue, selectedAllergies.length > 0 && styles.allergyWarningText]}>
                  {selectedAllergies.length > 0 ? `${selectedAllergies.length}개 항목 설정됨` : '설정 안함'}
                </Text>
                {selectedAllergies.length > 0 && (
                  <Text style={[styles.cardContentDescription, styles.allergyDescriptionText]}>
                    {getSelectedAllergyNames()}
                  </Text>
                )}
              </View>
              <Text style={styles.cardArrow}>›</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* 앱 설정 섹션 */}
        <View style={styles.contentSection}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>⚙️ 앱 설정</Text>
          </View>
          
          <View style={styles.cardInfoCard}>
            <View style={styles.settingItemWithSwitch}>
              <View style={styles.settingInfo}>
                <Text style={styles.cardContentLabel}>애니메이션 효과</Text>
                <Text style={styles.cardContentDescription}>
                  앱 내 애니메이션 효과를 활성화합니다
                </Text>
              </View>
              <Switch
                value={isAnimationEnabled}
                onValueChange={toggleAnimation}
                trackColor={{ false: '#e0e0e0', true: '#FFD54F' }}
                thumbColor={isAnimationEnabled ? '#FF8F00' : '#9e9e9e'}
                ios_backgroundColor="#e0e0e0"
              />
            </View>
          </View>
        </View>

        {/* 기타 설정 섹션 */}
        <View style={[styles.contentSection, { paddingBottom: 40 }]}>
          <Text style={styles.sectionTitle}>기타</Text>
          <View style={styles.settingsCard}>
            <TouchableOpacity style={styles.settingItem}>
              <Text style={styles.settingText}>🔔 알림 설정</Text>
              <Text style={styles.settingArrow}>→</Text>
            </TouchableOpacity>
            <View style={styles.settingDivider} />
            <TouchableOpacity style={styles.settingItem}>
              <Text style={styles.settingText}>🔒 개인정보 처리방침</Text>
              <Text style={styles.settingArrow}>→</Text>
            </TouchableOpacity>
            <View style={styles.settingDivider} />
            <TouchableOpacity style={styles.settingItem}>
              <Text style={styles.settingText}>📄 이용약관</Text>
              <Text style={styles.settingArrow}>→</Text>
            </TouchableOpacity>
            <View style={styles.settingDivider} />
            <TouchableOpacity 
              style={styles.settingItem}
              onPress={async () => {
                if (Platform.OS === 'web') {
                  const confirmed = window.confirm('정말 로그아웃 하시겠습니까?\n모든 데이터가 초기화됩니다.');
                  if (confirmed) {
                    try {
                      console.log('🚪 로그아웃 시작...');
                      
                      // AsyncStorage의 모든 데이터 삭제
                      const allKeys = await AsyncStorage.getAllKeys();
                      console.log('삭제할 데이터 키:', allKeys);
                      await AsyncStorage.multiRemove(allKeys);
                      
                      // StorageService로도 추가 삭제
                      await StorageService.clearAllData();
                      
                      console.log('✅ 모든 데이터 삭제 완료');
                      
                      // 시작 화면(welcome)으로 이동
                      router.replace('/(auth)/welcome');
                    } catch (error) {
                      console.error('로그아웃 오류:', error);
                      window.alert('로그아웃 중 문제가 발생했습니다.');
                    }
                  }
                } else {
                  Alert.alert(
                    '로그아웃',
                    '정말 로그아웃 하시겠습니까?\n모든 데이터가 초기화됩니다.',
                    [
                      { text: '취소', style: 'cancel' },
                      {
                        text: '로그아웃',
                        style: 'destructive',
                        onPress: async () => {
                          try {
                            console.log('🚪 로그아웃 시작...');
                            
                            // AsyncStorage의 모든 데이터 삭제
                            const allKeys = await AsyncStorage.getAllKeys();
                            console.log('삭제할 데이터 키:', allKeys);
                            await AsyncStorage.multiRemove(allKeys);
                            
                            // StorageService로도 추가 삭제
                            await StorageService.clearAllData();
                            
                            console.log('✅ 모든 데이터 삭제 완료');
                            
                            // 시작 화면(welcome)으로 이동
                            router.replace('/(auth)/welcome');
                          } catch (error) {
                            console.error('로그아웃 오류:', error);
                            Alert.alert('오류', '로그아웃 중 문제가 발생했습니다.');
                          }
                        }
                      }
                    ]
                  );
                }
              }}
            >
              <Text style={[styles.settingText, { color: '#FF6B6B' }]}>🚪 로그아웃</Text>
              <Text style={styles.settingArrow}>→</Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>

      {/* 페르소나 선택 모달 */}
      <Modal
        visible={showPersonaModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowPersonaModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.ricePulModalContainer, { flex: 0.6 }]}>
            <View style={styles.modalHeader}>
              <TouchableOpacity 
                onPress={() => setShowPersonaModal(false)} 
                style={styles.modalCloseButton}
              >
                <Text style={styles.modalCloseButtonText}>✕</Text>
              </TouchableOpacity>
              
              <View style={styles.modalTitleContainer}>
                <Text style={styles.modalTitle}>프로필 선택</Text>
                <Text style={styles.modalSubtitle}>사용할 프로필을 선택하세요</Text>
              </View>
              
              <View style={{ width: 40 }} />
            </View>

            <ScrollView style={styles.modalContent} showsVerticalScrollIndicator={false}>
              {personas.map((persona) => (
                <TouchableOpacity
                  key={persona.id}
                  style={[
                    styles.personaItem,
                    selectedPersona === persona.id && styles.personaItemSelected
                  ]}
                  onPress={() => saveSelectedPersona(persona.id)}
                >
                  <View style={styles.personaInfo}>
                    <Text style={[
                      styles.personaName,
                      selectedPersona === persona.id && styles.personaNameSelected
                    ]}>
                      {persona.name}
                    </Text>
                    <Text style={styles.personaDescription}>
                      {persona.age}세 • 급식카드 {persona.balance.toLocaleString()}원
                    </Text>
                    {persona.id === 'min_ho' && (
                      <Text style={styles.personaDetails}>한식, 패스트푸드, 매운음식 선호</Text>
                    )}
                    {persona.id === 'myeong_bin' && (
                      <Text style={styles.personaDetails}>양식, 카페, 단맛 선호 • 견과류 알러지</Text>
                    )}
                    {persona.id === 'tae_hoon' && (
                      <Text style={styles.personaDetails}>한식, 중식, 단맛 선호 • 갑각류, 계란 알러지</Text>
                    )}
                  </View>
                  {selectedPersona === persona.id && (
                    <View style={styles.personaCheckmark}>
                      <Text style={styles.personaCheckmarkText}>✓</Text>
                    </View>
                  )}
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* 추천 카테고리 선택 모달 */}
      <Modal
        visible={showCategoryModal}
        animationType="slide"
        transparent={true}
        onRequestClose={closeCategoryModal}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.ricePulModalContainer, { flex: 0.8 }]}>
            <View style={styles.modalHeader}>
              <TouchableOpacity 
                onPress={closeCategoryModal} 
                style={styles.modalCloseButton}
              >
                <Text style={styles.modalCloseButtonText}>✕</Text>
              </TouchableOpacity>
              
              <View style={styles.modalTitleContainer}>
                <Text style={styles.modalTitle}>선호 카테고리</Text>
                <Text style={styles.modalSubtitle}>좋아하는 음식 종류를 선택하세요</Text>
              </View>
              
              <TouchableOpacity 
                onPress={closeCategoryModal} 
                style={styles.modalSaveButton}
              >
                <Text style={styles.modalSaveText}>저장</Text>
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalContent} showsVerticalScrollIndicator={false}>
              <View style={styles.categoryGrid}>
                {AVAILABLE_CATEGORIES.map((category) => (
                  <TouchableOpacity
                    key={category.id}
                    style={[
                      styles.categoryItemCard,
                      selectedCategories.includes(category.id) && styles.categoryItemCardSelected
                    ]}
                    onPress={() => toggleCategory(category.id)}
                  >
                    <Text style={styles.categoryEmoji}>{category.emoji}</Text>
                    <Text style={[
                      styles.categoryName,
                      selectedCategories.includes(category.id) && styles.categoryNameSelected
                    ]}>
                      {category.name}
                    </Text>
                    <Text style={styles.categoryDescription}>{category.description}</Text>
                    {selectedCategories.includes(category.id) && (
                      <View style={styles.categoryCheckIcon}>
                        <Text style={styles.categoryCheckText}>✓</Text>
                      </View>
                    )}
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* 알러지 정보 선택 모달 */}
      <Modal
        visible={showAllergyModal}
        animationType="slide"
        transparent={true}
        onRequestClose={closeAllergyModal}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.ricePulModalContainer, { flex: 0.8 }]}>
            <View style={styles.modalHeader}>
              <TouchableOpacity 
                onPress={closeAllergyModal} 
                style={styles.modalCloseButton}
              >
                <Text style={styles.modalCloseButtonText}>✕</Text>
              </TouchableOpacity>
              
              <View style={styles.modalTitleContainer}>
                <Text style={styles.modalTitle}>알러지 정보</Text>
                <Text style={styles.modalSubtitle}>알러지가 있는 식품을 선택하세요</Text>
              </View>
              
              <TouchableOpacity 
                onPress={closeAllergyModal} 
                style={styles.modalSaveButton}
              >
                <Text style={styles.modalSaveText}>저장</Text>
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalContent} showsVerticalScrollIndicator={false}>
              <View style={styles.categoryGrid}>
                {AVAILABLE_ALLERGIES.map((allergy) => (
                  <TouchableOpacity
                    key={allergy.id}
                    style={[
                      styles.allergyItemCard,
                      selectedAllergies.includes(allergy.id) && styles.allergyItemCardSelected
                    ]}
                    onPress={() => toggleAllergy(allergy.id)}
                  >
                    <Text style={styles.allergyEmoji}>{allergy.emoji}</Text>
                    <Text style={[
                      styles.allergyName,
                      selectedAllergies.includes(allergy.id) && styles.allergyNameSelected
                    ]}>
                      {allergy.name}
                    </Text>
                    <Text style={styles.allergyDescription}>{allergy.description}</Text>
                    {selectedAllergies.includes(allergy.id) && (
                      <View style={styles.allergyCheckIcon}>
                        <Text style={styles.allergyCheckText}>✓</Text>
                      </View>
                    )}
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* 밥풀 상세 모달 */}
      {showRicePulModal && (
        <View style={styles.modalOverlay}>
          <View style={styles.ricePulModalContainer}>
            <View style={styles.modalHeader}>
              <TouchableOpacity 
                onPress={() => setShowRicePulModal(false)} 
                style={styles.modalCloseButton}
              >
                <Text style={styles.modalCloseButtonText}>✕</Text>
              </TouchableOpacity>
              
              <View style={styles.modalTitleContainer}>
                <Text style={styles.modalTitle}>밥풀 & 레벨 현황</Text>
                <Text style={styles.modalSubtitle}>나의 밥풀과 레벨 정보</Text>
              </View>
              
              <TouchableOpacity 
                style={styles.modalRefreshButton}
                onPress={loadIntegratedData}
                activeOpacity={0.7}
              >
                <Text style={styles.modalRefreshButtonText}>🔄</Text>
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalContent} showsVerticalScrollIndicator={false}>
              {/* 밥풀 & 레벨 카드 */}
              <View style={styles.ricePulDetailCard}>
                <View style={styles.ricePulHeader}>
                  <Image source={require('../../assets/rice.png')} style={styles.riceIcon} />
                  <View style={styles.ricePulInfo}>
                    <Text style={styles.ricePulAmount}>{currentRicePul.toLocaleString()}</Text>
                    <Text style={styles.ricePulLabel}>보유 밥풀</Text>
                  </View>
                </View>
                
                {/* 레벨 정보 */}
                {currentLevel && (
                  <View style={styles.levelDetailSection}>
                    <Text style={styles.levelDetailTitle}>
                      🏆 Lv.{currentLevel.level} {currentLevel.title}
                    </Text>
                    <View style={styles.levelProgressDetail}>
                      <View 
                        style={[styles.levelProgressFillDetail, { width: `${getLevelProgress()}%` }]} 
                      />
                    </View>
                    <Text style={styles.levelDetailExp}>
                      {currentLevel.expToNext > 0 
                        ? `다음 레벨까지 ${currentLevel.expToNext}밥풀` 
                        : '최고 레벨 달성!'
                      }
                    </Text>
                    
                    {/* 레벨 혜택 */}
                    <View style={styles.levelBenefits}>
                      <Text style={styles.levelBenefitsTitle}>🎁 현재 혜택</Text>
                      {currentLevel.benefits.map((benefit, index) => (
                        <Text key={index} style={styles.levelBenefit}>• {benefit}</Text>
                      ))}
                    </View>
                  </View>
                )}
              </View>

              {/* 거래 내역 */}
              <View style={styles.historySection}>
                <Text style={styles.historySectionTitle}>📋 최근 거래 내역</Text>
                
                {transactionHistory.length > 0 ? (
                  <View style={styles.historyList}>
                    {transactionHistory.slice(0, 10).map((transaction, index) => (
                      <View key={transaction.id || index} style={styles.historyItem}>
                        <View style={styles.historyContent}>
                          <View style={styles.historyInfo}>
                            <Text style={styles.historyReason}>{transaction.reason}</Text>
                            <Text style={styles.historyDate}>
                              {new Date(transaction.timestamp).toLocaleString('ko-KR', {
                                month: 'short',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit'
                              })}
                            </Text>
                          </View>
                          <View style={styles.historyAmount}>
                            <Text style={[
                              styles.historyAmountText,
                              transaction.amount > 0
                                ? styles.historyAmountEarn 
                                : styles.historyAmountSpend
                            ]}>
                              {transaction.amount > 0 ? '+' : ''}{transaction.amount}
                            </Text>
                          </View>
                        </View>
                      </View>
                    ))}
                  </View>
                ) : (
                  <View style={styles.noHistoryContainer}>
                    <Text style={styles.noHistoryEmoji}>📝</Text>
                    <Text style={styles.noHistoryText}>아직 거래 내역이 없어요</Text>
                    <Text style={styles.noHistoryDesc}>챗봇과 대화하고 밥풀을 모아보세요!</Text>
                  </View>
                )}
              </View>
            </ScrollView>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fafafa',
  },
  appHeader: {
    padding: 20,
    paddingBottom: 15,
    backgroundColor: 'white',
  },
  appTitle: {
    fontSize: 28,
    fontWeight: '800',
    color: '#020202ff',
    letterSpacing: 0.5,
  },
  profileBanner: {
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
  profileContent: {
    padding: 24,
  },
  profileRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
  },
  profileAvatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#e5e7eb',
    marginRight: 16,
  },
  profileInfo: {
    flex: 1,
  },
  profileName: {
    fontSize: 20,
    fontWeight: '700',
    color: '#333',
    marginBottom: 4,
  },
  profilePhone: {
    fontSize: 14,
    color: '#555',
    marginBottom: 12,
  },
  // 주소 및 날씨 관련 스타일 (사용되지 않음, 추후 제거 예정)
  addressContainer: {
    backgroundColor: 'rgba(0,0,0,0.6)',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 12,
    marginBottom: 8,
    alignSelf: 'flex-start',
    maxWidth: '90%',
  },
  addressText: {
    color: 'white',
    fontSize: 12,
    fontWeight: '500',
    marginBottom: 2,
  },
  weatherText: {
    color: 'white',
    fontSize: 11,
    opacity: 0.9,
  },
  levelContainer: {
    marginBottom: 12,
  },
  levelText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 6,
  },
  levelProgress: {
    width: '100%',
    height: 6,
    backgroundColor: 'rgba(0,0,0,0.2)',
    borderRadius: 3,
    marginBottom: 4,
  },
  levelProgressFill: {
    height: '100%',
    backgroundColor: '#fff',
    borderRadius: 3,
  },
  levelExpText: {
    fontSize: 12,
    color: '#666',
  },
  pointsContainer: {
    backgroundColor: 'rgba(0,0,0,0.7)',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
  },
  riceIcon: {
      width: 16,
      height: 16, // 밥알 모양에 맞게 비율 조정
      resizeMode: 'contain',
      transform: [{ rotate: '30deg' }],
  },
  pointsText: {
    color: 'white',
    fontSize: 14,
    fontWeight: '600',
  },
  editProfileButton: {
    backgroundColor: 'rgba(255, 255, 255, 0.9)',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 16,
    marginLeft: 12,
    alignSelf: 'flex-start',
  },
  editProfileButtonText: {
    color: '#333',
    fontSize: 12,
    fontWeight: '600',
  },
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
  seeAllText: {
    fontSize: 14,
    color: '#FFBF00',
    fontWeight: '600',
  },
  editCard: {
    backgroundColor: 'white',
    borderRadius: 16,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: '#333',
    marginBottom: 4,
  },
  input: {
    backgroundColor: 'white',
    borderWidth: 1,
    borderColor: '#d1d5db',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 16,
    marginBottom: 12,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 8,
  },
  saveButton: {
    backgroundColor: '#FFBF00',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
    flex: 1,
  },
  saveButtonText: {
    color: '#333',
    fontWeight: '700',
    textAlign: 'center',
    fontSize: 16,
  },
  cancelButton: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#ddd',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
    flex: 1,
  },
  cancelButtonText: {
    color: '#666',
    fontSize: 14,
    fontWeight: '500',
    textAlign: 'center',
  },
  cardInfoCard: {
    backgroundColor: 'white',
    borderRadius: 16,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  mealCardContainer: {
    padding: 4,
  },
  mealCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  mealCardTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  registeredBadge: {
    backgroundColor: '#dcfce7',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  registeredBadgeText: {
    color: '#166534',
    fontSize: 12,
    fontWeight: '700',
  },
  mealCardBalance: {
    alignItems: 'center',
    marginBottom: 16,
    padding: 16,
    backgroundColor: '#f8f9fa',
    borderRadius: 12,
  },
  balanceLabel: {
    fontSize: 14,
    color: '#666',
    marginBottom: 4,
  },
  balanceAmount: {
    fontSize: 24,
    fontWeight: '700',
    color: '#333',
  },
  mealCardInfo: {
    backgroundColor: '#f0f8ff',
    padding: 12,
    borderRadius: 8,
    marginBottom: 12,
  },
  cardNumberText: {
    fontSize: 12,
    color: '#666',
    marginBottom: 2,
  },
  lastUsedText: {
    fontSize: 12,
    color: '#666',
  },
  discountBadge: {
    backgroundColor: '#fff3cd',
    padding: 8,
    borderRadius: 8,
    alignItems: 'center',
  },
  discountText: {
    fontSize: 12,
    color: '#856404',
    fontWeight: '600',
  },
  cardActions: {
    alignItems: 'center',
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#f0f0f0',
  },
  deleteCardButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#F44336',
    borderRadius: 8,
  },
  deleteCardButtonText: {
    fontSize: 12,
    color: '#F44336',
    fontWeight: '600',
  },
  noCardContainer: {
    alignItems: 'center',
    paddingVertical: 30,
  },
  noCardText: {
    fontSize: 16,
    fontWeight: '500',
    color: '#666',
    textAlign: 'center',
  },
  regionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 12,
  },
  regionButton: {
    backgroundColor: '#f3f4f6',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e5e7eb',
  },
  regionButtonSelected: {
    backgroundColor: '#FFBF00',
    borderColor: '#FFBF00',
  },
  regionButtonText: {
    fontSize: 12,
    color: '#374151',
    fontWeight: '500',
  },
  regionButtonTextSelected: {
    color: '#333',
    fontWeight: '700',
  },
  // 주소 표시 카드
  addressDisplayCard: {
    backgroundColor: 'white',
    borderRadius: 16,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  addressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  addressTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  weatherBadge: {
    backgroundColor: '#e3f5ff',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#81d4fa',
  },
  weatherBadgeText: {
    fontSize: 12,
    color: '#0277bd',
    fontWeight: '500',
  },
  addressDisplayText: {
    fontSize: 14,
    color: '#333',
    lineHeight: 20,
  },
  detailAddressText: {
    fontSize: 12,
    color: '#666',
    marginTop: 4,
  },
  noAddressContainer: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  noAddressText: {
    fontSize: 16,
    fontWeight: '500',
    color: '#666',
    marginBottom: 4,
  },
  noAddressSubtext: {
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
  },
  // 밥풀 카드
  ricePulSummaryCard: {
    backgroundColor: 'white',
    borderRadius: 16,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  ricePulSummaryContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  ricePulSummaryInfo: {
    flex: 1,
  },
  ricePulSummaryAmount: {
    fontSize: 20,
    fontWeight: '700',
    color: '#333',
  },
  ricePulSummaryLabel: {
    fontSize: 14,
    color: '#666',
    marginTop: 2,
  },
  ricePulLevelText: {
    fontSize: 12,
    color: '#FFBF00',
    fontWeight: '600',
    marginTop: 4,
  },
  ricePulSummaryArrow: {
    width: 24,
    height: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  ricePulArrowText: {
    fontSize: 16,
    color: '#6b7280',
  },
  // 설정 카드
  settingsCard: {
    backgroundColor: 'white',
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  settingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  settingText: {
    fontSize: 16,
    color: '#333',
    fontWeight: '500',
  },
  settingArrow: {
    fontSize: 16,
    color: '#6b7280',
  },
  settingDivider: {
    height: 1,
    backgroundColor: '#f3f4f6',
    marginHorizontal: 20,
  },
  // 모달 관련 스타일
  modalContainer: {
    flex: 1,
    backgroundColor: 'white',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  modalCancelText: {
    fontSize: 16,
    color: '#666',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
  },
  modalSaveText: {
    fontSize: 16,
    color: '#FF8F00',
    fontWeight: '600',
  },
  modalContent: {
    flex: 1,
    paddingHorizontal: 16,
  },
  modalDescription: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    marginVertical: 16,
    lineHeight: 20,
  },
  weatherContainer: {
    backgroundColor: '#e3f5ff',
    padding: 10,
    borderRadius: 8,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#81d4fa',
  },
  weatherDisplayText: {
    fontSize: 14,
    color: '#0277bd',
    fontWeight: '500',
  },
  savedAddressContainer: {
    padding: 12,
    backgroundColor: '#f8f9fa',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e9ecef',
    marginVertical: 12,
  },
  savedAddressLabel: {
    fontSize: 12,
    color: '#666',
    marginBottom: 4,
  },
  savedAddress: {
    fontSize: 16,
    color: '#333',
    fontWeight: '500',
    marginBottom: 4,
  },
  savedDetailAddress: {
    fontSize: 14,
    color: '#666',
    marginBottom: 12,
  },
  inputContainer: {
    gap: 12,
  },
  textInput: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    backgroundColor: '#fff',
    minHeight: 44,
  },
  button: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  editButton: {
    backgroundColor: '#2196F3',
  },
  editButtonText: {
    color: 'white',
    fontSize: 14,
    fontWeight: '600',
  },
  deleteButton: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#f44336',
  },
  deleteButtonText: {
    color: '#f44336',
    fontSize: 14,
    fontWeight: '500',
  },
  searchButton: {
    backgroundColor: '#fff3e0',
    borderWidth: 1,
    borderColor: '#ff9800',
  },
  searchButtonText: {
    color: '#ff9800',
    fontSize: 14,
    fontWeight: '500',
  },
  locationButton: {
    backgroundColor: '#e3f2fd',
    borderWidth: 1,
    borderColor: '#2196f3',
  },
  locationButtonText: {
    color: '#2196f3',
    fontSize: 14,
    fontWeight: '500',
  },
  searchResultsContainer: {
    marginTop: 12,
    backgroundColor: '#f8f9fa',
    borderRadius: 8,
    padding: 12,
    maxHeight: 200,
  },
  searchResultsTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  searchResultsList: {
    maxHeight: 150,
  },
  searchResultItem: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: 'white',
    borderRadius: 6,
    marginBottom: 6,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  searchResultName: {
    fontSize: 14,
    fontWeight: '500',
    color: '#333',
  },
  searchResultAddress: {
    fontSize: 12,
    color: '#666',
    marginTop: 2,
  },
  // 밥풀 모달
  modalOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
    zIndex: 1000,
  },
  ricePulModalContainer: {
    flex: 0.9,
    backgroundColor: '#f8f9fa',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    overflow: 'hidden',
  },
  modalCloseButton: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 20,
    backgroundColor: '#f8f9fa',
  },
  modalCloseButtonText: {
    fontSize: 18,
    color: '#666',
    fontWeight: 'bold',
  },
  modalTitleContainer: {
    flex: 1,
    alignItems: 'center',
  },
  modalSubtitle: {
    fontSize: 14,
    color: '#666',
    marginTop: 2,
  },
  modalRefreshButton: {
    width: 40,
    height: 40,
    backgroundColor: '#f3f4f6',
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalRefreshButtonText: {
    fontSize: 16,
  },
  ricePulDetailCard: {
    backgroundColor: 'white',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  ricePulHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#f3f4f6',
  },
  ricePulInfo: {
    flex: 1,
  },
  ricePulAmount: {
    fontSize: 24,
    fontWeight: '700',
    color: '#333',
  },
  ricePulLabel: {
    fontSize: 14,
    color: '#666',
    marginTop: 2,
  },
  levelDetailSection: {
    backgroundColor: '#f8f9fa',
    borderRadius: 12,
    padding: 16,
  },
  levelDetailTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 12,
    textAlign: 'center',
  },
  levelProgressDetail: {
    width: '100%',
    height: 8,
    backgroundColor: '#e5e7eb',
    borderRadius: 4,
    marginBottom: 8,
  },
  levelProgressFillDetail: {
    height: '100%',
    backgroundColor: '#FFBF00',
    borderRadius: 4,
  },
  levelDetailExp: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    marginBottom: 16,
  },
  levelBenefits: {
    backgroundColor: '#fff',
    padding: 12,
    borderRadius: 8,
  },
  levelBenefitsTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  levelBenefit: {
    fontSize: 12,
    color: '#666',
    marginBottom: 4,
  },
  historySection: {
    backgroundColor: 'white',
    borderRadius: 16,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  historySectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#333',
    marginBottom: 16,
  },
  historyList: {
    gap: 12,
  },
  historyItem: {
    backgroundColor: '#f8f9fa',
    borderRadius: 12,
    padding: 16,
  },
  historyContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  historyInfo: {
    flex: 1,
  },
  historyReason: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  historyDate: {
    fontSize: 12,
    color: '#666',
  },
  historyAmount: {
    alignItems: 'flex-end',
  },
  historyAmountText: {
    fontSize: 16,
    fontWeight: '700',
  },
  historyAmountEarn: {
    color: '#22c55e',
  },
  historyAmountSpend: {
    color: '#ef4444',
  },
  noHistoryContainer: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  noHistoryEmoji: {
    fontSize: 48,
    marginBottom: 12,
  },
  noHistoryText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 8,
  },
  noHistoryDesc: {
    fontSize: 14,
    color: '#6b7280',
    textAlign: 'center',
  },
  // 카드 공통 스타일
  cardContentItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
  },
  cardContentInfo: {
    flex: 1,
  },
  cardContentLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  cardContentValue: {
    fontSize: 14,
    color: '#FF8F00',
    fontWeight: '500',
    marginBottom: 4,
  },
  cardContentDescription: {
    fontSize: 13,
    color: '#666',
    lineHeight: 18,
  },
  cardArrow: {
    fontSize: 20,
    color: '#9e9e9e',
  },
  ricePulAmount: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFBF00',
    marginBottom: 4,
  },
  levelInfoContainer: {
    marginTop: 8,
  },
  levelInfoText: {
    fontSize: 13,
    color: '#666',
    marginBottom: 4,
  },
  levelProgressMini: {
    width: 120,
    height: 4,
    backgroundColor: '#e0e0e0',
    borderRadius: 2,
  },
  levelProgressFillMini: {
    height: '100%',
    backgroundColor: '#FFBF00',
    borderRadius: 2,
  },
  allergyWarningText: {
    color: '#f44336',
    fontWeight: '600',
  },
  allergyDescriptionText: {
    color: '#c62828',
  },
  settingItemWithSwitch: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
  },
  // 추천 카테고리 관련 스타일
  categorySettingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  categoryInfo: {
    flex: 1,
  },
  categoryCount: {
    fontSize: 14,
    color: '#FF8F00',
    fontWeight: '500',
    marginTop: 2,
  },
  selectedCategoriesContainer: {
    backgroundColor: '#fff3e0',
    padding: 12,
    borderRadius: 8,
    marginTop: 12,
    borderWidth: 1,
    borderColor: '#ffcc02',
  },
  selectedCategoriesText: {
    fontSize: 14,
    color: '#e65100',
    lineHeight: 20,
  },
  // 알러지 관련 스타일
  allergyWarning: {
    color: '#f44336',
    fontWeight: '600',
  },
  selectedAllergiesContainer: {
    backgroundColor: '#ffebee',
    padding: 12,
    borderRadius: 8,
    marginTop: 12,
    borderWidth: 1,
    borderColor: '#f44336',
  },
  selectedAllergiesText: {
    fontSize: 14,
    color: '#c62828',
    lineHeight: 20,
    fontWeight: '500',
  },
  // 설정 항목 스타일
  settingInfo: {
    flex: 1,
    marginRight: 16,
  },
  settingLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  settingDescription: {
    fontSize: 14,
    color: '#666',
    marginTop: 4,
  },
  // 페르소나 모달 스타일
  personaItem: {
    backgroundColor: 'white',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: '#f0f0f0',
    flexDirection: 'row',
    alignItems: 'center',
  },
  personaItemSelected: {
    borderColor: '#FFB000',
    backgroundColor: '#fff8e1',
  },
  personaInfo: {
    flex: 1,
  },
  personaName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  personaNameSelected: {
    color: '#FF8F00',
  },
  personaDescription: {
    fontSize: 14,
    color: '#666',
    marginBottom: 4,
  },
  personaDetails: {
    fontSize: 12,
    color: '#999',
    fontStyle: 'italic',
  },
  personaCheckmark: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#FFB000',
    justifyContent: 'center',
    alignItems: 'center',
  },
  personaCheckmarkText: {
    color: 'white',
    fontWeight: 'bold',
  },
  // 카테고리 모달 스타일
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    padding: 16,
  },
  categoryItemCard: {
    width: '47%',
    backgroundColor: 'white',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#f0f0f0',
    position: 'relative',
  },
  categoryItemCardSelected: {
    borderColor: '#FFB000',
    backgroundColor: '#fff8e1',
  },
  categoryEmoji: {
    fontSize: 32,
    marginBottom: 8,
  },
  categoryName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  categoryNameSelected: {
    color: '#FF8F00',
  },
  categoryDescription: {
    fontSize: 11,
    color: '#999',
    textAlign: 'center',
  },
  categoryCheckIcon: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#FFB000',
    justifyContent: 'center',
    alignItems: 'center',
  },
  categoryCheckText: {
    color: 'white',
    fontSize: 12,
    fontWeight: 'bold',
  },
  // 알러지 모달 스타일
  allergyItemCard: {
    width: '47%',
    backgroundColor: 'white',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#f0f0f0',
    position: 'relative',
  },
  allergyItemCardSelected: {
    borderColor: '#f44336',
    backgroundColor: '#ffebee',
  },
  allergyEmoji: {
    fontSize: 32,
    marginBottom: 8,
  },
  allergyName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  allergyNameSelected: {
    color: '#c62828',
  },
  allergyDescription: {
    fontSize: 11,
    color: '#999',
    textAlign: 'center',
  },
  allergyCheckIcon: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#f44336',
    justifyContent: 'center',
    alignItems: 'center',
  },
  allergyCheckText: {
    color: 'white',
    fontSize: 12,
    fontWeight: 'bold',
  },
  modalSaveButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  modalSaveText: {
    fontSize: 16,
    color: '#FF8F00',
    fontWeight: '600',
  },
});