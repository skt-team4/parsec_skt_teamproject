// components/ChatHeader.tsx
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import React, { useState, useEffect } from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect } from '@react-navigation/native';
import { isSmallScreen, styles } from '../styles/chatStyles';
import { getUserProfile, refreshUserProfile } from '../utils/ricePulManager';

export const ChatHeader = () => {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [ricePul, setRicePul] = useState(0);

  // 밥풀 정보 로드
  const loadRicePul = async () => {
    try {
      const profile = await getUserProfile();
      setRicePul(profile.ricePul);
    } catch (error) {
      console.error('밥풀 정보 로드 실패:', error);
    }
  };

  // 컴포넌트가 마운트되거나 포커스될 때 밥풀 정보 로드
  useEffect(() => {
    loadRicePul();
  }, []);

  useFocusEffect(
    React.useCallback(() => {
      loadRicePul();
    }, [])
  );

  return (
    <LinearGradient
      colors={['#FFBF00', '#FDD046']}
      style={[styles.header, { paddingTop: insets.top + 10 }]}
    >
      <View style={styles.headerContent}>
        <View style={styles.leftSection}>
          <Text style={[styles.headerTitle, { fontSize: isSmallScreen ? 24 : 28 }]}>
            YUM:AI
          </Text>
        </View>
        
        <View style={styles.centerSection}>
          <TouchableOpacity 
            onPress={loadRicePul}
            style={styles.ricePulContainer}
            activeOpacity={0.7}
          >
            <Text style={styles.ricePulIcon}>🍚</Text>
            <Text style={styles.ricePulText}>{ricePul.toLocaleString()}</Text>
          </TouchableOpacity>
        </View>
        
        <View style={styles.rightSection}>
          <TouchableOpacity onPress={() => router.back()} style={styles.closeButtonContainer}>
            <Text style={styles.closeButton}>✕</Text>
          </TouchableOpacity>
        </View>
      </View>
    </LinearGradient>
  );
};