// nutritionAnalyzer.ts - 영양 균형 분석 유틸리티
import AsyncStorage from '@react-native-async-storage/async-storage';

// 영양 데이터 타입
export interface NutritionData {
  calories: number;
  protein?: number;
  carbohydrates?: number;
  fat?: number;
  fiber?: number;
  sodium?: number;
  sugar?: number;
}

export interface DailyNutritionReport {
  date: string;
  meals: {
    breakfast?: NutritionData;
    lunch?: NutritionData;
    dinner?: NutritionData;
  };
  totals: NutritionData;
  balance: {
    score: number; // 0-100, 낮을수록 불균형
    level: 'good' | 'warning' | 'critical'; // good: 균형, warning: 1단계(매우편중), critical: 2단계(편중식사)
    issues: string[];
  };
}

// 권장 영양소 기준 (하루 기준, 청소년 평균)
const DAILY_RECOMMENDATIONS = {
  calories: { min: 1800, max: 2500, ideal: 2100 },
  protein: { min: 40, max: 80, ideal: 60 }, // g
  carbohydrates: { min: 250, max: 400, ideal: 300 }, // g
  fat: { min: 40, max: 80, ideal: 60 }, // g
  fiber: { min: 20, max: 35, ideal: 25 }, // g
  sodium: { min: 0, max: 2300, ideal: 1500 }, // mg
  sugar: { min: 0, max: 50, ideal: 25 }, // g
};

// 영양 균형 점수 계산
export const calculateNutritionBalance = (nutrition: NutritionData): number => {
  let score = 100;
  let penalties = 0;

  // 칼로리 체크
  if (nutrition.calories < DAILY_RECOMMENDATIONS.calories.min) {
    penalties += 20; // 칼로리 부족
  } else if (nutrition.calories > DAILY_RECOMMENDATIONS.calories.max) {
    penalties += 15; // 칼로리 과다
  }

  // 3대 영양소 균형 체크
  const totalMacros = (nutrition.protein || 0) + (nutrition.carbohydrates || 0) + (nutrition.fat || 0);
  if (totalMacros > 0) {
    const proteinRatio = (nutrition.protein || 0) / totalMacros;
    const carbRatio = (nutrition.carbohydrates || 0) / totalMacros;
    const fatRatio = (nutrition.fat || 0) / totalMacros;

    // 이상적인 비율: 탄수화물 50-60%, 단백질 15-20%, 지방 20-30%
    if (carbRatio < 0.4 || carbRatio > 0.7) penalties += 15;
    if (proteinRatio < 0.1 || proteinRatio > 0.3) penalties += 15;
    if (fatRatio < 0.15 || fatRatio > 0.35) penalties += 15;
  } else {
    penalties += 30; // 영양소 데이터 없음
  }

  // 나트륨 과다
  if (nutrition.sodium && nutrition.sodium > DAILY_RECOMMENDATIONS.sodium.max) {
    penalties += 10;
  }

  // 당분 과다
  if (nutrition.sugar && nutrition.sugar > DAILY_RECOMMENDATIONS.sugar.max) {
    penalties += 10;
  }

  // 섬유질 부족
  if (nutrition.fiber && nutrition.fiber < DAILY_RECOMMENDATIONS.fiber.min) {
    penalties += 5;
  }

  score = Math.max(0, score - penalties);
  return score;
};

// 영양 불균형 수준 판단
export const getNutritionBalanceLevel = (score: number): 'good' | 'warning' | 'critical' => {
  if (score >= 70) return 'good';      // 균형잡힌 식사
  if (score >= 40) return 'warning';   // 1단계: 약간 불균형 (매우편중)
  return 'critical';                   // 2단계: 심각한 불균형 (편중식사)
};

// 영양 문제점 분석
export const analyzeNutritionIssues = (nutrition: NutritionData): string[] => {
  const issues: string[] = [];

  // 칼로리 체크
  if (nutrition.calories < DAILY_RECOMMENDATIONS.calories.min) {
    issues.push('칼로리 섭취 부족');
  } else if (nutrition.calories > DAILY_RECOMMENDATIONS.calories.max) {
    issues.push('칼로리 과다 섭취');
  }

  // 단백질 체크
  if (nutrition.protein !== undefined) {
    if (nutrition.protein < DAILY_RECOMMENDATIONS.protein.min) {
      issues.push('단백질 부족');
    } else if (nutrition.protein > DAILY_RECOMMENDATIONS.protein.max) {
      issues.push('단백질 과다');
    }
  }

  // 탄수화물 체크
  if (nutrition.carbohydrates !== undefined) {
    if (nutrition.carbohydrates < DAILY_RECOMMENDATIONS.carbohydrates.min) {
      issues.push('탄수화물 부족');
    } else if (nutrition.carbohydrates > DAILY_RECOMMENDATIONS.carbohydrates.max) {
      issues.push('탄수화물 과다');
    }
  }

  // 지방 체크
  if (nutrition.fat !== undefined) {
    if (nutrition.fat > DAILY_RECOMMENDATIONS.fat.max) {
      issues.push('지방 과다');
    }
  }

  // 나트륨 체크
  if (nutrition.sodium && nutrition.sodium > DAILY_RECOMMENDATIONS.sodium.max) {
    issues.push('나트륨 과다 (짜게 먹음)');
  }

  // 당분 체크
  if (nutrition.sugar && nutrition.sugar > DAILY_RECOMMENDATIONS.sugar.max) {
    issues.push('당분 과다 섭취');
  }

  // 섬유질 체크
  if (nutrition.fiber && nutrition.fiber < DAILY_RECOMMENDATIONS.fiber.min) {
    issues.push('섬유질 부족 (채소 부족)');
  }

  return issues;
};

// 일일 영양 리포트 생성
export const generateDailyNutritionReport = async (date?: Date): Promise<DailyNutritionReport> => {
  const targetDate = date || new Date();
  const dateStr = targetDate.toISOString().split('T')[0];

  try {
    // AsyncStorage에서 해당 날짜의 영양 데이터 가져오기 (foodHistory 사용)
    const foodHistoryData = await AsyncStorage.getItem('foodHistory');
    const history = foodHistoryData ? JSON.parse(foodHistoryData) : [];
    console.log(`🥗 [DEBUG] 전체 음식 히스토리 개수: ${history.length}`);
    console.log(`🥗 [DEBUG] 대상 날짜: ${dateStr}`);

    // 해당 날짜의 식사 데이터 필터링
    const todayMeals = history.filter((item: any) => 
      item.date && item.date.startsWith(dateStr)
    );
    console.log(`🥗 [DEBUG] 오늘 식사 개수: ${todayMeals.length}`, todayMeals);

    // 식사별로 분류
    const meals: DailyNutritionReport['meals'] = {};
    const totals: NutritionData = {
      calories: 0,
      protein: 0,
      carbohydrates: 0,
      fat: 0,
      fiber: 0,
      sodium: 0,
      sugar: 0,
    };

    todayMeals.forEach((meal: any) => {
      const mealData: NutritionData = {
        calories: meal.calories || 0,
        protein: meal.nutritionData?.totalNutrients?.PROCNT?.quantity || 0,
        carbohydrates: meal.nutritionData?.totalNutrients?.CHOCDF?.quantity || 0,
        fat: meal.nutritionData?.totalNutrients?.FAT?.quantity || 0,
        fiber: meal.nutritionData?.totalNutrients?.FIBTG?.quantity || 0,
        sodium: meal.nutritionData?.totalNutrients?.NA?.quantity || 0,
        sugar: meal.nutritionData?.totalNutrients?.SUGAR?.quantity || 0,
      };

      // 식사 시간별 분류
      if (meal.mealType === 'breakfast') {
        meals.breakfast = mealData;
      } else if (meal.mealType === 'lunch') {
        meals.lunch = mealData;
      } else if (meal.mealType === 'dinner') {
        meals.dinner = mealData;
      }

      // 총합 계산
      totals.calories += mealData.calories;
      totals.protein! += mealData.protein || 0;
      totals.carbohydrates! += mealData.carbohydrates || 0;
      totals.fat! += mealData.fat || 0;
      totals.fiber! += mealData.fiber || 0;
      totals.sodium! += mealData.sodium || 0;
      totals.sugar! += mealData.sugar || 0;
    });

    // 균형 점수 계산
    const score = calculateNutritionBalance(totals);
    const level = getNutritionBalanceLevel(score);
    const issues = analyzeNutritionIssues(totals);

    console.log(`🥗 [DEBUG] 영양 균형 계산 완료:`);
    console.log(`  - 총 칼로리: ${totals.calories}`);
    console.log(`  - 단백질: ${totals.protein}g, 탄수화물: ${totals.carbohydrates}g, 지방: ${totals.fat}g`);
    console.log(`  - 균형 점수: ${score}점`);
    console.log(`  - 균형 레벨: ${level}`);
    console.log(`  - 문제점: ${issues.join(', ')}`);

    return {
      date: dateStr,
      meals,
      totals,
      balance: {
        score,
        level,
        issues,
      },
    };
  } catch (error) {
    console.error('영양 리포트 생성 실패:', error);
    
    // 에러 시 기본값 반환
    return {
      date: dateStr,
      meals: {},
      totals: { calories: 0 },
      balance: {
        score: 50,
        level: 'warning',
        issues: ['영양 데이터를 불러올 수 없습니다'],
      },
    };
  }
};

// 캐릭터 애니메이션 결정
export const getCharacterAnimationByNutrition = async (): Promise<string> => {
  const report = await generateDailyNutritionReport();
  console.log(`🎭 [DEBUG] 캐릭터 애니메이션 결정 - 레벨: ${report.balance.level}, 점수: ${report.balance.score}`);
  
  switch (report.balance.level) {
    case 'critical':
      console.log(`🎭 [DEBUG] Critical 레벨 감지 - Being_편중식사 적용`);
      return 'Being_편중식사'; // 2단계: 심각한 불균형
    case 'warning':
      console.log(`🎭 [DEBUG] Warning 레벨 감지 - Being_매우편중 적용`);
      return 'Being_매우편중'; // 1단계: 약간 불균형
    case 'good':
    default:
      // 기본 애니메이션 유지 (AsyncStorage에서 읽기)
      const currentAnimation = await AsyncStorage.getItem('selected_animation');
      console.log(`🎭 [DEBUG] Good 레벨 - 기본 애니메이션 유지: ${currentAnimation || 'Hi_normal'}`);
      return currentAnimation || 'Hi_normal';
  }
};

// 영양 균형 상태 저장
export const saveNutritionStatus = async (status: 'good' | 'warning' | 'critical'): Promise<void> => {
  try {
    await AsyncStorage.setItem('nutrition_balance_status', status);
    console.log(`영양 균형 상태 저장: ${status}`);
  } catch (error) {
    console.error('영양 균형 상태 저장 실패:', error);
  }
};

// 영양 균형 상태 로드
export const loadNutritionStatus = async (): Promise<'good' | 'warning' | 'critical'> => {
  try {
    const status = await AsyncStorage.getItem('nutrition_balance_status');
    return (status as 'good' | 'warning' | 'critical') || 'good';
  } catch (error) {
    console.error('영양 균형 상태 로드 실패:', error);
    return 'good';
  }
};