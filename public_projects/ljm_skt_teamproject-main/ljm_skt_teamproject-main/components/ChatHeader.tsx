// components/ChatHeader.tsx
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { isSmallScreen, styles } from '../styles/chatStyles';

export const ChatHeader = () => {
  const router = useRouter();
  const insets = useSafeAreaInsets();

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
        
        <View style={styles.rightSection}>
          <TouchableOpacity onPress={() => router.back()} style={styles.closeButtonContainer}>
            <Text style={styles.closeButton}>✕</Text>
          </TouchableOpacity>
        </View>
      </View>
    </LinearGradient>
  );
};