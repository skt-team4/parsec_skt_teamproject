// Food Recognition Service
import { API_ENDPOINTS } from '../config/api.config';

export interface FoodPrediction {
  food: string;
  confidence: number;
  food_kr?: string;
}

export interface FoodRecognitionResponse {
  status: string;
  predictions: FoodPrediction[];
  food_item: string;
  confidence: number;
}

export interface NutritionInfo {
  calories?: number;
  protein?: number;
  carbohydrates?: number;
  fat?: number;
  fiber?: number;
  sodium?: number;
  sugar?: number;
  [key: string]: any;
}

export interface NutritionAnalysisResponse {
  status: string;
  foodNames: string[];
  nutritional_info: NutritionInfo;
  nutri_score?: string;
  message?: string;
}

export interface NutritionHistoryRecord {
  id: number;
  userId: string;
  foodName: string;
  mealType: string;
  calories: number;
  nutritionInfo: NutritionInfo;
  nutriScore?: string;
  timestamp: string;
}

export interface NutritionHistoryResponse {
  records: NutritionHistoryRecord[];
  total: number;
}

export interface NutritionStatistics {
  totalRecords: number;
  averageCalories: number;
  mealDistribution: {
    breakfast: number;
    lunch: number;
    dinner: number;
    snack: number;
  };
  nutriScoreDistribution: {
    [key: string]: number;
  };
}

// 음식 이미지 인식
export async function recognizeFood(imageUri: string): Promise<FoodRecognitionResponse> {
  try {
    const formData = new FormData();
    
    // React Native에서 이미지 파일 추가
    const imageFile = {
      uri: imageUri,
      type: 'image/jpeg',
      name: 'food.jpg',
    } as any;
    
    formData.append('file', imageFile);
    
    const response = await fetch(API_ENDPOINTS.foodRecognition(), {
      method: 'POST',
      body: formData,
      headers: {
        'Accept': 'application/json',
      },
    });
    
    if (!response.ok) {
      throw new Error(`음식 인식 실패: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('음식 인식 오류:', error);
    throw error;
  }
}

// 영양 정보 분석 (LogMeal API)
export async function analyzeNutrition(imageUri: string): Promise<NutritionAnalysisResponse> {
  try {
    const formData = new FormData();
    
    const imageFile = {
      uri: imageUri,
      type: 'image/jpeg',
      name: 'food.jpg',
    } as any;
    
    formData.append('file', imageFile);
    
    const response = await fetch(API_ENDPOINTS.nutritionAnalyze(), {
      method: 'POST',
      body: formData,
      headers: {
        'Accept': 'application/json',
      },
    });
    
    if (!response.ok) {
      throw new Error(`영양 분석 실패: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('영양 분석 오류:', error);
    throw error;
  }
}

// 영양 기록 저장
export async function saveNutritionRecord(
  foodName: string,
  mealType: string,
  calories: number,
  nutritionInfo: NutritionInfo,
  nutriScore?: string
): Promise<{ status: string; recordId: number; message: string }> {
  try {
    const response = await fetch(API_ENDPOINTS.nutritionSave(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        userId: 'guest', // 기본 사용자
        foodName,
        mealType,
        calories,
        nutritionInfo,
        nutriScore,
      }),
    });
    
    if (!response.ok) {
      throw new Error(`기록 저장 실패: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('영양 기록 저장 오류:', error);
    throw error;
  }
}

// 영양 기록 조회
export async function getNutritionHistory(
  userId: string = 'guest',
  limit: number = 100
): Promise<NutritionHistoryResponse> {
  try {
    const url = `${API_ENDPOINTS.nutritionHistory()}?userId=${userId}&limit=${limit}`;
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`기록 조회 실패: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('영양 기록 조회 오류:', error);
    throw error;
  }
}

// 영양 통계 조회
export async function getNutritionStatistics(userId: string = 'guest'): Promise<NutritionStatistics> {
  try {
    const url = `${API_ENDPOINTS.nutritionStats()}?userId=${userId}`;
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`통계 조회 실패: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('영양 통계 조회 오류:', error);
    throw error;
  }
}

// 영양 기록 삭제
export async function deleteNutritionRecord(recordId: number): Promise<{ status: string; message: string }> {
  try {
    const response = await fetch(API_ENDPOINTS.nutritionDelete(recordId.toString()), {
      method: 'DELETE',
    });
    
    if (!response.ok) {
      throw new Error(`기록 삭제 실패: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('영양 기록 삭제 오류:', error);
    throw error;
  }
}

// 지원되는 음식 목록 조회
export async function getSupportedFoods(): Promise<{ korean_foods: string[]; other_foods: string[]; total: number }> {
  try {
    const response = await fetch(API_ENDPOINTS.foodList());
    
    if (!response.ok) {
      throw new Error(`음식 목록 조회 실패: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('음식 목록 조회 오류:', error);
    throw error;
  }
}