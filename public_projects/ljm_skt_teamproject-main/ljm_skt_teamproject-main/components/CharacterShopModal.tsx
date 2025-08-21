// CharacterShopModal.tsx - 동작 + 재료 조합 시스템 (적용 기능 포함)
import { Image } from 'expo-image';
import React, { useEffect, useState } from 'react';
import {
  Alert,
  Dimensions,
  Modal,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  ActivityIndicator,
  Image as RNImage,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getRicePul, spendRicePul } from '../utils/ricePulManager';
import {
  ACTIONS,
  INGREDIENTS,
  SPECIAL_PACKS,
  COMBO_ANIMATIONS,
  AnimationItem,
  SpecialPack,
  calculateComboPrice,
  isComboUnlocked,
  debugShopState,
  ERROR_MESSAGES,
  SUCCESS_MESSAGES,
} from '../config/animationShop.config';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

interface CharacterShopModalProps {
  visible: boolean;
  onClose: () => void;
  currentGifIndex: number;
  onGifChange: (index: number) => void;
  isAnimationEnabled: boolean;
}

type TabType = 'actions' | 'ingredients' | 'combos' | 'packs' | 'collection';

const CharacterShopModal: React.FC<CharacterShopModalProps> = ({
  visible,
  onClose,
  currentGifIndex,
  onGifChange,
  isAnimationEnabled,
}) => {
  // State
  const [activeTab, setActiveTab] = useState<TabType>('collection');
  const [userCoins, setUserCoins] = useState(0);
  const [unlockedActions, setUnlockedActions] = useState<string[]>(['Hi']);
  const [unlockedIngredients, setUnlockedIngredients] = useState<string[]>([]);
  const [unlockedCombos, setUnlockedCombos] = useState<string[]>([]);
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const [selectedIngredient, setSelectedIngredient] = useState<string | null>(null);
  const [currentAnimation, setCurrentAnimation] = useState<string>('Hi');
  const [isLoading, setIsLoading] = useState(false);
  const [debugMode, setDebugMode] = useState(false);

  // Storage Keys
  const STORAGE_KEYS = {
    UNLOCKED_ACTIONS: 'shop_unlocked_actions',
    UNLOCKED_INGREDIENTS: 'shop_unlocked_ingredients',
    UNLOCKED_COMBOS: 'shop_unlocked_combos',
    CURRENT_ANIMATION: 'shop_current_animation',
    DEBUG_MODE: 'shop_debug_mode',
  };

  // Load saved data
  useEffect(() => {
    loadShopData();
  }, [visible]);

  const loadShopData = async () => {
    setIsLoading(true);
    try {
      // Load coins
      const coins = await getRicePul();
      setUserCoins(coins);

      // Load unlocked items and current animation
      const [actions, ingredients, combos, current, debug] = await Promise.all([
        AsyncStorage.getItem(STORAGE_KEYS.UNLOCKED_ACTIONS),
        AsyncStorage.getItem(STORAGE_KEYS.UNLOCKED_INGREDIENTS),
        AsyncStorage.getItem(STORAGE_KEYS.UNLOCKED_COMBOS),
        AsyncStorage.getItem(STORAGE_KEYS.CURRENT_ANIMATION),
        AsyncStorage.getItem(STORAGE_KEYS.DEBUG_MODE),
      ]);

      if (actions) setUnlockedActions(JSON.parse(actions));
      if (ingredients) setUnlockedIngredients(JSON.parse(ingredients));
      if (combos) setUnlockedCombos(JSON.parse(combos));
      if (current) setCurrentAnimation(current);
      if (debug) setDebugMode(JSON.parse(debug));

      // Debug logging
      if (debugMode) {
        debugShopState({
          userCoins: coins,
          unlockedActions: actions ? JSON.parse(actions) : ['Hi'],
          unlockedIngredients: ingredients ? JSON.parse(ingredients) : [],
          unlockedCombos: combos ? JSON.parse(combos) : [],
          currentAnimation: current || 'Hi',
        });
      }
    } catch (error) {
      console.error('Error loading shop data:', error);
      showError('데이터 로드 실패');
    } finally {
      setIsLoading(false);
    }
  };

  // Save unlocked items - 명시적으로 데이터 전달
  const saveShopData = async (newActions?: string[], newIngredients?: string[], newCombos?: string[]) => {
    try {
      const dataToSave = {
        actions: newActions || unlockedActions,
        ingredients: newIngredients || unlockedIngredients,
        combos: newCombos || unlockedCombos,
      };
      
      await Promise.all([
        AsyncStorage.setItem(STORAGE_KEYS.UNLOCKED_ACTIONS, JSON.stringify(dataToSave.actions)),
        AsyncStorage.setItem(STORAGE_KEYS.UNLOCKED_INGREDIENTS, JSON.stringify(dataToSave.ingredients)),
        AsyncStorage.setItem(STORAGE_KEYS.UNLOCKED_COMBOS, JSON.stringify(dataToSave.combos)),
      ]);
      
      if (debugMode) {
        console.log('✅ Shop data saved successfully:', dataToSave);
      }
    } catch (error) {
      console.error('Error saving shop data:', error);
      throw new Error(ERROR_MESSAGES.SAVE_FAILED);
    }
  };

  // Apply animation (새로운 기능!)
  const applyAnimation = async (animationId: string) => {
    try {
      setCurrentAnimation(animationId);
      await AsyncStorage.setItem(STORAGE_KEYS.CURRENT_ANIMATION, animationId);
      
      // GIF 인덱스 매핑
      const gifMapping: Record<string, number> = {
        'Hi': 0,
        'Sad': 1,
        'Dance': 2,
        'Jump': 3,
        'Sunglass': 4,
        'Gunchim': 5,
        // 조합 애니메이션은 6번부터 시작
      };
      
      // 기본 동작인 경우
      if (gifMapping[animationId] !== undefined) {
        onGifChange(gifMapping[animationId]);
      } else {
        // 조합 애니메이션인 경우 - 임시로 0번 사용 (추후 개선 필요)
        onGifChange(0);
      }
      
      showSuccess(`${animationId} 애니메이션이 적용되었습니다!`);
      
      if (debugMode) {
        console.log(`🎬 Applied animation: ${animationId}`);
      }
    } catch (error) {
      console.error('Error applying animation:', error);
      showError('애니메이션 적용 실패');
    }
  };

  // Purchase action
  const purchaseAction = async (actionId: string) => {
    try {
      const action = ACTIONS[actionId];
      if (!action) {
        throw new Error(ERROR_MESSAGES.INVALID_ITEM);
      }

      if (unlockedActions.includes(actionId)) {
        showError(ERROR_MESSAGES.ALREADY_OWNED);
        return;
      }

      if (userCoins < action.price) {
        showError(ERROR_MESSAGES.INSUFFICIENT_COINS);
        return;
      }

      // Process purchase
      setIsLoading(true);
      const success = await spendRicePul(action.price);
      
      if (success) {
        const newUnlockedActions = [...unlockedActions, actionId];
        setUnlockedActions(newUnlockedActions);
        setUserCoins(userCoins - action.price);
        
        // 새로운 데이터를 명시적으로 전달
        await saveShopData(newUnlockedActions, undefined, undefined);
        
        showSuccess(`${action.name} 동작을 구매했습니다!`);
        
        // Check for new combos
        checkNewCombos(actionId, 'action');
      } else {
        throw new Error(ERROR_MESSAGES.PURCHASE_FAILED);
      }
    } catch (error) {
      console.error('Purchase action error:', error);
      showError(error.message || ERROR_MESSAGES.PURCHASE_FAILED);
    } finally {
      setIsLoading(false);
    }
  };

  // Purchase ingredient
  const purchaseIngredient = async (ingredientId: string) => {
    try {
      const ingredient = INGREDIENTS[ingredientId];
      if (!ingredient) {
        throw new Error(ERROR_MESSAGES.INVALID_ITEM);
      }

      if (unlockedIngredients.includes(ingredientId)) {
        showError(ERROR_MESSAGES.ALREADY_OWNED);
        return;
      }

      if (userCoins < ingredient.price) {
        showError(ERROR_MESSAGES.INSUFFICIENT_COINS);
        return;
      }

      // Process purchase
      setIsLoading(true);
      const success = await spendRicePul(ingredient.price);
      
      if (success) {
        const newUnlockedIngredients = [...unlockedIngredients, ingredientId];
        setUnlockedIngredients(newUnlockedIngredients);
        setUserCoins(userCoins - ingredient.price);
        
        // 새로운 데이터를 명시적으로 전달
        await saveShopData(undefined, newUnlockedIngredients, undefined);
        
        showSuccess(`${ingredient.name} 재료를 구매했습니다!`);
        
        // Check for new combos
        checkNewCombos(ingredientId, 'ingredient');
      } else {
        throw new Error(ERROR_MESSAGES.PURCHASE_FAILED);
      }
    } catch (error) {
      console.error('Purchase ingredient error:', error);
      showError(error.message || ERROR_MESSAGES.PURCHASE_FAILED);
    } finally {
      setIsLoading(false);
    }
  };

  // Purchase combo
  const purchaseCombo = async (actionId: string, ingredientId: string) => {
    try {
      const comboPrice = calculateComboPrice(actionId, ingredientId);
      const comboId = `${actionId}_${ingredientId}`;

      if (unlockedCombos.includes(comboId)) {
        showError(ERROR_MESSAGES.ALREADY_OWNED);
        return;
      }

      // Check if both action and ingredient are unlocked
      if (!unlockedActions.includes(actionId)) {
        showError(`먼저 ${ACTIONS[actionId].name} 동작을 구매해주세요!`);
        return;
      }

      if (!unlockedIngredients.includes(ingredientId)) {
        showError(`먼저 ${INGREDIENTS[ingredientId].name} 재료를 구매해주세요!`);
        return;
      }

      if (userCoins < comboPrice) {
        showError(ERROR_MESSAGES.INSUFFICIENT_COINS);
        return;
      }

      // Process purchase
      setIsLoading(true);
      const success = await spendRicePul(comboPrice);
      
      if (success) {
        const newUnlockedCombos = [...unlockedCombos, comboId];
        setUnlockedCombos(newUnlockedCombos);
        setUserCoins(userCoins - comboPrice);
        
        // 새로운 데이터를 명시적으로 전달
        await saveShopData(undefined, undefined, newUnlockedCombos);
        
        showSuccess(SUCCESS_MESSAGES.COMBO_UNLOCKED);
      } else {
        throw new Error(ERROR_MESSAGES.PURCHASE_FAILED);
      }
    } catch (error) {
      console.error('Purchase combo error:', error);
      showError(error.message || ERROR_MESSAGES.PURCHASE_FAILED);
    } finally {
      setIsLoading(false);
    }
  };

  // Purchase special pack
  const purchasePack = async (packId: string) => {
    try {
      const pack = SPECIAL_PACKS[packId];
      if (!pack) {
        throw new Error(ERROR_MESSAGES.INVALID_ITEM);
      }

      if (userCoins < pack.price) {
        showError(ERROR_MESSAGES.INSUFFICIENT_COINS);
        return;
      }

      // Process purchase
      setIsLoading(true);
      const success = await spendRicePul(pack.price);
      
      if (success) {
        const newActions: string[] = [];
        const newIngredients: string[] = [];

        // Unlock all items in pack
        pack.items.forEach(itemId => {
          if (ACTIONS[itemId] && !unlockedActions.includes(itemId)) {
            newActions.push(itemId);
          }
          if (INGREDIENTS[itemId] && !unlockedIngredients.includes(itemId)) {
            newIngredients.push(itemId);
          }
        });

        const updatedActions = [...unlockedActions, ...newActions];
        const updatedIngredients = [...unlockedIngredients, ...newIngredients];
        
        setUnlockedActions(updatedActions);
        setUnlockedIngredients(updatedIngredients);
        setUserCoins(userCoins - pack.price);
        
        // 새로운 데이터를 명시적으로 전달
        await saveShopData(updatedActions, updatedIngredients, unlockedCombos);
        
        showSuccess(`${pack.name} 패키지를 구매했습니다! ${pack.discount} 코인 절약!`);
      } else {
        throw new Error(ERROR_MESSAGES.PURCHASE_FAILED);
      }
    } catch (error) {
      console.error('Purchase pack error:', error);
      showError(error.message || ERROR_MESSAGES.PURCHASE_FAILED);
    } finally {
      setIsLoading(false);
    }
  };

  // Check for new combo availability
  const checkNewCombos = (itemId: string, type: 'action' | 'ingredient') => {
    const newCombos: string[] = [];
    
    COMBO_ANIMATIONS.forEach(combo => {
      if (type === 'action' && combo.action === itemId) {
        if (unlockedIngredients.includes(combo.ingredient)) {
          newCombos.push(combo.id);
        }
      } else if (type === 'ingredient' && combo.ingredient === itemId) {
        if (unlockedActions.includes(combo.action)) {
          newCombos.push(combo.id);
        }
      }
    });

    if (newCombos.length > 0 && debugMode) {
      console.log(`🎉 New combos available: ${newCombos.join(', ')}`);
    }
  };

  // Debug functions
  const unlockAllItems = async () => {
    if (!debugMode) return;
    
    setUnlockedActions(Object.keys(ACTIONS));
    setUnlockedIngredients(Object.keys(INGREDIENTS));
    
    const allCombos = COMBO_ANIMATIONS.map(c => c.id);
    setUnlockedCombos(allCombos);
    
    await saveShopData();
    showSuccess('🔓 모든 아이템 잠금 해제!');
  };

  const resetPurchases = async () => {
    if (!debugMode) return;
    
    setUnlockedActions(['Hi']);
    setUnlockedIngredients([]);
    setUnlockedCombos([]);
    setCurrentAnimation('Hi');
    
    await AsyncStorage.multiRemove([
      STORAGE_KEYS.UNLOCKED_ACTIONS,
      STORAGE_KEYS.UNLOCKED_INGREDIENTS,
      STORAGE_KEYS.UNLOCKED_COMBOS,
      STORAGE_KEYS.CURRENT_ANIMATION,
    ]);
    
    showSuccess('🔄 구매 내역 초기화!');
  };

  // UI Helpers
  const showError = (message: string) => {
    if (Platform.OS === 'web') {
      window.alert(`❌ ${message}`);
    } else {
      Alert.alert('오류', message, [{ text: '확인' }]);
    }
  };

  const showSuccess = (message: string) => {
    if (Platform.OS === 'web') {
      window.alert(`✅ ${message}`);
    } else {
      Alert.alert('성공', message, [{ text: '확인' }]);
    }
  };

  // Render tabs
  const renderTabs = () => (
    <View style={styles.tabContainer}>
      <TouchableOpacity
        style={[styles.tab, activeTab === 'collection' && styles.activeTab]}
        onPress={() => setActiveTab('collection')}
      >
        <Text style={[styles.tabText, activeTab === 'collection' && styles.activeTabText]}>
          내 컬렉션 🎁
        </Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.tab, activeTab === 'actions' && styles.activeTab]}
        onPress={() => setActiveTab('actions')}
      >
        <Text style={[styles.tabText, activeTab === 'actions' && styles.activeTabText]}>
          동작 💃
        </Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.tab, activeTab === 'ingredients' && styles.activeTab]}
        onPress={() => setActiveTab('ingredients')}
      >
        <Text style={[styles.tabText, activeTab === 'ingredients' && styles.activeTabText]}>
          재료 🍳
        </Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.tab, activeTab === 'combos' && styles.activeTab]}
        onPress={() => setActiveTab('combos')}
      >
        <Text style={[styles.tabText, activeTab === 'combos' && styles.activeTabText]}>
          조합 ✨
        </Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.tab, activeTab === 'packs' && styles.activeTab]}
        onPress={() => setActiveTab('packs')}
      >
        <Text style={[styles.tabText, activeTab === 'packs' && styles.activeTabText]}>
          패키지 🎪
        </Text>
      </TouchableOpacity>
    </View>
  );

  // Render collection tab (NEW!)
  const renderCollectionTab = () => (
    <ScrollView style={styles.itemsContainer}>
      <Text style={styles.sectionTitle}>🎬 보유한 애니메이션</Text>
      
      {/* 기본 동작 */}
      <Text style={styles.subSectionTitle}>기본 동작</Text>
      {unlockedActions.map(actionId => {
        const action = ACTIONS[actionId];
        if (!action) return null;
        const isActive = currentAnimation === actionId;
        
        return (
          <TouchableOpacity
            key={actionId}
            style={[styles.collectionItem, isActive && styles.activeAnimation]}
            onPress={() => applyAnimation(actionId)}
          >
            <View style={styles.itemPreview}>
              {action.preview ? (
                <Image 
                  source={action.preview} 
                  style={styles.previewImage}
                  contentFit="contain"
                />
              ) : (
                <Text style={styles.itemEmoji}>{action.emoji}</Text>
              )}
            </View>
            <View style={styles.itemInfo}>
              <Text style={styles.itemName}>{action.name}</Text>
              <Text style={styles.itemDescription}>{action.description}</Text>
            </View>
            <TouchableOpacity
              style={[styles.applyButton, isActive && styles.appliedButton]}
              onPress={() => applyAnimation(actionId)}
            >
              <Text style={styles.applyButtonText}>
                {isActive ? '적용중 ✓' : '적용하기'}
              </Text>
            </TouchableOpacity>
          </TouchableOpacity>
        );
      })}
      
      {/* 조합 애니메이션 */}
      {unlockedCombos.length > 0 && (
        <>
          <Text style={styles.subSectionTitle}>조합 애니메이션</Text>
          {unlockedCombos.map(comboId => {
            const combo = COMBO_ANIMATIONS.find(c => c.id === comboId);
            if (!combo) return null;
            const isActive = currentAnimation === comboId;
            
            return (
              <TouchableOpacity
                key={comboId}
                style={[styles.collectionItem, isActive && styles.activeAnimation]}
                onPress={() => applyAnimation(comboId)}
              >
                <View style={styles.itemInfo}>
                  <Text style={styles.itemName}>
                    {ACTIONS[combo.action]?.name} + {INGREDIENTS[combo.ingredient]?.name}
                  </Text>
                  <Text style={styles.itemDescription}>특별한 조합 애니메이션</Text>
                </View>
                <TouchableOpacity
                  style={[styles.applyButton, isActive && styles.appliedButton]}
                  onPress={() => applyAnimation(comboId)}
                >
                  <Text style={styles.applyButtonText}>
                    {isActive ? '적용중 ✓' : '적용하기'}
                  </Text>
                </TouchableOpacity>
              </TouchableOpacity>
            );
          })}
        </>
      )}
      
      {unlockedActions.length === 1 && unlockedCombos.length === 0 && (
        <View style={styles.emptyState}>
          <Text style={styles.emptyStateText}>
            아직 구매한 애니메이션이 없습니다.
          </Text>
          <Text style={styles.emptyStateSubtext}>
            동작과 재료를 구매하여 컬렉션을 늘려보세요!
          </Text>
        </View>
      )}
    </ScrollView>
  );

  // Render actions tab
  const renderActionsTab = () => (
    <ScrollView style={styles.itemsContainer}>
      {Object.values(ACTIONS).map((action) => {
        const isUnlocked = unlockedActions.includes(action.id);
        return (
          <TouchableOpacity
            key={action.id}
            style={[styles.shopItem, isUnlocked && styles.unlockedItem]}
            onPress={() => !isUnlocked && purchaseAction(action.id)}
            disabled={isUnlocked || isLoading}
          >
            <View style={styles.itemPreview}>
              {action.preview ? (
                <Image 
                  source={action.preview} 
                  style={styles.previewImage}
                  contentFit="contain"
                />
              ) : (
                <Text style={styles.itemEmoji}>{action.emoji}</Text>
              )}
            </View>
            <View style={styles.itemInfo}>
              <Text style={styles.itemName}>{action.name}</Text>
              <Text style={styles.itemDescription}>{action.description}</Text>
              <View style={styles.priceContainer}>
                {isUnlocked ? (
                  <Text style={styles.ownedText}>보유중 ✓</Text>
                ) : (
                  <View style={styles.priceRow}>
                    <RNImage source={require('../assets/rice.png')} style={styles.riceIcon} />
                    <Text style={styles.itemPrice}>{action.price}</Text>
                  </View>
                )}
              </View>
            </View>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );

  // Render ingredients tab
  const renderIngredientsTab = () => (
    <ScrollView style={styles.itemsContainer}>
      {Object.values(INGREDIENTS).map((ingredient) => {
        const isUnlocked = unlockedIngredients.includes(ingredient.id);
        return (
          <TouchableOpacity
            key={ingredient.id}
            style={[styles.shopItem, isUnlocked && styles.unlockedItem]}
            onPress={() => !isUnlocked && purchaseIngredient(ingredient.id)}
            disabled={isUnlocked || isLoading}
          >
            <View style={styles.itemPreview}>
              {ingredient.preview ? (
                <Image 
                  source={ingredient.preview} 
                  style={styles.previewImage}
                  contentFit="contain"
                />
              ) : (
                <Text style={styles.itemEmoji}>{ingredient.emoji}</Text>
              )}
            </View>
            <View style={styles.itemInfo}>
              <Text style={styles.itemName}>{ingredient.name}</Text>
              <Text style={styles.itemDescription}>{ingredient.description}</Text>
              <View style={styles.priceContainer}>
                {isUnlocked ? (
                  <Text style={styles.ownedText}>보유중 ✓</Text>
                ) : (
                  <View style={styles.priceRow}>
                    <RNImage source={require('../assets/rice.png')} style={styles.riceIcon} />
                    <Text style={styles.itemPrice}>{ingredient.price}</Text>
                  </View>
                )}
              </View>
            </View>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );

  // Render combos tab
  const renderCombosTab = () => (
    <ScrollView style={styles.itemsContainer}>
      <View style={styles.comboSelector}>
        <View style={styles.selectorSection}>
          <Text style={styles.selectorTitle}>동작 선택</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            {unlockedActions.map(actionId => (
              <TouchableOpacity
                key={actionId}
                style={[
                  styles.selectorItem,
                  selectedAction === actionId && styles.selectedItem
                ]}
                onPress={() => setSelectedAction(actionId)}
              >
                <Text style={styles.selectorEmoji}>{ACTIONS[actionId]?.emoji}</Text>
                <Text style={styles.selectorName}>{ACTIONS[actionId]?.name}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
        
        <View style={styles.selectorSection}>
          <Text style={styles.selectorTitle}>재료 선택</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            {unlockedIngredients.map(ingredientId => (
              <TouchableOpacity
                key={ingredientId}
                style={[
                  styles.selectorItem,
                  selectedIngredient === ingredientId && styles.selectedItem
                ]}
                onPress={() => setSelectedIngredient(ingredientId)}
              >
                {INGREDIENTS[ingredientId]?.preview ? (
                  <RNImage 
                    source={INGREDIENTS[ingredientId].preview} 
                    style={styles.selectorImage}
                  />
                ) : (
                  <Text style={styles.selectorEmoji}>{INGREDIENTS[ingredientId]?.emoji}</Text>
                )}
                <Text style={styles.selectorName}>{INGREDIENTS[ingredientId]?.name}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      </View>

      {selectedAction && selectedIngredient && (
        <View style={styles.comboPreview}>
          <Text style={styles.comboTitle}>
            {ACTIONS[selectedAction].name} + {INGREDIENTS[selectedIngredient].name}
          </Text>
          {unlockedCombos.includes(`${selectedAction}_${selectedIngredient}`) ? (
            <View style={styles.comboOwned}>
              <Text style={styles.ownedText}>이미 보유한 조합입니다 ✓</Text>
            </View>
          ) : (
            <TouchableOpacity
              style={styles.comboPurchaseButton}
              onPress={() => purchaseCombo(selectedAction, selectedIngredient)}
              disabled={isLoading}
            >
              <View style={styles.comboPurchaseContent}>
                <Text style={styles.comboPurchaseText}>조합 구매</Text>
                <View style={styles.priceRow}>
                  <RNImage source={require('../assets/rice.png')} style={styles.riceIconSmall} />
                  <Text style={styles.comboPurchasePrice}>{calculateComboPrice(selectedAction, selectedIngredient)}</Text>
                </View>
              </View>
            </TouchableOpacity>
          )}
        </View>
      )}

      <View style={styles.unlockedCombosSection}>
        <Text style={styles.sectionTitle}>보유한 조합</Text>
        {unlockedCombos.map(comboId => {
          const combo = COMBO_ANIMATIONS.find(c => c.id === comboId);
          if (!combo) return null;
          
          return (
            <View key={comboId} style={styles.unlockedComboItem}>
              <Text style={styles.comboItemText}>
                {ACTIONS[combo.action]?.emoji} {ACTIONS[combo.action]?.name} + 
                {INGREDIENTS[combo.ingredient]?.emoji} {INGREDIENTS[combo.ingredient]?.name}
              </Text>
            </View>
          );
        })}
      </View>
    </ScrollView>
  );

  // Render packs tab
  const renderPacksTab = () => (
    <ScrollView style={styles.itemsContainer}>
      {Object.values(SPECIAL_PACKS).map((pack) => (
        <TouchableOpacity
          key={pack.id}
          style={styles.packItem}
          onPress={() => purchasePack(pack.id)}
          disabled={isLoading}
        >
          <View style={styles.packHeader}>
            <Text style={styles.packEmoji}>{pack.emoji}</Text>
            <View style={styles.packBadge}>
              <Text style={styles.packBadgeText}>-{pack.discount} 코인</Text>
            </View>
          </View>
          <Text style={styles.packName}>{pack.name}</Text>
          <Text style={styles.packDescription}>{pack.description}</Text>
          <View style={styles.packItems}>
            {pack.items.map(itemId => (
              <Text key={itemId} style={styles.packItemName}>
                • {ACTIONS[itemId]?.name || INGREDIENTS[itemId]?.name}
              </Text>
            ))}
          </View>
          <View style={styles.packPriceContainer}>
            <View style={styles.priceRow}>
              <RNImage source={require('../assets/rice.png')} style={styles.riceIcon} />
              <Text style={styles.packOriginalPrice}>{pack.originalPrice}</Text>
            </View>
            <View style={styles.priceRow}>
              <RNImage source={require('../assets/rice.png')} style={styles.riceIconLarge} />
              <Text style={styles.packPrice}>{pack.price}</Text>
            </View>
          </View>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={true}
      onRequestClose={onClose}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <View style={styles.header}>
            <Text style={styles.title}>🏪 캐릭터 상점</Text>
            <TouchableOpacity onPress={onClose} style={styles.closeButton}>
              <Text style={styles.closeButtonText}>✕</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.coinDisplay}>
            <View style={styles.coinRow}>
              <RNImage source={require('../assets/rice.png')} style={styles.riceIconLarge} />
              <Text style={styles.coinText}>{userCoins} 밥풀</Text>
            </View>
          </View>

          {renderTabs()}

          {isLoading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color="#FFBF00" />
              <Text style={styles.loadingText}>처리중...</Text>
            </View>
          ) : (
            <>
              {activeTab === 'collection' && renderCollectionTab()}
              {activeTab === 'actions' && renderActionsTab()}
              {activeTab === 'ingredients' && renderIngredientsTab()}
              {activeTab === 'combos' && renderCombosTab()}
              {activeTab === 'packs' && renderPacksTab()}
            </>
          )}

          {debugMode && (
            <View style={styles.debugPanel}>
              <Text style={styles.debugTitle}>🐛 디버그 모드</Text>
              <View style={styles.debugButtons}>
                <TouchableOpacity
                  style={styles.debugButton}
                  onPress={unlockAllItems}
                >
                  <Text style={styles.debugButtonText}>모두 잠금해제</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.debugButton}
                  onPress={resetPurchases}
                >
                  <Text style={styles.debugButtonText}>초기화</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.debugButton}
                  onPress={() => debugShopState({
                    userCoins,
                    unlockedActions,
                    unlockedIngredients,
                    unlockedCombos,
                    currentAnimation,
                  })}
                >
                  <Text style={styles.debugButtonText}>상태 로그</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalContent: {
    width: SCREEN_WIDTH * 0.95,
    height: SCREEN_HEIGHT * 0.85,
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    backgroundColor: '#FFBF00',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
  closeButton: {
    padding: 5,
  },
  closeButtonText: {
    fontSize: 28,
    color: '#FFFFFF',
  },
  coinDisplay: {
    backgroundColor: '#FFF8DC',
    padding: 15,
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#FFE4B5',
  },
  coinText: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FF8C00',
  },
  tabContainer: {
    flexDirection: 'row',
    backgroundColor: '#F5F5F5',
    paddingVertical: 10,
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
  },
  activeTab: {
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 3,
    borderBottomColor: '#FFBF00',
  },
  tabText: {
    fontSize: 12,
    color: '#666666',
  },
  activeTabText: {
    fontWeight: 'bold',
    color: '#FFBF00',
  },
  itemsContainer: {
    flex: 1,
    padding: 15,
  },
  shopItem: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderRadius: 15,
    padding: 15,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: '#E0E0E0',
  },
  unlockedItem: {
    backgroundColor: '#F0FFF0',
    borderColor: '#90EE90',
  },
  collectionItem: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderRadius: 15,
    padding: 15,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: '#E0E0E0',
    alignItems: 'center',
  },
  activeAnimation: {
    backgroundColor: '#FFF8DC',
    borderColor: '#FFD700',
  },
  itemPreview: {
    width: 60,
    height: 60,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 15,
  },
  previewImage: {
    width: 60,
    height: 60,
    borderRadius: 10,
  },
  itemEmoji: {
    fontSize: 36,
  },
  itemInfo: {
    flex: 1,
    justifyContent: 'space-between',
  },
  itemName: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333333',
  },
  itemDescription: {
    fontSize: 14,
    color: '#666666',
    marginTop: 4,
  },
  priceContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
  itemPrice: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#FF8C00',
  },
  ownedText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#32CD32',
  },
  applyButton: {
    backgroundColor: '#FFBF00',
    borderRadius: 20,
    paddingVertical: 8,
    paddingHorizontal: 20,
  },
  appliedButton: {
    backgroundColor: '#32CD32',
  },
  applyButtonText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333333',
    marginBottom: 15,
    marginTop: 10,
  },
  subSectionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#666666',
    marginBottom: 10,
    marginTop: 15,
  },
  emptyState: {
    padding: 40,
    alignItems: 'center',
  },
  emptyStateText: {
    fontSize: 16,
    color: '#666666',
    marginBottom: 10,
  },
  emptyStateSubtext: {
    fontSize: 14,
    color: '#999999',
    textAlign: 'center',
  },
  comboSelector: {
    backgroundColor: '#F8F8F8',
    borderRadius: 15,
    padding: 15,
    marginBottom: 20,
  },
  selectorSection: {
    marginBottom: 15,
  },
  selectorTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333333',
    marginBottom: 10,
  },
  selectorItem: {
    backgroundColor: '#FFFFFF',
    borderRadius: 10,
    padding: 10,
    marginRight: 10,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#E0E0E0',
  },
  selectedItem: {
    borderColor: '#FFBF00',
    backgroundColor: '#FFF8DC',
  },
  selectorEmoji: {
    fontSize: 24,
    marginBottom: 4,
  },
  selectorImage: {
    width: 30,
    height: 30,
    resizeMode: 'contain',
    marginBottom: 4,
  },
  selectorName: {
    fontSize: 12,
    color: '#666666',
  },
  comboPreview: {
    backgroundColor: '#FFFFFF',
    borderRadius: 15,
    padding: 20,
    marginBottom: 20,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#FFBF00',
  },
  comboTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333333',
    marginBottom: 15,
  },
  comboPurchaseButton: {
    backgroundColor: '#FFBF00',
    borderRadius: 25,
    paddingVertical: 12,
    paddingHorizontal: 30,
  },
  comboPurchaseText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
  comboOwned: {
    padding: 10,
  },
  unlockedCombosSection: {
    marginTop: 20,
  },
  unlockedComboItem: {
    backgroundColor: '#F0FFF0',
    borderRadius: 10,
    padding: 10,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#90EE90',
  },
  comboItemText: {
    fontSize: 14,
    color: '#333333',
  },
  packItem: {
    backgroundColor: '#FFF8DC',
    borderRadius: 15,
    padding: 20,
    marginBottom: 15,
    borderWidth: 2,
    borderColor: '#FFD700',
  },
  packHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  packEmoji: {
    fontSize: 36,
  },
  packBadge: {
    backgroundColor: '#FF6347',
    borderRadius: 15,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  packBadgeText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
  packName: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333333',
    marginBottom: 8,
  },
  packDescription: {
    fontSize: 14,
    color: '#666666',
    marginBottom: 12,
  },
  packItems: {
    marginBottom: 15,
  },
  packItemName: {
    fontSize: 14,
    color: '#333333',
    marginBottom: 4,
  },
  packPriceContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 15,
  },
  packOriginalPrice: {
    fontSize: 16,
    color: '#999999',
    textDecorationLine: 'line-through',
  },
  packPrice: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FF8C00',
  },
  riceIcon: {
    width: 16,
    height: 16,
    marginRight: 4,
    resizeMode: 'contain',
  },
  riceIconSmall: {
    width: 14,
    height: 14,
    marginRight: 3,
    resizeMode: 'contain',
  },
  riceIconLarge: {
    width: 20,
    height: 20,
    marginRight: 5,
    resizeMode: 'contain',
  },
  priceRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  coinRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  comboPurchaseContent: {
    alignItems: 'center',
  },
  comboPurchasePrice: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#FFFFFF',
    marginLeft: 2,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 10,
    fontSize: 16,
    color: '#666666',
  },
  debugPanel: {
    backgroundColor: '#F0F0F0',
    padding: 15,
    borderTopWidth: 1,
    borderTopColor: '#E0E0E0',
  },
  debugTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#333333',
    marginBottom: 10,
  },
  debugButtons: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  debugButton: {
    backgroundColor: '#FF69B4',
    borderRadius: 15,
    paddingVertical: 5,
    paddingHorizontal: 15,
  },
  debugButtonText: {
    fontSize: 12,
    color: '#FFFFFF',
  },
});

export default CharacterShopModal;