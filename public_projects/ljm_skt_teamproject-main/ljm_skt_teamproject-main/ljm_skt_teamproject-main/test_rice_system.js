// Test rice grain system functionality
import {
  getUserProfile,
  addTransaction,
  getMealCardInfo,
  registerMealCard,
  deleteMealCard,
  getRicePulLevel,
  getTransactionHistory
} from './utils/ricePulManager';

async function testRiceSystem() {
  console.log('=== Testing Rice Grain System ===\n');

  // Test 1: Get user profile
  console.log('1. Getting user profile...');
  const profile = await getUserProfile();
  console.log('User Profile:', {
    name: profile.name,
    points: profile.ricePulPoints,
    level: getRicePulLevel(profile.ricePulPoints)
  });

  // Test 2: Add a transaction
  console.log('\n2. Adding a test transaction...');
  await addTransaction({
    type: 'earn',
    amount: 500,
    description: '식사 완료 보상'
  });
  
  const updatedProfile = await getUserProfile();
  console.log('Updated points:', updatedProfile.ricePulPoints);

  // Test 3: Get meal card info
  console.log('\n3. Getting meal card info...');
  const mealCard = await getMealCardInfo();
  if (mealCard) {
    console.log('Meal Card:', {
      balance: mealCard.balance,
      studentId: mealCard.studentId,
      schoolName: mealCard.schoolName
    });
  } else {
    console.log('No meal card registered');
  }

  // Test 4: Get transaction history
  console.log('\n4. Getting transaction history...');
  const history = await getTransactionHistory();
  console.log('Recent transactions:', history.slice(0, 3));

  console.log('\n=== Test Complete ===');
}

// Run test
testRiceSystem().catch(console.error);