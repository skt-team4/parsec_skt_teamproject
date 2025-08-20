import React, { useState, useEffect } from 'react';
import {
  Dimensions,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { BarChart, LineChart, PieChart } from 'react-native-chart-kit';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import { 
  generateDailyNutritionReport, 
  type DailyNutritionReport,
  getNutritionBalanceLevel 
} from '../../utils/nutritionAnalyzer';

const { width } = Dimensions.get('window');

interface FoodData {
  id: string;
  foodName: string;
  mealType: 'breakfast' | 'lunch' | 'dinner';
  imageUri: string;
  timestamp: string;
  date?: string;
  calories?: number;
  nutritionData?: {
    calories: number;
    totalNutrients: {
      [key: string]: {
        label: string;
        quantity: number;
        unit: string;
      };
    };
    nutri_score?: {
      category: string;
      score: number;
    };
  };
}

interface DailyNutrition {
  date: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  fiber: number;
  sodium: number;
  sugar: number;
  mealCount: {
    breakfast: number;
    lunch: number;
    dinner: number;
  };
}

export default function NutritionScreen() {
  const [selectedTab, setSelectedTab] = useState<'daily' | 'weekly' | 'monthly'>('daily');
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [dailyData, setDailyData] = useState<DailyNutrition | null>(null);
  const [weeklyData, setWeeklyData] = useState<DailyNutrition[]>([]);
  const [monthlyData, setMonthlyData] = useState<DailyNutrition[]>([]);
  const [nutritionReport, setNutritionReport] = useState<DailyNutritionReport | null>(null);

  useEffect(() => {
    loadNutritionData();
    loadNutritionReport();
  }, [selectedDate, selectedTab]);

  const loadNutritionData = async () => {
    setIsLoading(true);
    try {
      const data = await AsyncStorage.getItem('foodHistory');
      if (data) {
        const history: FoodData[] = JSON.parse(data);
        
        if (selectedTab === 'daily') {
          calculateDailyNutrition(history);
        } else if (selectedTab === 'weekly') {
          calculateWeeklyNutrition(history);
        } else {
          calculateMonthlyNutrition(history);
        }
      }
    } catch (error) {
      console.error('영양소 데이터 로드 실패:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const calculateDailyNutrition = (history: FoodData[]) => {
    const today = selectedDate.toISOString().split('T')[0];
    const todayData = history.filter(item => {
      const itemDate = item.date || item.timestamp?.split('T')[0];
      return itemDate === today;
    });

    const nutrition: DailyNutrition = {
      date: today,
      calories: 0,
      protein: 0,
      carbs: 0,
      fat: 0,
      fiber: 0,
      sodium: 0,
      sugar: 0,
      mealCount: {
        breakfast: 0,
        lunch: 0,
        dinner: 0,
      }
    };

    todayData.forEach(item => {
      nutrition.calories += item.calories || 0;
      
      if (item.nutritionData?.totalNutrients) {
        const nutrients = item.nutritionData.totalNutrients;
        nutrition.protein += nutrients.PROCNT?.quantity || 0;
        nutrition.carbs += nutrients.CHOCDF?.quantity || 0;
        nutrition.fat += nutrients.FAT?.quantity || 0;
        nutrition.fiber += nutrients.FIBTG?.quantity || 0;
        // 나트륨 단위 체크 (g이면 mg로 변환)
        const sodiumValue = nutrients.NA?.quantity || 0;
        nutrition.sodium += sodiumValue < 10 ? sodiumValue * 1000 : sodiumValue;
        nutrition.sugar += nutrients.SUGAR?.quantity || 0;
      }
      
      if (item.mealType) {
        nutrition.mealCount[item.mealType]++;
      }
    });

    setDailyData(nutrition);
  };

  const loadNutritionReport = async () => {
    try {
      const report = await generateDailyNutritionReport(selectedDate);
      setNutritionReport(report);
      console.log('🥗 영양 리포트 로드:', report.balance);
    } catch (error) {
      console.error('영양 리포트 로드 실패:', error);
    }
  };

  const calculateWeeklyNutrition = (history: FoodData[]) => {
    const weekData: DailyNutrition[] = [];
    
    for (let i = 6; i >= 0; i--) {
      const date = new Date(selectedDate);
      date.setDate(date.getDate() - i);
      const dateStr = date.toISOString().split('T')[0];
      
      const dayData = history.filter(item => {
        const itemDate = item.date || item.timestamp?.split('T')[0];
        return itemDate === dateStr;
      });

      const nutrition: DailyNutrition = {
        date: dateStr,
        calories: 0,
        protein: 0,
        carbs: 0,
        fat: 0,
        fiber: 0,
        sodium: 0,
        sugar: 0,
        mealCount: {
          breakfast: 0,
          lunch: 0,
          dinner: 0,
        }
      };

      dayData.forEach(item => {
        nutrition.calories += item.calories || 0;
        
        if (item.nutritionData?.totalNutrients) {
          const nutrients = item.nutritionData.totalNutrients;
          nutrition.protein += nutrients.PROCNT?.quantity || 0;
          nutrition.carbs += nutrients.CHOCDF?.quantity || 0;
          nutrition.fat += nutrients.FAT?.quantity || 0;
          nutrition.fiber += nutrients.FIBTG?.quantity || 0;
          // 나트륨 단위 체크 (g이면 mg로 변환)
          const sodiumValue = nutrients.NA?.quantity || 0;
          nutrition.sodium += sodiumValue < 10 ? sodiumValue * 1000 : sodiumValue;
          nutrition.sugar += nutrients.SUGAR?.quantity || 0;
        }
        
        if (item.mealType) {
          nutrition.mealCount[item.mealType]++;
        }
      });

      weekData.push(nutrition);
    }

    setWeeklyData(weekData);
  };

  const calculateMonthlyNutrition = (history: FoodData[]) => {
    const monthData: DailyNutrition[] = [];
    
    for (let i = 29; i >= 0; i--) {
      const date = new Date(selectedDate);
      date.setDate(date.getDate() - i);
      const dateStr = date.toISOString().split('T')[0];
      
      const dayData = history.filter(item => {
        const itemDate = item.date || item.timestamp?.split('T')[0];
        return itemDate === dateStr;
      });

      const nutrition: DailyNutrition = {
        date: dateStr,
        calories: 0,
        protein: 0,
        carbs: 0,
        fat: 0,
        fiber: 0,
        sodium: 0,
        sugar: 0,
        mealCount: {
          breakfast: 0,
          lunch: 0,
          dinner: 0,
        }
      };

      dayData.forEach(item => {
        nutrition.calories += item.calories || 0;
        
        if (item.nutritionData?.totalNutrients) {
          const nutrients = item.nutritionData.totalNutrients;
          nutrition.protein += nutrients.PROCNT?.quantity || 0;
          nutrition.carbs += nutrients.CHOCDF?.quantity || 0;
          nutrition.fat += nutrients.FAT?.quantity || 0;
          nutrition.fiber += nutrients.FIBTG?.quantity || 0;
          // 나트륨 단위 체크 (g이면 mg로 변환)
          const sodiumValue = nutrients.NA?.quantity || 0;
          nutrition.sodium += sodiumValue < 10 ? sodiumValue * 1000 : sodiumValue;
          nutrition.sugar += nutrients.SUGAR?.quantity || 0;
        }
      });

      monthData.push(nutrition);
    }

    setMonthlyData(monthData);
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadNutritionData();
    await loadNutritionReport();
    setRefreshing(false);
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return `${date.getMonth() + 1}/${date.getDate()}`;
  };

  const getDayName = (dateStr: string) => {
    const date = new Date(dateStr);
    const days = ['일', '월', '화', '수', '목', '금', '토'];
    return days[date.getDay()];
  };

  // 차트 설정
  const chartConfig = {
    backgroundGradientFrom: '#ffffff',
    backgroundGradientTo: '#ffffff',
    color: (opacity = 1) => `rgba(255, 191, 0, ${opacity})`,
    strokeWidth: 2,
    barPercentage: 0.7,
    useShadowColorFromDataset: false,
    decimalPlaces: 0,
  };

  // 일일 영양소 도넛 차트 데이터
  const getDailyMacroChartData = () => {
    if (!dailyData) return [];
    
    const total = dailyData.protein + dailyData.carbs + dailyData.fat;
    if (total === 0) return [];

    return [
      {
        name: '단백질',
        population: Math.round((dailyData.protein / total) * 100),
        color: '#FF6B6B',
        legendFontColor: '#333',
      },
      {
        name: '탄수화물',
        population: Math.round((dailyData.carbs / total) * 100),
        color: '#4ECDC4',
        legendFontColor: '#333',
      },
      {
        name: '지방',
        population: Math.round((dailyData.fat / total) * 100),
        color: '#45B7D1',
        legendFontColor: '#333',
      }
    ];
  };

  // 주간 칼로리 라인 차트 데이터
  const getWeeklyCaloriesData = () => {
    return {
      labels: weeklyData.map(d => getDayName(d.date)),
      datasets: [
        {
          data: weeklyData.map(d => d.calories),
          color: (opacity = 1) => `rgba(255, 191, 0, ${opacity})`,
          strokeWidth: 3,
        }
      ],
    };
  };

  // 식사 분포 바 차트 데이터
  const getMealDistributionData = () => {
    if (!dailyData) return { labels: [], datasets: [{ data: [0, 0, 0] }] };
    
    return {
      labels: ['아침', '점심', '저녁'],
      datasets: [{
        data: [
          dailyData.mealCount.breakfast,
          dailyData.mealCount.lunch,
          dailyData.mealCount.dinner
        ]
      }]
    };
  };

  if (isLoading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#FFBF00" />
          <Text style={styles.loadingText}>영양소 데이터를 분석하는 중...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* 헤더 */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>영양소 리포트</Text>
        <Text style={styles.headerSubtitle}>실제 섭취 기반 영양 분석</Text>
      </View>

      {/* 탭 선택 */}
      <View style={styles.tabContainer}>
        <TouchableOpacity 
          style={[styles.tab, selectedTab === 'daily' && styles.activeTab]}
          onPress={() => setSelectedTab('daily')}
        >
          <Text style={[styles.tabText, selectedTab === 'daily' && styles.activeTabText]}>
            📊 일일
          </Text>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={[styles.tab, selectedTab === 'weekly' && styles.activeTab]}
          onPress={() => setSelectedTab('weekly')}
        >
          <Text style={[styles.tabText, selectedTab === 'weekly' && styles.activeTabText]}>
            📈 주간
          </Text>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={[styles.tab, selectedTab === 'monthly' && styles.activeTab]}
          onPress={() => setSelectedTab('monthly')}
        >
          <Text style={[styles.tabText, selectedTab === 'monthly' && styles.activeTabText]}>
            📅 월간
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView 
        style={styles.content} 
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {selectedTab === 'daily' && dailyData && (
          <View>
            {/* 영양 균형 상태 */}
            {nutritionReport && (
              <View style={styles.chartCard}>
                <Text style={styles.chartTitle}>⚖️ 영양 균형 상태</Text>
                <View style={styles.balanceContainer}>
                  <View style={[styles.balanceScore, { 
                    backgroundColor: nutritionReport.balance.level === 'good' ? '#4CAF50' : 
                                   nutritionReport.balance.level === 'warning' ? '#FF9800' : '#F44336'
                  }]}>
                    <Text style={styles.balanceScoreText}>{nutritionReport.balance.score}점</Text>
                  </View>
                  <View style={styles.balanceDetails}>
                    <Text style={[styles.balanceLevel, {
                      color: nutritionReport.balance.level === 'good' ? '#4CAF50' : 
                             nutritionReport.balance.level === 'warning' ? '#FF9800' : '#F44336'
                    }]}>
                      {nutritionReport.balance.level === 'good' ? '✅ 균형잡힌 식사' :
                       nutritionReport.balance.level === 'warning' ? '⚠️ 영양 불균형 주의' : '🚨 심각한 영양 불균형'}
                    </Text>
                    {nutritionReport.balance.issues.length > 0 && (
                      <View style={styles.issuesList}>
                        {nutritionReport.balance.issues.slice(0, 3).map((issue, index) => (
                          <Text key={index} style={styles.issueText}>• {issue}</Text>
                        ))}
                      </View>
                    )}
                  </View>
                </View>
              </View>
            )}

            {/* 오늘의 칼로리 */}
            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>🔥 오늘의 칼로리</Text>
              <View style={styles.calorieContainer}>
                <Text style={styles.calorieNumber}>{Math.round(dailyData.calories)}</Text>
                <Text style={styles.calorieUnit}>kcal</Text>
              </View>
              <Text style={styles.calorieTarget}>권장: 2,000 kcal</Text>
            </View>

            {/* 3대 영양소 비율 */}
            {getDailyMacroChartData().length > 0 && (
              <View style={styles.chartCard}>
                <Text style={styles.chartTitle}>🍎 3대 영양소 비율</Text>
                <PieChart
                  data={getDailyMacroChartData()}
                  width={width - 48}
                  height={200}
                  chartConfig={chartConfig}
                  accessor="population"
                  backgroundColor="transparent"
                  paddingLeft="15"
                  center={[10, 0]}
                  hasLegend={true}
                />
                <View style={styles.macroDetails}>
                  <View style={styles.macroItem}>
                    <View style={[styles.macroDot, { backgroundColor: '#FF6B6B' }]} />
                    <Text style={styles.macroLabel}>단백질</Text>
                    <Text style={styles.macroValue}>{dailyData.protein.toFixed(1)}g</Text>
                  </View>
                  <View style={styles.macroItem}>
                    <View style={[styles.macroDot, { backgroundColor: '#4ECDC4' }]} />
                    <Text style={styles.macroLabel}>탄수화물</Text>
                    <Text style={styles.macroValue}>{dailyData.carbs.toFixed(1)}g</Text>
                  </View>
                  <View style={styles.macroItem}>
                    <View style={[styles.macroDot, { backgroundColor: '#45B7D1' }]} />
                    <Text style={styles.macroLabel}>지방</Text>
                    <Text style={styles.macroValue}>{dailyData.fat.toFixed(1)}g</Text>
                  </View>
                </View>
              </View>
            )}

            {/* 식사 분포 */}
            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>🍽️ 오늘의 식사 기록</Text>
              <BarChart
                data={getMealDistributionData()}
                width={width - 48}
                height={200}
                chartConfig={{
                  ...chartConfig,
                  color: (opacity = 1) => `rgba(76, 175, 80, ${opacity})`,
                }}
                style={styles.barChart}
                showValuesOnTopOfBars={true}
                fromZero={true}
              />
            </View>

            {/* 기타 영양소 */}
            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>💊 기타 영양소</Text>
              <View style={styles.nutrientGrid}>
                <View style={styles.nutrientItem}>
                  <Text style={styles.nutrientLabel}>식이섬유</Text>
                  <Text style={styles.nutrientValue}>{dailyData.fiber.toFixed(1)}g</Text>
                </View>
                <View style={styles.nutrientItem}>
                  <Text style={styles.nutrientLabel}>나트륨</Text>
                  <Text style={styles.nutrientValue}>{Math.round(dailyData.sodium)}mg</Text>
                </View>
                <View style={styles.nutrientItem}>
                  <Text style={styles.nutrientLabel}>당류</Text>
                  <Text style={styles.nutrientValue}>{dailyData.sugar.toFixed(1)}g</Text>
                </View>
              </View>
            </View>
          </View>
        )}

        {selectedTab === 'weekly' && weeklyData.length > 0 && (
          <View>
            {/* 주간 칼로리 트렌드 */}
            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>📈 주간 칼로리 트렌드</Text>
              <LineChart
                data={getWeeklyCaloriesData()}
                width={width - 48}
                height={220}
                chartConfig={{
                  ...chartConfig,
                  color: (opacity = 1) => `rgba(255, 191, 0, ${opacity})`,
                }}
                bezier
                style={styles.lineChart}
                withDots={true}
                withShadow={false}
              />
              <Text style={styles.chartDescription}>
                주간 평균: {Math.round(weeklyData.reduce((sum, d) => sum + d.calories, 0) / 7)} kcal
              </Text>
            </View>

            {/* 주간 3대 영양소 */}
            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>⚖️ 주간 3대 영양소 섭취량</Text>
              <BarChart
                data={{
                  labels: weeklyData.map(d => getDayName(d.date)),
                  datasets: [
                    {
                      data: weeklyData.map(d => d.protein),
                    }
                  ]
                }}
                width={width - 48}
                height={200}
                chartConfig={{
                  ...chartConfig,
                  color: (opacity = 1) => `rgba(255, 107, 107, ${opacity})`,
                }}
                style={styles.barChart}
                showValuesOnTopOfBars={false}
                fromZero={true}
              />
              <View style={styles.weeklyStats}>
                <Text style={styles.weeklyStatText}>
                  평균 단백질: {(weeklyData.reduce((sum, d) => sum + d.protein, 0) / 7).toFixed(1)}g
                </Text>
                <Text style={styles.weeklyStatText}>
                  평균 탄수화물: {(weeklyData.reduce((sum, d) => sum + d.carbs, 0) / 7).toFixed(1)}g
                </Text>
                <Text style={styles.weeklyStatText}>
                  평균 지방: {(weeklyData.reduce((sum, d) => sum + d.fat, 0) / 7).toFixed(1)}g
                </Text>
              </View>
            </View>
          </View>
        )}

        {selectedTab === 'monthly' && monthlyData.length > 0 && (
          <View>
            {/* 월간 칼로리 트렌드 */}
            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>📅 월간 칼로리 트렌드</Text>
              <LineChart
                data={{
                  labels: monthlyData.filter((_, i) => i % 5 === 0).map(d => formatDate(d.date)),
                  datasets: [{
                    data: monthlyData.map(d => d.calories),
                    color: (opacity = 1) => `rgba(255, 191, 0, ${opacity})`,
                    strokeWidth: 2,
                  }]
                }}
                width={width - 48}
                height={220}
                chartConfig={chartConfig}
                bezier
                style={styles.lineChart}
                withDots={false}
                withShadow={false}
              />
              <Text style={styles.chartDescription}>
                월간 평균: {Math.round(monthlyData.reduce((sum, d) => sum + d.calories, 0) / 30)} kcal
              </Text>
            </View>

            {/* 월간 통계 */}
            <View style={styles.summaryCard}>
              <Text style={styles.summaryTitle}>📊 월간 요약</Text>
              <View style={styles.summaryGrid}>
                <View style={styles.summaryItem}>
                  <Text style={styles.summaryNumber}>
                    {monthlyData.filter(d => d.calories > 0).length}
                  </Text>
                  <Text style={styles.summaryLabel}>기록일수</Text>
                </View>
                <View style={styles.summaryItem}>
                  <Text style={styles.summaryNumber}>
                    {Math.round(monthlyData.reduce((sum, d) => sum + d.calories, 0))}
                  </Text>
                  <Text style={styles.summaryLabel}>총 칼로리</Text>
                </View>
                <View style={styles.summaryItem}>
                  <Text style={styles.summaryNumber}>
                    {Math.max(...monthlyData.map(d => d.calories))}
                  </Text>
                  <Text style={styles.summaryLabel}>최고 칼로리</Text>
                </View>
              </View>
            </View>
          </View>
        )}

        {/* 데이터가 없을 때 */}
        {((selectedTab === 'daily' && !dailyData) || 
          (selectedTab === 'weekly' && weeklyData.length === 0) ||
          (selectedTab === 'monthly' && monthlyData.length === 0)) && (
          <View style={styles.emptyContainer}>
            <Ionicons name="nutrition-outline" size={64} color="#999" />
            <Text style={styles.emptyText}>아직 기록된 데이터가 없습니다</Text>
            <Text style={styles.emptySubtext}>음식을 촬영하고 기록을 시작해보세요!</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  header: {
    paddingHorizontal: 24,
    paddingTop: 40,
    paddingBottom: 24,
    backgroundColor: '#fff',
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#FFBF00',
    marginBottom: 4,
  },
  headerSubtitle: {
    fontSize: 16,
    color: '#666',
  },
  tabContainer: {
    flexDirection: 'row',
    backgroundColor: '#fff',
    paddingHorizontal: 24,
    paddingBottom: 16,
  },
  tab: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 25,
    alignItems: 'center',
    marginHorizontal: 4,
    backgroundColor: '#f5f5f5',
  },
  activeTab: {
    backgroundColor: '#FFBF00',
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#666',
  },
  activeTabText: {
    color: '#fff',
  },
  content: {
    flex: 1,
    paddingHorizontal: 24,
  },
  chartCard: {
    backgroundColor: '#fff',
    borderRadius: 20,
    padding: 20,
    marginTop: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 5,
  },
  chartTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 16,
    textAlign: 'center',
  },
  calorieContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'baseline',
    marginVertical: 20,
  },
  calorieNumber: {
    fontSize: 48,
    fontWeight: 'bold',
    color: '#FFBF00',
  },
  calorieUnit: {
    fontSize: 20,
    color: '#666',
    marginLeft: 8,
  },
  calorieTarget: {
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
  },
  macroDetails: {
    marginTop: 16,
  },
  macroItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  macroDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: 12,
  },
  macroLabel: {
    flex: 1,
    fontSize: 14,
    color: '#666',
  },
  macroValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
  },
  lineChart: {
    marginVertical: 8,
    borderRadius: 16,
  },
  barChart: {
    marginVertical: 8,
    borderRadius: 16,
  },
  chartDescription: {
    textAlign: 'center',
    fontSize: 14,
    color: '#666',
    marginTop: 8,
    fontStyle: 'italic',
  },
  nutrientGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  nutrientItem: {
    width: '30%',
    backgroundColor: '#f8f9fa',
    borderRadius: 12,
    padding: 12,
    alignItems: 'center',
    marginBottom: 8,
  },
  nutrientLabel: {
    fontSize: 12,
    color: '#666',
    marginBottom: 4,
  },
  nutrientValue: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  weeklyStats: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0',
  },
  weeklyStatText: {
    fontSize: 14,
    color: '#666',
    marginBottom: 4,
  },
  summaryCard: {
    backgroundColor: '#fff',
    borderRadius: 20,
    padding: 20,
    marginTop: 16,
    marginBottom: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 5,
  },
  summaryTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 16,
    textAlign: 'center',
  },
  summaryGrid: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  summaryItem: {
    alignItems: 'center',
  },
  summaryNumber: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#FFBF00',
    marginBottom: 4,
  },
  summaryLabel: {
    fontSize: 12,
    color: '#666',
    textAlign: 'center',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: '#666',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#666',
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#999',
    marginTop: 8,
    textAlign: 'center',
  },
  balanceContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
  },
  balanceScore: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 20,
  },
  balanceScoreText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  balanceDetails: {
    flex: 1,
  },
  balanceLevel: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  issuesList: {
    marginTop: 4,
  },
  issueText: {
    fontSize: 12,
    color: '#666',
    marginBottom: 2,
  },
});