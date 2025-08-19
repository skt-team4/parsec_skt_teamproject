import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  SectionList,
  Image,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  RefreshControl,
  Alert,
  ActivityIndicator,
  Modal,
  ScrollView,
  Dimensions,
  Platform,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';

const { width, height } = Dimensions.get('window');

interface FoodData {
  id: string;
  foodName: string;
  mealType: 'breakfast' | 'lunch' | 'dinner';
  imageUri: string;
  timestamp: string;
  date?: string; // 날짜 필드 추가
  calories?: number;
  confidence?: number;
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

interface GroupedData {
  title: string;
  data: FoodData[];
}

export default function FoodHistoryScreen() {
  const [foodHistory, setFoodHistory] = useState<FoodData[]>([]);
  const [serverHistory, setServerHistory] = useState<any[]>([]);
  const [groupedHistory, setGroupedHistory] = useState<GroupedData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedTab, setSelectedTab] = useState<'local' | 'server'>('local');
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  const [selectedItem, setSelectedItem] = useState<any>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  useEffect(() => {
    loadHistory();
  }, [selectedTab]);

  const loadHistory = async () => {
    setIsLoading(true);
    try {
      if (selectedTab === 'local') {
        // AsyncStorage에서 로컬 기록 불러오기
        const data = await AsyncStorage.getItem('foodHistory');
        if (data) {
          const history = JSON.parse(data);
          setFoodHistory(history);
          groupDataByDate(history);
        }
      } else {
        // 서버에서 기록 불러오기
        const response = await fetch('http://localhost:5004/api/get-history?userId=guest&limit=100');
        const result = await response.json();
        if (result.status === 'success') {
          setServerHistory(result.records);
          groupDataByDate(result.records);
        }
      }
    } catch (error) {
      console.error('기록 불러오기 실패:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // 날짜별로 데이터 그룹화 및 식사 시간별 정렬
  const groupDataByDate = (data: any[]) => {
    const mealOrder = { breakfast: 0, lunch: 1, dinner: 2 };
    
    // 날짜별로 그룹화
    const grouped: { [date: string]: any[] } = {};
    
    data.forEach(item => {
      const date = item.date || item.timestamp?.split('T')[0] || new Date(item.timestamp).toISOString().split('T')[0];
      if (!grouped[date]) {
        grouped[date] = [];
      }
      grouped[date].push(item);
    });
    
    // 각 날짜 내에서 식사 시간별로 정렬
    Object.keys(grouped).forEach(date => {
      grouped[date].sort((a, b) => {
        const orderA = mealOrder[a.mealType as keyof typeof mealOrder] ?? 3;
        const orderB = mealOrder[b.mealType as keyof typeof mealOrder] ?? 3;
        return orderA - orderB;
      });
    });
    
    // SectionList 형식으로 변환
    const sections: GroupedData[] = Object.keys(grouped)
      .sort((a, b) => b.localeCompare(a)) // 최신 날짜가 먼저 오도록
      .map(date => ({
        title: formatDateHeader(date),
        data: grouped[date]
      }));
    
    setGroupedHistory(sections);
  };

  const formatDateHeader = (dateStr: string) => {
    const date = new Date(dateStr + 'T00:00:00');
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    const dateOnly = (d: Date) => `${d.getFullYear()}-${(d.getMonth() + 1).toString().padStart(2, '0')}-${d.getDate().toString().padStart(2, '0')}`;
    
    if (dateOnly(date) === dateOnly(today)) {
      return '오늘';
    } else if (dateOnly(date) === dateOnly(yesterday)) {
      return '어제';
    }
    
    const weekDays = ['일', '월', '화', '수', '목', '금', '토'];
    return `${date.getMonth() + 1}월 ${date.getDate()}일 (${weekDays[date.getDay()]})`;
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadHistory();
    setRefreshing(false);
  };

  const getMealTypeEmoji = (mealType: string) => {
    switch (mealType) {
      case 'breakfast': return '🌅';
      case 'lunch': return '☀️';
      case 'dinner': return '🌙';
      default: return '🍽️';
    }
  };

  const getMealTypeKorean = (mealType: string) => {
    switch (mealType) {
      case 'breakfast': return '아침';
      case 'lunch': return '점심';
      case 'dinner': return '저녁';
      default: return '식사';
    }
  };

  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) {
      return `오늘 ${date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}`;
    } else if (date.toDateString() === yesterday.toDateString()) {
      return `어제 ${date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}`;
    }
    return date.toLocaleDateString('ko-KR', { 
      month: 'long', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const deleteItem = async (id: string) => {
    // 웹과 모바일에서 모두 작동하도록 수정
    const confirmDelete = () => {
      if (Platform.OS === 'web') {
        return window.confirm('이 기록을 삭제하시겠습니까?');
      } else {
        return new Promise<boolean>((resolve) => {
          Alert.alert(
            '기록 삭제',
            '이 기록을 삭제하시겠습니까?',
            [
              { text: '취소', style: 'cancel', onPress: () => resolve(false) },
              { text: '삭제', style: 'destructive', onPress: () => resolve(true) }
            ]
          );
        });
      }
    };

    const shouldDelete = Platform.OS === 'web' ? confirmDelete() : await confirmDelete();
    
    if (shouldDelete) {
      try {
        if (selectedTab === 'local') {
          const newHistory = foodHistory.filter(item => item.id !== id);
          setFoodHistory(newHistory);
          await AsyncStorage.setItem('foodHistory', JSON.stringify(newHistory));
          // 다시 그룹화
          groupDataByDate(newHistory);
        } else {
          const response = await fetch(`http://localhost:5004/api/delete-record/${id}`, {
            method: 'DELETE'
          });
          if (response.ok) {
            await loadHistory();
          }
        }
        
        // 삭제 성공 메시지
        if (Platform.OS === 'web') {
          console.log('기록이 삭제되었습니다.');
        }
      } catch (error) {
        console.error('삭제 실패:', error);
        if (Platform.OS === 'web') {
          window.alert('삭제에 실패했습니다.');
        } else {
          Alert.alert('오류', '삭제에 실패했습니다.');
        }
      }
    }
  };

  const toggleExpanded = (id: string) => {
    const newExpanded = new Set(expandedItems);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedItems(newExpanded);
  };

  const openDetailModal = (item: any) => {
    setSelectedItem(item);
    setShowDetailModal(true);
  };

  const getNutrientValue = (nutrients: any, key: string) => {
    if (!nutrients || !nutrients[key]) return null;
    return nutrients[key];
  };

  const renderLocalItem = ({ item }: { item: FoodData }) => {
    const isExpanded = expandedItems.has(item.id);
    
    return (
      <View style={styles.card}>
        <TouchableOpacity onPress={() => toggleExpanded(item.id)}>
          <View style={styles.cardHeader}>
            <View style={styles.mealTypeContainer}>
              <Text style={styles.mealEmoji}>{getMealTypeEmoji(item.mealType)}</Text>
              <Text style={styles.mealType}>{getMealTypeKorean(item.mealType)}</Text>
            </View>
            <View style={styles.headerRight}>
              <Text style={styles.timestamp}>{formatDate(item.timestamp)}</Text>
              <Ionicons 
                name={isExpanded ? "chevron-up" : "chevron-down"} 
                size={20} 
                color="#666" 
                style={{ marginLeft: 8 }}
              />
            </View>
          </View>

          <View style={styles.cardContent}>
            {item.imageUri && (
              <TouchableOpacity onPress={() => openDetailModal(item)}>
                <Image source={{ uri: item.imageUri }} style={styles.foodImage} />
                <View style={styles.imageOverlay}>
                  <Ionicons name="expand-outline" size={20} color="white" />
                </View>
              </TouchableOpacity>
            )}
            <View style={styles.infoContainer}>
              <Text style={styles.foodName}>{item.foodName}</Text>
              <Text style={styles.calories}>{Math.round(item.calories || 0)} kcal</Text>
              
              {item.nutritionData?.nutri_score && (
                <View style={styles.nutriScoreContainer}>
                  <Text style={styles.nutriScoreLabel}>영양등급</Text>
                  <Text style={[styles.nutriScore, { 
                    backgroundColor: item.nutritionData.nutri_score.category === 'A' ? '#28a745' :
                                    item.nutritionData.nutri_score.category === 'B' ? '#6f42c1' :
                                    item.nutritionData.nutri_score.category === 'C' ? '#fd7e14' :
                                    item.nutritionData.nutri_score.category === 'D' ? '#dc3545' : '#6c757d'
                  }]}>
                    {item.nutritionData.nutri_score.category}
                  </Text>
                </View>
              )}

              {!isExpanded && item.nutritionData?.totalNutrients && (
                <View style={styles.nutritionInfo}>
                  <Text style={styles.nutrientText}>
                    단백질 {item.nutritionData.totalNutrients.PROCNT?.quantity.toFixed(1) || '0'}g • 
                    탄수화물 {item.nutritionData.totalNutrients.CHOCDF?.quantity.toFixed(1) || '0'}g • 
                    지방 {item.nutritionData.totalNutrients.FAT?.quantity.toFixed(1) || '0'}g
                  </Text>
                </View>
              )}
            </View>
          </View>
        </TouchableOpacity>

        {isExpanded && item.nutritionData?.totalNutrients && (
          <View style={styles.expandedContent}>
            <Text style={styles.expandedTitle}>📊 상세 영양 정보</Text>
            <View style={styles.nutritionGrid}>
              {Object.entries(item.nutritionData.totalNutrients).map(([key, nutrient]) => (
                <View key={key} style={styles.nutritionGridItem}>
                  <Text style={styles.nutritionGridLabel}>{nutrient.label}</Text>
                  <Text style={styles.nutritionGridValue}>
                    {nutrient.quantity < 1 
                      ? nutrient.quantity.toFixed(2) 
                      : nutrient.quantity.toFixed(1)
                    }{nutrient.unit}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        )}

        <View style={styles.cardActions}>
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={() => openDetailModal(item)}
          >
            <Ionicons name="eye-outline" size={20} color="#007AFF" />
            <Text style={styles.actionButtonText}>상세보기</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={() => deleteItem(item.id)}
          >
            <Ionicons name="trash-outline" size={20} color="#dc3545" />
            <Text style={[styles.actionButtonText, { color: '#dc3545' }]}>삭제</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  const renderServerItem = ({ item }: { item: any }) => {
    const isExpanded = expandedItems.has(item.id);
    
    return (
      <View style={styles.card}>
        <TouchableOpacity onPress={() => toggleExpanded(item.id)}>
          <View style={styles.cardHeader}>
            <View style={styles.mealTypeContainer}>
              <Text style={styles.mealEmoji}>{getMealTypeEmoji(item.mealType)}</Text>
              <Text style={styles.mealType}>{getMealTypeKorean(item.mealType)}</Text>
            </View>
            <View style={styles.headerRight}>
              <Text style={styles.timestamp}>{formatDate(item.timestamp)}</Text>
              <Ionicons 
                name={isExpanded ? "chevron-up" : "chevron-down"} 
                size={20} 
                color="#666" 
                style={{ marginLeft: 8 }}
              />
            </View>
          </View>

          <View style={styles.cardContent}>
            {item.imageUri && (
              <TouchableOpacity onPress={() => openDetailModal(item)}>
                <Image source={{ uri: item.imageUri }} style={styles.foodImage} />
                <View style={styles.imageOverlay}>
                  <Ionicons name="expand-outline" size={20} color="white" />
                </View>
              </TouchableOpacity>
            )}
            <View style={styles.infoContainer}>
              <Text style={styles.foodName}>{item.foodName}</Text>
              <Text style={styles.calories}>{Math.round(item.calories || 0)} kcal</Text>
              
              {item.nutriScore?.category && (
                <View style={styles.nutriScoreContainer}>
                  <Text style={styles.nutriScoreLabel}>영양등급</Text>
                  <Text style={[styles.nutriScore, { 
                    backgroundColor: item.nutriScore.category === 'A' ? '#28a745' :
                                    item.nutriScore.category === 'B' ? '#6f42c1' :
                                    item.nutriScore.category === 'C' ? '#fd7e14' :
                                    item.nutriScore.category === 'D' ? '#dc3545' : '#6c757d'
                  }]}>
                    {item.nutriScore.category}
                  </Text>
                </View>
              )}

              {!isExpanded && item.nutritionInfo?.totalNutrients && (
                <View style={styles.nutritionInfo}>
                  <Text style={styles.nutrientText}>
                    단백질 {item.nutritionInfo.totalNutrients.PROCNT?.quantity.toFixed(1) || '0'}g • 
                    탄수화물 {item.nutritionInfo.totalNutrients.CHOCDF?.quantity.toFixed(1) || '0'}g • 
                    지방 {item.nutritionInfo.totalNutrients.FAT?.quantity.toFixed(1) || '0'}g
                  </Text>
                </View>
              )}
            </View>
          </View>
        </TouchableOpacity>

        {isExpanded && item.nutritionInfo?.totalNutrients && (
          <View style={styles.expandedContent}>
            <Text style={styles.expandedTitle}>📊 상세 영양 정보</Text>
            <View style={styles.nutritionGrid}>
              {Object.entries(item.nutritionInfo.totalNutrients).map(([key, nutrient]) => (
                <View key={key} style={styles.nutritionGridItem}>
                  <Text style={styles.nutritionGridLabel}>{nutrient.label}</Text>
                  <Text style={styles.nutritionGridValue}>
                    {nutrient.quantity < 1 
                      ? nutrient.quantity.toFixed(2) 
                      : nutrient.quantity.toFixed(1)
                    }{nutrient.unit}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        )}

        <View style={styles.cardActions}>
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={() => openDetailModal(item)}
          >
            <Ionicons name="eye-outline" size={20} color="#007AFF" />
            <Text style={styles.actionButtonText}>상세보기</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={() => deleteItem(item.id)}
          >
            <Ionicons name="trash-outline" size={20} color="#dc3545" />
            <Text style={[styles.actionButtonText, { color: '#dc3545' }]}>삭제</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  // 상세보기 모달 컴포넌트
  const DetailModal = () => {
    if (!selectedItem) return null;
    
    const nutrients = selectedItem.nutritionData?.totalNutrients || selectedItem.nutritionInfo?.totalNutrients;
    const nutriScore = selectedItem.nutritionData?.nutri_score || selectedItem.nutriScore;
    
    return (
      <Modal
        visible={showDetailModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowDetailModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <ScrollView showsVerticalScrollIndicator={false}>
              <TouchableOpacity 
                style={styles.modalCloseButton}
                onPress={() => setShowDetailModal(false)}
              >
                <Ionicons name="close-circle" size={32} color="#666" />
              </TouchableOpacity>
              
              <Text style={styles.modalTitle}>{selectedItem.foodName}</Text>
              
              {selectedItem.imageUri && (
                <Image 
                  source={{ uri: selectedItem.imageUri }} 
                  style={styles.modalImage}
                  resizeMode="contain"
                />
              )}
              
              <View style={styles.modalInfoSection}>
                <View style={styles.modalInfoRow}>
                  <Text style={styles.modalInfoLabel}>📅 날짜</Text>
                  <Text style={styles.modalInfoValue}>{formatDate(selectedItem.timestamp)}</Text>
                </View>
                <View style={styles.modalInfoRow}>
                  <Text style={styles.modalInfoLabel}>🍽️ 식사</Text>
                  <Text style={styles.modalInfoValue}>
                    {getMealTypeEmoji(selectedItem.mealType)} {getMealTypeKorean(selectedItem.mealType)}
                  </Text>
                </View>
                <View style={styles.modalInfoRow}>
                  <Text style={styles.modalInfoLabel}>🔥 칼로리</Text>
                  <Text style={styles.modalInfoValue}>{Math.round(selectedItem.calories || 0)} kcal</Text>
                </View>
                {nutriScore && (
                  <View style={styles.modalInfoRow}>
                    <Text style={styles.modalInfoLabel}>📊 영양등급</Text>
                    <Text style={[styles.modalNutriScore, { 
                      backgroundColor: nutriScore.category === 'A' ? '#28a745' :
                                      nutriScore.category === 'B' ? '#6f42c1' :
                                      nutriScore.category === 'C' ? '#fd7e14' :
                                      nutriScore.category === 'D' ? '#dc3545' : '#6c757d'
                    }]}>
                      {nutriScore.category}
                    </Text>
                  </View>
                )}
              </View>
              
              {nutrients && (
                <View style={styles.modalNutritionSection}>
                  <Text style={styles.modalSectionTitle}>영양 성분 상세</Text>
                  {Object.entries(nutrients).map(([key, nutrient]) => (
                    <View key={key} style={styles.modalNutrientRow}>
                      <Text style={styles.modalNutrientLabel}>{nutrient.label}</Text>
                      <Text style={styles.modalNutrientValue}>
                        {nutrient.quantity < 1 
                          ? nutrient.quantity.toFixed(2) 
                          : nutrient.quantity.toFixed(1)
                        } {nutrient.unit}
                      </Text>
                    </View>
                  ))}
                </View>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>음식 분석 기록</Text>
        <Text style={styles.headerSubtitle}>촬영한 음식과 영양 정보를 확인하세요</Text>
      </View>

      <View style={styles.tabContainer}>
        <TouchableOpacity 
          style={[styles.tab, selectedTab === 'local' && styles.activeTab]}
          onPress={() => setSelectedTab('local')}
        >
          <Text style={[styles.tabText, selectedTab === 'local' && styles.activeTabText]}>
            📱 기기 저장
          </Text>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={[styles.tab, selectedTab === 'server' && styles.activeTab]}
          onPress={() => setSelectedTab('server')}
        >
          <Text style={[styles.tabText, selectedTab === 'server' && styles.activeTabText]}>
            ☁️ 서버 저장
          </Text>
        </TouchableOpacity>
      </View>

      {isLoading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
          <Text style={styles.loadingText}>기록을 불러오는 중...</Text>
        </View>
      ) : (
        <SectionList
          sections={groupedHistory}
          renderItem={selectedTab === 'local' ? renderLocalItem : renderServerItem}
          renderSectionHeader={({ section: { title } }) => (
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionHeaderText}>{title}</Text>
            </View>
          )}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContainer}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Ionicons name="restaurant-outline" size={64} color="#999" />
              <Text style={styles.emptyText}>아직 분석한 음식이 없습니다</Text>
              <Text style={styles.emptySubtext}>음식 사진을 촬영하여 영양 정보를 확인해보세요</Text>
            </View>
          }
          stickySectionHeadersEnabled={false}
        />
      )}
      
      <DetailModal />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 40,
    paddingBottom: 12,
    backgroundColor: '#fff',
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#FFBF00',
    marginBottom: 4,
  },
  headerSubtitle: {
    fontSize: 14,
    color: '#666',
  },
  tabContainer: {
    flexDirection: 'row',
    backgroundColor: '#fff',
    paddingHorizontal: 20,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 20,
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
  listContainer: {
    padding: 16,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    overflow: 'hidden',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  mealTypeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  mealEmoji: {
    fontSize: 20,
    marginRight: 6,
  },
  mealType: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
  },
  timestamp: {
    fontSize: 12,
    color: '#999',
  },
  cardContent: {
    flexDirection: 'row',
    padding: 12,
  },
  foodImage: {
    width: 80,
    height: 80,
    borderRadius: 8,
    marginRight: 12,
  },
  infoContainer: {
    flex: 1,
  },
  foodName: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  calories: {
    fontSize: 16,
    color: '#FFBF00',
    fontWeight: '600',
    marginBottom: 8,
  },
  nutriScoreContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  nutriScoreLabel: {
    fontSize: 12,
    color: '#666',
    marginRight: 8,
  },
  nutriScore: {
    fontSize: 14,
    fontWeight: 'bold',
    color: 'white',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
  },
  nutritionInfo: {
    marginTop: 4,
  },
  nutrientText: {
    fontSize: 12,
    color: '#666',
    marginBottom: 2,
  },
  deleteButton: {
    position: 'absolute',
    top: 12,
    right: 12,
    padding: 8,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
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
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  imageOverlay: {
    position: 'absolute',
    bottom: 4,
    right: 4,
    backgroundColor: 'rgba(0,0,0,0.5)',
    borderRadius: 12,
    padding: 4,
  },
  expandedContent: {
    backgroundColor: '#f8f9fa',
    padding: 16,
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0',
  },
  expandedTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 12,
  },
  nutritionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  nutritionGridItem: {
    width: '50%',
    paddingVertical: 8,
    paddingHorizontal: 4,
  },
  nutritionGridLabel: {
    fontSize: 12,
    color: '#666',
    marginBottom: 2,
  },
  nutritionGridValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
  },
  cardActions: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: '#f0f0f0',
    paddingTop: 8,
    paddingHorizontal: 12,
    paddingBottom: 8,
  },
  actionButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
  },
  actionButtonText: {
    fontSize: 14,
    color: '#007AFF',
    marginLeft: 4,
    fontWeight: '500',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalContent: {
    backgroundColor: 'white',
    borderRadius: 20,
    width: width * 0.9,
    maxHeight: height * 0.85,
    padding: 20,
  },
  modalCloseButton: {
    position: 'absolute',
    top: 10,
    right: 10,
    zIndex: 1,
  },
  modalTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    textAlign: 'center',
    marginBottom: 16,
    marginTop: 20,
  },
  modalImage: {
    width: '100%',
    height: 200,
    borderRadius: 12,
    marginBottom: 20,
  },
  modalInfoSection: {
    backgroundColor: '#f8f9fa',
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
  },
  modalInfoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  modalInfoLabel: {
    fontSize: 14,
    color: '#666',
  },
  modalInfoValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
  },
  modalNutriScore: {
    fontSize: 14,
    fontWeight: 'bold',
    color: 'white',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 10,
  },
  modalNutritionSection: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  modalSectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: 12,
  },
  modalNutrientRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  modalNutrientLabel: {
    fontSize: 14,
    color: '#666',
    flex: 1,
  },
  modalNutrientValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
  },
  sectionHeader: {
    backgroundColor: '#f8f9fa',
    paddingVertical: 8,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0',
  },
  sectionHeaderText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
});