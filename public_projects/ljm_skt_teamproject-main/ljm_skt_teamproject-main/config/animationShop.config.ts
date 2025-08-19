// Animation Shop Configuration
// 동작(Action) + 재료(Ingredient) 조합 시스템

export interface AnimationItem {
  id: string;
  name: string;
  price: number;
  description: string;
  unlocked?: boolean;
  category: 'action' | 'ingredient' | 'combo' | 'pack';
  emoji?: string;
  preview?: string;
}

export interface ComboAnimation {
  id: string;
  action: string;
  ingredient: string;
  file: string;
  unlocked?: boolean;
}

export interface SpecialPack {
  id: string;
  name: string;
  items: string[];
  price: number;
  originalPrice: number;
  discount: number;
  description: string;
  emoji?: string;
}

// 동작 카테고리 (실제 파일 기반)
export const ACTIONS: Record<string, AnimationItem> = {
  Hi: {
    id: 'Hi',
    name: '인사',
    price: 0,
    description: '기본 인사 동작',
    unlocked: true,
    category: 'action',
    emoji: '👋',
    preview: require('../assets/Hi.gif')
  },
  Sad: {
    id: 'Sad',
    name: '슬픔',
    price: 50,
    description: '슬픈 표정으로 감정 표현',
    unlocked: false,
    category: 'action',
    emoji: '😢',
    preview: require('../assets/Sad.gif')
  },
  Dance: {
    id: 'Dance',
    name: '춤',
    price: 100,
    description: '신나는 춤 동작',
    unlocked: false,
    category: 'action',
    emoji: '💃',
    preview: require('../assets/Dance.gif')
  },
  Jump: {
    id: 'Jump',
    name: '점프',
    price: 80,
    description: '활기찬 점프 동작',
    unlocked: false,
    category: 'action',
    emoji: '🦘',
    preview: require('../assets/Jump.gif')
  },
  Gunchim: {
    id: 'Gunchim',
    name: '군침',
    price: 200,
    description: '배고픈 모습',
    unlocked: false,
    category: 'action',
    emoji: '🤤',
    preview: require('../assets/Gunchim.gif')
  },
  Sunglass: {
    id: 'Sunglass',
    name: '선글라스',
    price: 180,
    description: '쿨한 모습',
    unlocked: false,
    category: 'action',
    emoji: '😎',
    preview: require('../assets/Sunglass.gif')
  }
};

// 재료 카테고리
export const INGREDIENTS: Record<string, AnimationItem> = {
  '계란말이': {
    id: '계란말이',
    name: '계란말이',
    price: 30,
    description: '부드러운 계란말이',
    unlocked: false,
    category: 'ingredient',
    emoji: '🥚'
  },
  '김': {
    id: '김',
    name: '김',
    price: 20,
    description: '바삭한 김',
    unlocked: false,
    category: 'ingredient',
    emoji: '🍙'
  },
  '명란': {
    id: '명란',
    name: '명란',
    price: 80,
    description: '짭짤한 명란',
    unlocked: false,
    category: 'ingredient',
    emoji: '🐟'
  },
  '베이컨': {
    id: '베이컨',
    name: '베이컨',
    price: 70,
    description: '고소한 베이컨',
    unlocked: false,
    category: 'ingredient',
    emoji: '🥓'
  },
  '연어': {
    id: '연어',
    name: '연어',
    price: 100,
    description: '신선한 연어',
    unlocked: false,
    category: 'ingredient',
    emoji: '🍣'
  },
  '후라이': {
    id: '후라이',
    name: '후라이',
    price: 50,
    description: '바삭한 후라이',
    unlocked: false,
    category: 'ingredient',
    emoji: '🍳'
  },
  '매우편중': {
    id: '매우편중',
    name: '매우편중',
    price: 150,
    description: '극도로 편중된 식사',
    unlocked: false,
    category: 'ingredient',
    emoji: '🍔'
  },
  '편중식사': {
    id: '편중식사',
    name: '편중식사',
    price: 120,
    description: '편중된 식사',
    unlocked: false,
    category: 'ingredient',
    emoji: '🍕'
  }
};

// 특별 패키지
export const SPECIAL_PACKS: Record<string, SpecialPack> = {
  starter_pack: {
    id: 'starter_pack',
    name: '스타터 팩',
    items: ['Sad', '김', '계란말이'],
    price: 80,
    originalPrice: 100,
    discount: 20,
    description: '초보자를 위한 기본 세트',
    emoji: '🎁'
  },
  food_lover_pack: {
    id: 'food_lover_pack',
    name: '음식 애호가 팩',
    items: ['Dance', 'Jump', '베이컨', '연어'],
    price: 280,
    originalPrice: 350,
    discount: 70,
    description: '음식과 함께 춤추기',
    emoji: '🍽️'
  },
  premium_pack: {
    id: 'premium_pack',
    name: '프리미엄 팩',
    items: ['Sunglass', 'Gunchim', '명란', '연어', '매우편중'],
    price: 500,
    originalPrice: 630,
    discount: 130,
    description: '고급 애니메이션 풀세트',
    emoji: '👑'
  },
  cool_pack: {
    id: 'cool_pack',
    name: '쿨가이 팩',
    items: ['Sunglass', 'Jump', '후라이'],
    price: 280,
    originalPrice: 310,
    discount: 30,
    description: '쿨한 스타일 세트',
    emoji: '😎'
  }
};

// 실제 존재하는 조합 애니메이션 파일 매핑
export const COMBO_ANIMATIONS: ComboAnimation[] = [
  // Hi 조합 (8개)
  { id: 'Hi_계란말이', action: 'Hi', ingredient: '계란말이', file: 'Hi_계란말이.gif', unlocked: false },
  { id: 'Hi_김', action: 'Hi', ingredient: '김', file: 'Hi_김.gif', unlocked: false },
  { id: 'Hi_명란', action: 'Hi', ingredient: '명란', file: 'Hi_명란.gif', unlocked: false },
  { id: 'Hi_베이컨', action: 'Hi', ingredient: '베이컨', file: 'Hi_베이컨.gif', unlocked: false },
  { id: 'Hi_연어', action: 'Hi', ingredient: '연어', file: 'Hi_연어.gif', unlocked: false },
  { id: 'Hi_후라이', action: 'Hi', ingredient: '후라이', file: 'Hi_후라이.gif', unlocked: false },
  { id: 'Hi_매우편중', action: 'Hi', ingredient: '매우편중', file: 'Hi_매우편중.gif', unlocked: false },
  { id: 'Hi_편중식사', action: 'Hi', ingredient: '편중식사', file: 'Hi_편중식사.gif', unlocked: false },
  
  // Dance 조합 (6개)
  { id: 'Dance_계란말이', action: 'Dance', ingredient: '계란말이', file: 'Dance_계란말이.gif', unlocked: false },
  { id: 'Dance_김', action: 'Dance', ingredient: '김', file: 'Dance_김.gif', unlocked: false },
  { id: 'Dance_명란', action: 'Dance', ingredient: '명란', file: 'Dance_명란.gif', unlocked: false },
  { id: 'Dance_베이컨', action: 'Dance', ingredient: '베이컨', file: 'Dance_베이컨.gif', unlocked: false },
  { id: 'Dance_연어', action: 'Dance', ingredient: '연어', file: 'Dance_연어.gif', unlocked: false },
  { id: 'Dance_후라이', action: 'Dance', ingredient: '후라이', file: 'Dance_후라이.gif', unlocked: false },
  
  // Jump 조합 (6개)
  { id: 'Jump_계란말이', action: 'Jump', ingredient: '계란말이', file: 'Jump_계란말이.gif', unlocked: false },
  { id: 'Jump_김', action: 'Jump', ingredient: '김', file: 'Jump_김.gif', unlocked: false },
  { id: 'Jump_명란', action: 'Jump', ingredient: '명란', file: 'Jump_명란.gif', unlocked: false },
  { id: 'Jump_베이컨', action: 'Jump', ingredient: '베이컨', file: 'Jump_베이컨.gif', unlocked: false },
  { id: 'Jump_연어', action: 'Jump', ingredient: '연어', file: 'Jump_연어.gif', unlocked: false },
  { id: 'Jump_후라이', action: 'Jump', ingredient: '후라이', file: 'Jump_후라이.gif', unlocked: false },
  
  // Sad 조합 (8개)
  { id: 'Sad_계란말이', action: 'Sad', ingredient: '계란말이', file: 'Sad_계란말이.gif', unlocked: false },
  { id: 'Sad_김', action: 'Sad', ingredient: '김', file: 'Sad_김.gif', unlocked: false },
  { id: 'Sad_명란', action: 'Sad', ingredient: '명란', file: 'Sad_명란.gif', unlocked: false },
  { id: 'Sad_베이컨', action: 'Sad', ingredient: '베이컨', file: 'Sad_베이컨.gif', unlocked: false },
  { id: 'Sad_연어', action: 'Sad', ingredient: '연어', file: 'Sad_연어.gif', unlocked: false },
  { id: 'Sad_후라이', action: 'Sad', ingredient: '후라이', file: 'Sad_후라이.gif', unlocked: false },
  { id: 'Sad_매우편중', action: 'Sad', ingredient: '매우편중', file: 'Sad_매우편중.gif', unlocked: false },
  { id: 'Sad_편중식사', action: 'Sad', ingredient: '편중식사', file: 'Sad_편중식사.gif', unlocked: false },
];

// 조합 가격 계산 함수
export const calculateComboPrice = (actionId: string, ingredientId: string): number => {
  const action = ACTIONS[actionId];
  const ingredient = INGREDIENTS[ingredientId];
  
  if (!action || !ingredient) {
    console.error('Invalid action or ingredient:', actionId, ingredientId);
    return 0;
  }
  
  // 조합 가격 = (동작 가격 + 재료 가격) * 0.8 (20% 할인)
  return Math.floor((action.price + ingredient.price) * 0.8);
};

// 잠금 해제 확인 함수
export const isComboUnlocked = (
  actionId: string, 
  ingredientId: string, 
  unlockedActions: string[], 
  unlockedIngredients: string[]
): boolean => {
  return unlockedActions.includes(actionId) && unlockedIngredients.includes(ingredientId);
};

// 디버깅 유틸리티
export const debugShopState = (state: any) => {
  console.group('🛍️ Shop Debug Info');
  console.log('User Coins:', state.userCoins);
  console.log('Unlocked Actions:', state.unlockedActions);
  console.log('Unlocked Ingredients:', state.unlockedIngredients);
  console.log('Unlocked Combos:', state.unlockedCombos);
  console.groupEnd();
};

// 에러 메시지
export const ERROR_MESSAGES = {
  INSUFFICIENT_COINS: '코인이 부족합니다!',
  ALREADY_OWNED: '이미 보유하고 있습니다!',
  PURCHASE_FAILED: '구매 중 오류가 발생했습니다.',
  INVALID_ITEM: '유효하지 않은 아이템입니다.',
  NETWORK_ERROR: '네트워크 오류가 발생했습니다.',
  SAVE_FAILED: '저장 중 오류가 발생했습니다.'
};

// 성공 메시지
export const SUCCESS_MESSAGES = {
  PURCHASE_SUCCESS: '구매가 완료되었습니다!',
  COMBO_UNLOCKED: '새로운 조합이 해제되었습니다!',
  PACK_PURCHASED: '패키지 구매가 완료되었습니다!'
};