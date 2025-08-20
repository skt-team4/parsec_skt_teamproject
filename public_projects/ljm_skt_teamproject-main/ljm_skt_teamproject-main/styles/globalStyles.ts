// styles/globalStyles.ts
// 전역 반응형 스타일 설정

import { StyleSheet, Platform } from 'react-native';
import { wp, hp, fp, spacing, getDeviceType } from '../utils/responsive';

// 공통 색상
export const colors = {
  primary: '#FFBF00',
  secondary: '#4CAF50',
  success: '#4CAF50',
  warning: '#FF9800',
  danger: '#F44336',
  info: '#2196F3',
  text: '#333',
  textLight: '#666',
  textMuted: '#999',
  background: '#f8f9fa',
  white: '#fff',
  border: '#e0e0e0',
};

// 반응형 레이아웃 스타일
export const layouts = StyleSheet.create({
  // 컨테이너
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  
  safeContainer: {
    flex: 1,
    backgroundColor: colors.white,
    ...(Platform.OS === 'web' && {
      maxWidth: 1200,
      alignSelf: 'center',
      width: '100%',
    }),
  },
  
  scrollContainer: {
    flexGrow: 1,
  },
  
  // 카드
  card: {
    backgroundColor: colors.white,
    borderRadius: wp(3),
    padding: spacing.md,
    marginVertical: spacing.sm,
    marginHorizontal: spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    // 웹에서 최대 너비 제한
    ...(Platform.OS === 'web' && {
      maxWidth: 600,
      alignSelf: 'center',
      width: '100%',
    }),
  },
  
  // 행
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'nowrap', // 줄바꿈 방지
  },
  
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexWrap: 'nowrap',
  },
  
  // 버튼
  button: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: wp(2),
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: hp(5),
    minWidth: wp(20),
  },
  
  primaryButton: {
    backgroundColor: colors.primary,
  },
  
  buttonText: {
    color: colors.white,
    fontSize: fp(14),
    fontWeight: '600',
  },
  
  // 입력 필드
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: wp(2),
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    fontSize: fp(14),
    minHeight: hp(5),
    backgroundColor: colors.white,
  },
  
  // 섹션
  section: {
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
  },
  
  sectionTitle: {
    fontSize: fp(18),
    fontWeight: 'bold',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  
  // 리스트
  listItem: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  
  // 헤더
  header: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  
  headerTitle: {
    fontSize: fp(20),
    fontWeight: 'bold',
    color: colors.text,
  },
  
  // 모달
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  
  modalContent: {
    backgroundColor: colors.white,
    borderRadius: wp(3),
    padding: spacing.lg,
    width: wp(90),
    maxWidth: 400,
    maxHeight: hp(80),
  },
});

// 반응형 텍스트 스타일
export const typography = StyleSheet.create({
  h1: {
    fontSize: fp(24),
    fontWeight: 'bold',
    color: colors.text,
    lineHeight: fp(32),
  },
  
  h2: {
    fontSize: fp(20),
    fontWeight: 'bold',
    color: colors.text,
    lineHeight: fp(28),
  },
  
  h3: {
    fontSize: fp(18),
    fontWeight: '600',
    color: colors.text,
    lineHeight: fp(24),
  },
  
  body: {
    fontSize: fp(14),
    color: colors.text,
    lineHeight: fp(20),
  },
  
  caption: {
    fontSize: fp(12),
    color: colors.textLight,
    lineHeight: fp(16),
  },
  
  small: {
    fontSize: fp(10),
    color: colors.textMuted,
    lineHeight: fp(14),
  },
  
  // 줄바꿈 방지 스타일
  noWrap: {
    flexWrap: 'nowrap',
    flexShrink: 1,
  },
  
  ellipsis: {
    overflow: 'hidden',
  },
});

// 디바이스별 조건부 스타일
export const deviceStyles = {
  isSmall: getDeviceType() === 'small',
  isMedium: getDeviceType() === 'medium',
  isLarge: getDeviceType() === 'large',
  isXLarge: getDeviceType() === 'xlarge',
};

// 플랫폼별 조건부 스타일
export const platformStyles = {
  isWeb: Platform.OS === 'web',
  isIOS: Platform.OS === 'ios',
  isAndroid: Platform.OS === 'android',
};

export default {
  colors,
  layouts,
  typography,
  deviceStyles,
  platformStyles,
};