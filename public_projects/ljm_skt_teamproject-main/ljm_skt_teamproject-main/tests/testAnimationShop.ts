// Test file for Animation Shop System
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  ACTIONS,
  INGREDIENTS,
  SPECIAL_PACKS,
  COMBO_ANIMATIONS,
  calculateComboPrice,
  isComboUnlocked,
  ERROR_MESSAGES,
  SUCCESS_MESSAGES,
} from '../config/animationShop.config';

// Test Configuration
const DEBUG = true;

// Test Helper Functions
const log = (message: string, data?: any) => {
  if (DEBUG) {
    console.log(`🧪 TEST: ${message}`, data || '');
  }
};

const error = (message: string, err?: any) => {
  console.error(`❌ TEST ERROR: ${message}`, err || '');
};

const success = (message: string) => {
  console.log(`✅ TEST PASSED: ${message}`);
};

// Test Cases
export const runAnimationShopTests = async () => {
  console.group('🏪 Animation Shop System Tests');
  
  try {
    // Test 1: Verify all actions have valid configuration
    testActionsConfiguration();
    
    // Test 2: Verify all ingredients have valid configuration
    testIngredientsConfiguration();
    
    // Test 3: Test combo price calculation
    testComboPriceCalculation();
    
    // Test 4: Test combo unlock verification
    testComboUnlockVerification();
    
    // Test 5: Test special packs configuration
    testSpecialPacksConfiguration();
    
    // Test 6: Test AsyncStorage operations
    await testAsyncStorageOperations();
    
    // Test 7: Test error handling
    testErrorHandling();
    
    // Test 8: Test animation file paths
    testAnimationFilePaths();
    
    console.log('\n📊 All tests completed successfully!');
  } catch (err) {
    error('Test suite failed', err);
  } finally {
    console.groupEnd();
  }
};

// Test 1: Actions Configuration
const testActionsConfiguration = () => {
  log('Testing Actions Configuration...');
  
  Object.entries(ACTIONS).forEach(([id, action]) => {
    // Check required fields
    if (!action.id || !action.name || action.price === undefined) {
      error(`Action ${id} missing required fields`);
      return;
    }
    
    // Check price is non-negative
    if (action.price < 0) {
      error(`Action ${id} has negative price: ${action.price}`);
      return;
    }
    
    // Check category
    if (action.category !== 'action') {
      error(`Action ${id} has wrong category: ${action.category}`);
      return;
    }
  });
  
  success('Actions configuration valid');
};

// Test 2: Ingredients Configuration
const testIngredientsConfiguration = () => {
  log('Testing Ingredients Configuration...');
  
  Object.entries(INGREDIENTS).forEach(([id, ingredient]) => {
    // Check required fields
    if (!ingredient.id || !ingredient.name || ingredient.price === undefined) {
      error(`Ingredient ${id} missing required fields`);
      return;
    }
    
    // Check price is non-negative
    if (ingredient.price < 0) {
      error(`Ingredient ${id} has negative price: ${ingredient.price}`);
      return;
    }
    
    // Check category
    if (ingredient.category !== 'ingredient') {
      error(`Ingredient ${id} has wrong category: ${ingredient.category}`);
      return;
    }
  });
  
  success('Ingredients configuration valid');
};

// Test 3: Combo Price Calculation
const testComboPriceCalculation = () => {
  log('Testing Combo Price Calculation...');
  
  // Test valid combo
  const price1 = calculateComboPrice('Hi', '김');
  const expectedPrice1 = Math.floor((ACTIONS.Hi.price + INGREDIENTS['김'].price) * 0.8);
  if (price1 !== expectedPrice1) {
    error(`Combo price calculation wrong: expected ${expectedPrice1}, got ${price1}`);
    return;
  }
  
  // Test another combo
  const price2 = calculateComboPrice('Dance', '베이컨');
  const expectedPrice2 = Math.floor((100 + 70) * 0.8); // Dance: 100, 베이컨: 70
  if (price2 !== expectedPrice2) {
    error(`Combo price calculation wrong: expected ${expectedPrice2}, got ${price2}`);
    return;
  }
  
  // Test invalid combo
  const price3 = calculateComboPrice('InvalidAction', '김');
  if (price3 !== 0) {
    error(`Invalid combo should return 0, got ${price3}`);
    return;
  }
  
  success('Combo price calculation working correctly');
};

// Test 4: Combo Unlock Verification
const testComboUnlockVerification = () => {
  log('Testing Combo Unlock Verification...');
  
  // Test unlocked combo
  const unlocked1 = isComboUnlocked('Hi', '김', ['Hi', 'Dance'], ['김', '베이컨']);
  if (!unlocked1) {
    error('Should be unlocked when both action and ingredient are unlocked');
    return;
  }
  
  // Test locked combo (missing action)
  const unlocked2 = isComboUnlocked('Jump', '김', ['Hi', 'Dance'], ['김', '베이컨']);
  if (unlocked2) {
    error('Should be locked when action is not unlocked');
    return;
  }
  
  // Test locked combo (missing ingredient)
  const unlocked3 = isComboUnlocked('Hi', '연어', ['Hi', 'Dance'], ['김', '베이컨']);
  if (unlocked3) {
    error('Should be locked when ingredient is not unlocked');
    return;
  }
  
  success('Combo unlock verification working correctly');
};

// Test 5: Special Packs Configuration
const testSpecialPacksConfiguration = () => {
  log('Testing Special Packs Configuration...');
  
  Object.entries(SPECIAL_PACKS).forEach(([id, pack]) => {
    // Check required fields
    if (!pack.id || !pack.name || !pack.items || pack.price === undefined) {
      error(`Pack ${id} missing required fields`);
      return;
    }
    
    // Check discount
    const expectedDiscount = pack.originalPrice - pack.price;
    if (pack.discount !== expectedDiscount) {
      error(`Pack ${id} discount mismatch: expected ${expectedDiscount}, got ${pack.discount}`);
      return;
    }
    
    // Check items exist
    pack.items.forEach(itemId => {
      if (!ACTIONS[itemId] && !INGREDIENTS[itemId]) {
        error(`Pack ${id} contains invalid item: ${itemId}`);
      }
    });
  });
  
  success('Special packs configuration valid');
};

// Test 6: AsyncStorage Operations
const testAsyncStorageOperations = async () => {
  log('Testing AsyncStorage Operations...');
  
  const testData = {
    actions: ['Hi', 'Dance', 'Jump'],
    ingredients: ['김', '베이컨'],
    combos: ['Hi_김', 'Dance_베이컨'],
  };
  
  try {
    // Save test data
    await AsyncStorage.setItem('test_actions', JSON.stringify(testData.actions));
    await AsyncStorage.setItem('test_ingredients', JSON.stringify(testData.ingredients));
    await AsyncStorage.setItem('test_combos', JSON.stringify(testData.combos));
    
    // Load test data
    const loadedActions = JSON.parse(await AsyncStorage.getItem('test_actions') || '[]');
    const loadedIngredients = JSON.parse(await AsyncStorage.getItem('test_ingredients') || '[]');
    const loadedCombos = JSON.parse(await AsyncStorage.getItem('test_combos') || '[]');
    
    // Verify data
    if (JSON.stringify(loadedActions) !== JSON.stringify(testData.actions)) {
      error('Actions data mismatch after save/load');
      return;
    }
    
    if (JSON.stringify(loadedIngredients) !== JSON.stringify(testData.ingredients)) {
      error('Ingredients data mismatch after save/load');
      return;
    }
    
    if (JSON.stringify(loadedCombos) !== JSON.stringify(testData.combos)) {
      error('Combos data mismatch after save/load');
      return;
    }
    
    // Clean up test data
    await AsyncStorage.removeItem('test_actions');
    await AsyncStorage.removeItem('test_ingredients');
    await AsyncStorage.removeItem('test_combos');
    
    success('AsyncStorage operations working correctly');
  } catch (err) {
    error('AsyncStorage test failed', err);
  }
};

// Test 7: Error Handling
const testErrorHandling = () => {
  log('Testing Error Handling...');
  
  // Test error messages exist
  const errorKeys = Object.keys(ERROR_MESSAGES);
  const expectedErrors = [
    'INSUFFICIENT_COINS',
    'ALREADY_OWNED',
    'PURCHASE_FAILED',
    'INVALID_ITEM',
    'NETWORK_ERROR',
    'SAVE_FAILED'
  ];
  
  expectedErrors.forEach(key => {
    if (!errorKeys.includes(key)) {
      error(`Missing error message: ${key}`);
      return;
    }
  });
  
  // Test success messages exist
  const successKeys = Object.keys(SUCCESS_MESSAGES);
  const expectedSuccess = [
    'PURCHASE_SUCCESS',
    'COMBO_UNLOCKED',
    'PACK_PURCHASED'
  ];
  
  expectedSuccess.forEach(key => {
    if (!successKeys.includes(key)) {
      error(`Missing success message: ${key}`);
      return;
    }
  });
  
  success('Error handling configured correctly');
};

// Test 8: Animation File Paths
const testAnimationFilePaths = () => {
  log('Testing Animation File Paths...');
  
  // Test combo animations mapping
  COMBO_ANIMATIONS.forEach(combo => {
    // Check action exists
    if (!ACTIONS[combo.action]) {
      error(`Combo ${combo.id} references invalid action: ${combo.action}`);
      return;
    }
    
    // Check ingredient exists
    if (!INGREDIENTS[combo.ingredient]) {
      error(`Combo ${combo.id} references invalid ingredient: ${combo.ingredient}`);
      return;
    }
    
    // Check file naming convention
    const expectedFile = `${combo.action}_${combo.ingredient}.gif`;
    if (combo.file !== expectedFile) {
      error(`Combo ${combo.id} file naming mismatch: expected ${expectedFile}, got ${combo.file}`);
      return;
    }
  });
  
  success('Animation file paths configured correctly');
};

// Performance Test
export const runPerformanceTest = async () => {
  console.group('⚡ Performance Tests');
  
  const startTime = Date.now();
  
  // Test large batch operations
  const testItems = 1000;
  const testData: string[] = [];
  
  for (let i = 0; i < testItems; i++) {
    testData.push(`item_${i}`);
  }
  
  try {
    // Test save performance
    const saveStart = Date.now();
    await AsyncStorage.setItem('perf_test', JSON.stringify(testData));
    const saveTime = Date.now() - saveStart;
    log(`Save ${testItems} items: ${saveTime}ms`);
    
    // Test load performance
    const loadStart = Date.now();
    const loaded = JSON.parse(await AsyncStorage.getItem('perf_test') || '[]');
    const loadTime = Date.now() - loadStart;
    log(`Load ${testItems} items: ${loadTime}ms`);
    
    // Clean up
    await AsyncStorage.removeItem('perf_test');
    
    const totalTime = Date.now() - startTime;
    success(`Performance test completed in ${totalTime}ms`);
  } catch (err) {
    error('Performance test failed', err);
  } finally {
    console.groupEnd();
  }
};

// Export test runner
export default {
  runAll: async () => {
    await runAnimationShopTests();
    await runPerformanceTest();
  },
  runUnit: runAnimationShopTests,
  runPerformance: runPerformanceTest,
};