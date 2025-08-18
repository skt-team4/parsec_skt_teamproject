import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import React, { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  Modal,
  Platform,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  ScrollView,
} from 'react-native';
import { awardRicePul } from '../../utils/ricePulManager';
import DatePickerField from '../../components/DatePickerField';

interface FoodData {
  id: string;
  foodName: string;
  mealType: 'breakfast' | 'lunch' | 'dinner';
  imageUri: string;
  timestamp: string;
  date: string; // 날짜 필드 추가
  calories?: number;
  confidence?: number;
  nutritionData?: NutritionInfo;
}

interface FoodPrediction {
  label: string;
  score: number;
}

interface NutritionInfo {
  calories: number;
  totalNutrients: {
    [key: string]: {
      label: string;
      quantity: number;
      unit: string;
    };
  };
  dailyIntakeReference?: {
    [key: string]: number;
  };
  nutri_score?: {
    category: string;
    score: number;
  };
}

export default function FoodVisionScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [cameraRef, setCameraRef] = useState<any>(null);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showMealTypeModal, setShowMealTypeModal] = useState(false);
  const [analyzedFood, setAnalyzedFood] = useState<string>('');
  const [foodPredictions, setFoodPredictions] = useState<FoodPrediction[]>([]);
  const [estimatedCalories, setEstimatedCalories] = useState<number>(0);
  const [nutritionInfo, setNutritionInfo] = useState<NutritionInfo | null>(null);
  const [facing, setFacing] = useState<'front' | 'back'>('back');
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [showDatePicker, setShowDatePicker] = useState(false);

  const takePicture = async () => {
    if (cameraRef) {
      try {
        const photo = await cameraRef.takePictureAsync({
          quality: 0.8,
          base64: true,
        });
        setCapturedImage(photo.uri);
        analyzeFood(photo.base64!);
      } catch (error) {
        console.error('사진 촬영 오류:', error);
        Alert.alert('오류', '사진을 촬영할 수 없습니다.');
      }
    }
  };

  const pickImageFromGallery = async () => {
    try {
      console.log('갤러리에서 이미지 선택 시작...');
      
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [4, 3],
        quality: 0.8,
        base64: true,
      });

      console.log('ImagePicker 결과:', result);

      if (!result.canceled && result.assets[0]) {
        console.log('이미지 선택됨:', result.assets[0].uri);
        setCapturedImage(result.assets[0].uri);
        
        if (result.assets[0].base64) {
          console.log('base64 데이터 있음, 분석 시작...');
          analyzeFood(result.assets[0].base64);
        } else {
          console.error('base64 데이터가 없습니다');
          if (Platform.OS === 'web') {
            window.alert('이미지 데이터를 읽을 수 없습니다.');
          } else {
            Alert.alert('오류', '이미지 데이터를 읽을 수 없습니다.');
          }
        }
      } else {
        console.log('이미지 선택이 취소되었습니다');
      }
    } catch (error) {
      console.error('갤러리 선택 오류:', error);
      if (Platform.OS === 'web') {
        window.alert(`이미지 선택 오류: ${error instanceof Error ? error.message : '알 수 없는 오류'}`);
      } else {
        Alert.alert('오류', '이미지를 선택할 수 없습니다.');
      }
    }
  };

  // 웹용 파일을 FormData로 변환하는 헬퍼 함수
  const createFormDataFromFile = async (imageUri: string, base64?: string): Promise<FormData> => {
    const formData = new FormData();
    
    if (Platform.OS === 'web' && base64) {
      // 웹 환경에서 base64를 Blob으로 변환
      try {
        const base64Data = base64.replace(/^data:image\/\w+;base64,/, '');
        const byteCharacters = atob(base64Data);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'image/jpeg' });
        formData.append('file', blob, 'food.jpg');
      } catch (webError) {
        console.error('웹 base64 변환 오류:', webError);
        throw new Error('이미지 변환 실패');
      }
    } else {
      // 모바일 환경
      const filename = imageUri.split('/').pop() || 'food.jpg';
      const match = /\.(\w+)$/.exec(filename);
      const type = match ? `image/${match[1]}` : 'image/jpeg';
      
      formData.append('file', {
        uri: imageUri,
        name: filename,
        type,
      } as any);
    }
    
    return formData;
  };

  const analyzeFood = async (base64Image: string) => {
    setIsAnalyzing(true);
    console.log('음식 분석 시작...');
    
    try {
      // FormData 생성
      const formData = await createFormDataFromFile(capturedImage || '', base64Image);
      
      console.log('LogMeal API 호출 시작: http://localhost:5003/analyze-nutrition');
      
      // LogMeal 기반 통합 영양 분석 API 호출
      const response = await fetch('http://localhost:5003/analyze-nutrition', {
        method: 'POST',
        body: formData,
      });
      
      console.log('API 응답 상태:', response.status);
      
      if (!response.ok) {
        throw new Error(`API 요청 실패: ${response.status}`);
      }
      
      const result = await response.json();
      console.log('LogMeal 분석 결과:', result);
      
      if (result.status === 'success') {
        // 음식명 설정
        const foodNames = result.foodNames || [];
        if (foodNames.length > 0) {
          setAnalyzedFood(foodNames[0]);
          
          // 음식 예측 결과를 포맷팅 (LogMeal 형식에 맞게)
          const predictions = foodNames.map((name: string, index: number) => ({
            label: name,
            score: 90 - (index * 10) // 신뢰도 임시 설정
          }));
          setFoodPredictions(predictions);
        } else {
          setAnalyzedFood('음식');
        }
        
        // LogMeal에서 받은 실제 영양 정보 설정
        if (result.hasNutritionalInfo && result.nutritional_info) {
          setNutritionInfo(result.nutritional_info);
          setEstimatedCalories(result.nutritional_info.calories || 0);
          
          console.log('영양 정보:', {
            calories: result.nutritional_info.calories,
            nutrients: result.nutritional_info.totalNutrients
          });
        } else {
          console.warn('영양 정보가 없습니다');
          setEstimatedCalories(0);
        }
        
        setShowMealTypeModal(true);
      } else {
        throw new Error(result.message || '음식 분석 실패');
      }
    } catch (error) {
      console.error('음식 분석 오류:', error);
      
      // LogMeal API가 실패하면 기존 Korean Food API로 폴백
      console.log('LogMeal 실패, Korean Food API로 폴백...');
      try {
        const formData = await createFormDataFromFile(capturedImage || '', base64Image);
        const fallbackResponse = await fetch('http://localhost:5001/analyze', {
          method: 'POST',
          body: formData,
        });
        
        if (fallbackResponse.ok) {
          const fallbackResult = await fallbackResponse.json();
          if (fallbackResult.status === 'success' && fallbackResult.predictions) {
            setFoodPredictions(fallbackResult.predictions);
            const topFood = fallbackResult.predictions[0];
            setAnalyzedFood(topFood.label);
            
            // 기본 영양 정보 설정
            setEstimatedCalories(250);
            setShowMealTypeModal(true);
            return;
          }
        }
      } catch (fallbackError) {
        console.error('폴백도 실패:', fallbackError);
      }
      
      if (Platform.OS === 'web') {
        window.alert(`오류: ${error instanceof Error ? error.message : '음식을 인식할 수 없습니다.'}`);
      } else {
        Alert.alert('오류', '음식을 인식할 수 없습니다. 다시 시도해주세요.');
      }
    } finally {
      setIsAnalyzing(false);
    }
  };

  const saveFoodData = async (mealType: 'breakfast' | 'lunch' | 'dinner') => {
    if (!capturedImage || !analyzedFood) return;

    const foodData: FoodData = {
      id: Date.now().toString(),
      foodName: analyzedFood,
      mealType,
      imageUri: capturedImage,
      timestamp: selectedDate.toISOString(),
      date: selectedDate.toISOString().split('T')[0], // YYYY-MM-DD 형식
      calories: estimatedCalories,
      confidence: 0.85,
      nutritionData: nutritionInfo || undefined,
    };

    try {
      // 로컬 스토리지에 저장
      const existingData = await AsyncStorage.getItem('foodHistory');
      const foodHistory: FoodData[] = existingData ? JSON.parse(existingData) : [];
      foodHistory.unshift(foodData);
      if (foodHistory.length > 100) {
        foodHistory.splice(100);
      }
      await AsyncStorage.setItem('foodHistory', JSON.stringify(foodHistory));
      
      // 영양소 분석 기록 서버에도 저장
      try {
        const historyResponse = await fetch('http://localhost:5004/api/save-nutrition', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            foodName: analyzedFood,
            mealType,
            calories: estimatedCalories,
            nutritionInfo: nutritionInfo,
            nutriScore: nutritionInfo?.nutri_score,
            imageUri: capturedImage,
            userId: 'guest'
          })
        });
        
        const historyResult = await historyResponse.json();
        console.log('영양소 분석 기록 저장:', historyResult);
      } catch (historyError) {
        console.error('영양소 분석 기록 서버 저장 실패:', historyError);
        // 서버 저장 실패해도 계속 진행
      }
      
      // 밥풀 10개 보상 제공
      const ricePulResult = await awardRicePul(10, '음식 기록 저장', 'food_recommendation');
      
      let alertMessage = `${analyzedFood}이(가) ${getMealTypeKorean(mealType)} 기록에 저장되었습니다.\n\n🍚 밥풀 10개를 받았습니다!`;
      
      if (ricePulResult.levelUp && ricePulResult.newLevel) {
        alertMessage += `\n\n🎉 레벨업! ${ricePulResult.newLevel.title}이(가) 되었습니다!`;
      }
      
      Alert.alert(
        '저장 완료!',
        alertMessage,
        [{ text: '확인', onPress: resetCamera }]
      );
      
      setShowMealTypeModal(false);
    } catch (error) {
      console.error('데이터 저장 오류:', error);
      Alert.alert('오류', '데이터를 저장할 수 없습니다.');
    }
  };

  const getMealTypeKorean = (mealType: string): string => {
    switch (mealType) {
      case 'breakfast': return '아침식사';
      case 'lunch': return '점심식사';
      case 'dinner': return '저녁식사';
      default: return '식사';
    }
  };

  const resetCamera = () => {
    setCapturedImage(null);
    setAnalyzedFood('');
    setEstimatedCalories(0);
    setFoodPredictions([]);
    setNutritionInfo(null);
    setShowMealTypeModal(false);
    setSelectedDate(new Date()); // 날짜를 오늘로 리셋
  };


  // 웹에서는 카메라 권한 체크를 스킵하고 갤러리 선택 UI 제공
  if (Platform.OS === 'web') {
    // 웹에서는 권한 체크 없이 바로 갤러리 선택 가능
    if (!capturedImage && !permission?.granted) {
      return (
        <View style={styles.container}>
          <View style={styles.webContainer}>
            <Ionicons name="camera" size={80} color="#007AFF" />
            <Text style={styles.webTitle}>음식 사진 분석</Text>
            <Text style={styles.webSubtitle}>
              갤러리에서 음식 사진을 선택하거나 카메라로 직접 촬영하세요
            </Text>
            
            <TouchableOpacity style={styles.uploadButton} onPress={pickImageFromGallery}>
              <Ionicons name="images" size={24} color="white" />
              <Text style={styles.uploadButtonText}>갤러리에서 선택</Text>
            </TouchableOpacity>
            
            <Text style={styles.alternativeText}>또는</Text>
            
            <TouchableOpacity style={[styles.button, styles.secondaryButton]} onPress={requestPermission}>
              <Ionicons name="camera-outline" size={24} color="white" />
              <Text style={styles.buttonText}>카메라 사용</Text>
            </TouchableOpacity>
            
            <Text style={styles.supportedText}>
              지원 형식: JPG, PNG, WEBP
            </Text>
          </View>
        </View>
      );
    }
  } else {
    // 모바일에서만 카메라 권한 체크
    if (!permission) {
      return (
        <View style={styles.container}>
          <ActivityIndicator size="large" color="#007AFF" />
          <Text style={styles.loadingText}>카메라 권한을 확인하는 중...</Text>
        </View>
      );
    }

    if (!permission.granted) {
      return (
        <View style={styles.container}>
          <View style={styles.setupContainer}>
            <Ionicons name="camera-off" size={64} color="#007AFF" />
            <Text style={styles.setupTitle}>카메라 권한이 필요합니다</Text>
            <Text style={styles.setupText}>
              음식 사진을 촬영하기 위해 카메라 접근 권한이 필요합니다.
            </Text>
            <TouchableOpacity style={styles.button} onPress={requestPermission}>
              <Text style={styles.buttonText}>권한 허용</Text>
            </TouchableOpacity>
            
            <Text style={styles.alternativeText}>또는</Text>
            
            <TouchableOpacity style={[styles.button, styles.secondaryButton]} onPress={pickImageFromGallery}>
              <Ionicons name="images" size={20} color="white" />
              <Text style={styles.buttonText}>갤러리에서 선택</Text>
            </TouchableOpacity>
          </View>
        </View>
      );
    }
  }

  if (capturedImage) {
    return (
      <View style={styles.container}>
        <Image source={{ uri: capturedImage }} style={styles.capturedImage} />
        
        {isAnalyzing ? (
          <View style={styles.analyzingContainer}>
            <ActivityIndicator size="large" color="#007AFF" />
            <Text style={styles.analyzingText}>음식을 분석하는 중...</Text>
          </View>
        ) : analyzedFood ? (
          <View style={styles.resultContainer}>
            <Text style={styles.resultTitle}>인식된 음식</Text>
            <Text style={styles.foodName}>{analyzedFood}</Text>
            <Text style={styles.calories}>칼로리: {Math.round(estimatedCalories)}kcal</Text>
            
            {/* 영양 점수 표시 */}
            {nutritionInfo?.nutri_score && (
              <View style={styles.nutriScoreContainer}>
                <Text style={styles.nutriScoreLabel}>영양 등급: </Text>
                <Text style={[styles.nutriScore, { 
                  backgroundColor: nutritionInfo.nutri_score.category === 'A' ? '#28a745' :
                                  nutritionInfo.nutri_score.category === 'B' ? '#6f42c1' :
                                  nutritionInfo.nutri_score.category === 'C' ? '#fd7e14' :
                                  nutritionInfo.nutri_score.category === 'D' ? '#dc3545' : '#6c757d'
                }]}>
                  {nutritionInfo.nutri_score.category}
                </Text>
              </View>
            )}
            
            {/* 주요 영양소 정보 표시 */}
            {nutritionInfo && (
              <View style={styles.nutritionContainer}>
                <Text style={styles.nutritionTitle}>주요 영양소 정보</Text>
                <View style={styles.nutritionGrid}>
                  {nutritionInfo.totalNutrients.PROCNT && (
                    <View style={styles.nutritionItem}>
                      <Text style={styles.nutritionLabel}>단백질</Text>
                      <Text style={styles.nutritionValue}>
                        {nutritionInfo.totalNutrients.PROCNT.quantity.toFixed(1)}g
                      </Text>
                    </View>
                  )}
                  {nutritionInfo.totalNutrients.CHOCDF && (
                    <View style={styles.nutritionItem}>
                      <Text style={styles.nutritionLabel}>탄수화물</Text>
                      <Text style={styles.nutritionValue}>
                        {nutritionInfo.totalNutrients.CHOCDF.quantity.toFixed(1)}g
                      </Text>
                    </View>
                  )}
                  {nutritionInfo.totalNutrients.FAT && (
                    <View style={styles.nutritionItem}>
                      <Text style={styles.nutritionLabel}>지방</Text>
                      <Text style={styles.nutritionValue}>
                        {nutritionInfo.totalNutrients.FAT.quantity.toFixed(1)}g
                      </Text>
                    </View>
                  )}
                  {nutritionInfo.totalNutrients.FIBTG && (
                    <View style={styles.nutritionItem}>
                      <Text style={styles.nutritionLabel}>식이섬유</Text>
                      <Text style={styles.nutritionValue}>
                        {nutritionInfo.totalNutrients.FIBTG.quantity.toFixed(1)}g
                      </Text>
                    </View>
                  )}
                  {nutritionInfo.totalNutrients.NA && (
                    <View style={styles.nutritionItem}>
                      <Text style={styles.nutritionLabel}>나트륨</Text>
                      <Text style={styles.nutritionValue}>
                        {nutritionInfo.totalNutrients.NA.quantity.toFixed(0)}mg
                      </Text>
                    </View>
                  )}
                  {nutritionInfo.totalNutrients.SUGAR && (
                    <View style={styles.nutritionItem}>
                      <Text style={styles.nutritionLabel}>당류</Text>
                      <Text style={styles.nutritionValue}>
                        {nutritionInfo.totalNutrients.SUGAR.quantity.toFixed(1)}g
                      </Text>
                    </View>
                  )}
                </View>
              </View>
            )}
            
            {/* 다른 가능성 있는 음식들 표시 */}
            {foodPredictions.length > 1 && (
              <View style={styles.otherPredictions}>
                <Text style={styles.otherPredictionsTitle}>다른 가능성:</Text>
                {foodPredictions.slice(1, 4).map((pred, index) => (
                  <Text key={index} style={styles.otherPredictionItem}>
                    • {pred.label} ({(pred.score).toFixed(1)}%)
                  </Text>
                ))}
              </View>
            )}
          </View>
        ) : null}

        <View style={styles.bottomControls}>
          <TouchableOpacity style={styles.retakeButton} onPress={resetCamera}>
            <Ionicons name="refresh" size={24} color="white" />
            <Text style={styles.controlButtonText}>다시 촬영</Text>
          </TouchableOpacity>
        </View>

        {/* 식사 시간 선택 모달 */}
        <Modal
          visible={showMealTypeModal}
          transparent
          animationType="slide"
          onRequestClose={() => setShowMealTypeModal(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <Text style={styles.modalTitle}>언제 먹은 음식인가요?</Text>
              <Text style={styles.modalSubtitle}>{analyzedFood}</Text>
              
              {/* 날짜 선택 섹션 */}
              <View style={styles.dateSection}>
                <Text style={styles.dateSectionTitle}>📅 날짜 선택</Text>
                <DatePickerField
                  value={selectedDate}
                  onChange={setSelectedDate}
                  showPicker={showDatePicker}
                  setShowPicker={setShowDatePicker}
                />
              </View>

              {/* 식사 시간 선택 섹션 */}
              <Text style={styles.mealSectionTitle}>🍽️ 식사 시간</Text>
              
              <TouchableOpacity
                style={[styles.mealButton, { backgroundColor: '#FF6B6B' }]}
                onPress={() => saveFoodData('breakfast')}
              >
                <Ionicons name="sunny" size={24} color="white" />
                <Text style={styles.mealButtonText}>아침식사</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.mealButton, { backgroundColor: '#4ECDC4' }]}
                onPress={() => saveFoodData('lunch')}
              >
                <Ionicons name="partly-sunny" size={24} color="white" />
                <Text style={styles.mealButtonText}>점심식사</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.mealButton, { backgroundColor: '#45B7D1' }]}
                onPress={() => saveFoodData('dinner')}
              >
                <Ionicons name="moon" size={24} color="white" />
                <Text style={styles.mealButtonText}>저녁식사</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.cancelButton}
                onPress={() => {
                  setShowMealTypeModal(false);
                  setShowDatePicker(false);
                }}
              >
                <Text style={styles.cancelButtonText}>취소</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>
      </View>
    );
  }

  // 모든 플랫폼에서 카메라 UI 제공
  return (
    <View style={styles.container}>
      <CameraView
        style={styles.camera}
        facing={facing}
        ref={(ref) => setCameraRef(ref)}
      />
      
      <View style={styles.overlay}>
        <View style={styles.topControls}>
          <Text style={styles.title}>음식 사진을 촬영하세요</Text>
          <Text style={styles.subtitle}>AI가 자동으로 음식을 인식합니다</Text>
        </View>

        <View style={styles.focusArea}>
          <View style={styles.focusCorners}>
            <View style={[styles.corner, styles.topLeft]} />
            <View style={[styles.corner, styles.topRight]} />
            <View style={[styles.corner, styles.bottomLeft]} />
            <View style={[styles.corner, styles.bottomRight]} />
          </View>
        </View>

        <View style={styles.bottomControls}>
          <TouchableOpacity style={styles.galleryButton} onPress={pickImageFromGallery}>
            <Ionicons name="images" size={24} color="white" />
          </TouchableOpacity>

          <TouchableOpacity style={styles.captureButton} onPress={takePicture}>
            <View style={styles.captureButtonInner} />
          </TouchableOpacity>

          <View style={styles.placeholder} />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  camera: {
    flex: 1,
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'space-between',
  },
  topControls: {
    paddingTop: 60,
    paddingHorizontal: 20,
    alignItems: 'center',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: 'white',
    textAlign: 'center',
    textShadowColor: 'rgba(0,0,0,0.8)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  subtitle: {
    fontSize: 16,
    color: 'rgba(255,255,255,0.8)',
    textAlign: 'center',
    marginTop: 8,
    textShadowColor: 'rgba(0,0,0,0.8)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  focusArea: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  focusCorners: {
    width: 250,
    height: 250,
    position: 'relative',
  },
  corner: {
    position: 'absolute',
    width: 30,
    height: 30,
    borderColor: 'white',
    borderWidth: 3,
  },
  topLeft: {
    top: 0,
    left: 0,
    borderBottomWidth: 0,
    borderRightWidth: 0,
  },
  topRight: {
    top: 0,
    right: 0,
    borderBottomWidth: 0,
    borderLeftWidth: 0,
  },
  bottomLeft: {
    bottom: 0,
    left: 0,
    borderTopWidth: 0,
    borderRightWidth: 0,
  },
  bottomRight: {
    bottom: 0,
    right: 0,
    borderTopWidth: 0,
    borderLeftWidth: 0,
  },
  bottomControls: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingBottom: 50,
    paddingHorizontal: 40,
  },
  galleryButton: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: 'rgba(255,255,255,0.3)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  captureButton: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: 'white',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 4,
    borderColor: 'rgba(255,255,255,0.5)',
  },
  captureButtonInner: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: 'white',
    borderWidth: 2,
    borderColor: '#007AFF',
  },
  placeholder: {
    width: 50,
    height: 50,
  },
  capturedImage: {
    width: '100%',
    height: '60%',
    resizeMode: 'cover',
  },
  analyzingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'white',
  },
  analyzingText: {
    fontSize: 18,
    color: '#333',
    marginTop: 16,
  },
  resultContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'white',
    padding: 20,
  },
  resultTitle: {
    fontSize: 18,
    color: '#666',
    marginBottom: 8,
  },
  foodName: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 8,
  },
  calories: {
    fontSize: 16,
    color: '#007AFF',
    fontWeight: '600',
  },
  otherPredictions: {
    marginTop: 20,
    padding: 15,
    backgroundColor: '#f5f5f5',
    borderRadius: 10,
    width: '100%',
  },
  otherPredictionsTitle: {
    fontSize: 14,
    color: '#666',
    fontWeight: '600',
    marginBottom: 8,
  },
  otherPredictionItem: {
    fontSize: 14,
    color: '#333',
    marginVertical: 2,
  },
  retakeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 25,
    marginBottom: 20,
  },
  controlButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalContent: {
    backgroundColor: 'white',
    borderRadius: 20,
    padding: 24,
    width: '85%',
    alignItems: 'center',
  },
  modalTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 8,
  },
  modalSubtitle: {
    fontSize: 18,
    color: '#666',
    marginBottom: 24,
  },
  mealButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingVertical: 16,
    borderRadius: 12,
    width: '100%',
    marginBottom: 12,
  },
  mealButtonText: {
    color: 'white',
    fontSize: 18,
    fontWeight: '600',
    marginLeft: 12,
  },
  cancelButton: {
    paddingVertical: 12,
    paddingHorizontal: 24,
    marginTop: 8,
  },
  cancelButtonText: {
    fontSize: 16,
    color: '#666',
  },
  dateSection: {
    marginBottom: 20,
    paddingHorizontal: 10,
  },
  dateSectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 12,
  },
  dateButton: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  dateButtonText: {
    fontSize: 16,
    color: '#007AFF',
    fontWeight: '500',
  },
  mealSectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 12,
    paddingHorizontal: 10,
  },
  setupContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
    backgroundColor: 'white',
  },
  setupTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginTop: 20,
    marginBottom: 16,
    textAlign: 'center',
  },
  setupText: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    marginBottom: 20,
    paddingHorizontal: 20,
  },
  loadingText: {
    fontSize: 16,
    color: '#666',
    marginTop: 16,
    textAlign: 'center',
  },
  button: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
  secondaryButton: {
    backgroundColor: '#28a745',
    marginTop: 10,
  },
  alternativeText: {
    fontSize: 14,
    color: '#666',
    marginVertical: 10,
  },
  webContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'white',
    padding: 20,
  },
  webTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#333',
    marginTop: 20,
    marginBottom: 10,
  },
  webSubtitle: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    marginBottom: 30,
    lineHeight: 24,
  },
  uploadButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF',
    paddingHorizontal: 30,
    paddingVertical: 15,
    borderRadius: 30,
    marginBottom: 20,
  },
  uploadButtonText: {
    color: 'white',
    fontSize: 18,
    fontWeight: '600',
    marginLeft: 10,
  },
  supportedText: {
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
    marginTop: 10,
  },
  nutriScoreContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    marginBottom: 16,
  },
  nutriScoreLabel: {
    fontSize: 16,
    color: '#666',
    fontWeight: '600',
  },
  nutriScore: {
    fontSize: 16,
    fontWeight: 'bold',
    color: 'white',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
    textAlign: 'center',
    minWidth: 30,
  },
  nutritionContainer: {
    backgroundColor: '#f8f9fa',
    borderRadius: 12,
    padding: 16,
    marginTop: 16,
    width: '100%',
  },
  nutritionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 12,
    textAlign: 'center',
  },
  nutritionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  nutritionItem: {
    width: '48%',
    backgroundColor: 'white',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 1,
    },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 1,
  },
  nutritionLabel: {
    fontSize: 12,
    color: '#666',
    marginBottom: 4,
    textAlign: 'center',
  },
  nutritionValue: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#333',
    textAlign: 'center',
  },
});