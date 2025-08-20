// utils/responsive.ts
// 반응형 디자인 유틸리티

import { Dimensions, Platform, PixelRatio } from 'react-native';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

// 기준 디자인 크기 (iPhone 14 기준)
const BASE_WIDTH = 390;
const BASE_HEIGHT = 844;

// 디바이스 타입 판별
export const getDeviceType = () => {
  const ratio = SCREEN_HEIGHT / SCREEN_WIDTH;
  
  if (SCREEN_WIDTH < 400) return 'small'; // 작은 폰
  if (SCREEN_WIDTH < 768) return 'medium'; // 일반 폰
  if (SCREEN_WIDTH < 1024) return 'large'; // 태블릿
  return 'xlarge'; // 데스크톱
};

// 너비 기준 스케일링
export const wp = (widthPercent: number): number => {
  const elemWidth = typeof widthPercent === "number" ? widthPercent : parseFloat(widthPercent);
  return PixelRatio.roundToNearestPixel((SCREEN_WIDTH * elemWidth) / 100);
};

// 높이 기준 스케일링
export const hp = (heightPercent: number): number => {
  const elemHeight = typeof heightPercent === "number" ? heightPercent : parseFloat(heightPercent);
  return PixelRatio.roundToNearestPixel((SCREEN_HEIGHT * elemHeight) / 100);
};

// 폰트 스케일링
export const fp = (fontSize: number): number => {
  const scale = SCREEN_WIDTH / BASE_WIDTH;
  const newSize = fontSize * scale;
  
  // 최소/최대 크기 제한
  const minSize = fontSize * 0.8;
  const maxSize = fontSize * 1.2;
  
  if (Platform.OS === 'ios') {
    return Math.round(PixelRatio.roundToNearestPixel(Math.max(minSize, Math.min(maxSize, newSize))));
  } else {
    return Math.round(Math.max(minSize, Math.min(maxSize, newSize)));
  }
};

// 반응형 패딩/마진
export const spacing = {
  xs: wp(1),   // 4px on base
  sm: wp(2),   // 8px on base
  md: wp(4),   // 16px on base
  lg: wp(6),   // 24px on base
  xl: wp(8),   // 32px on base
  xxl: wp(10), // 40px on base
};

// 디바이스별 조건부 스타일
export const deviceStyles = (styles: {
  small?: any;
  medium?: any;
  large?: any;
  xlarge?: any;
  default: any;
}) => {
  const deviceType = getDeviceType();
  return styles[deviceType] || styles.default;
};

// 플랫폼별 스타일
export const platformStyles = (styles: {
  ios?: any;
  android?: any;
  web?: any;
  default: any;
}) => {
  const platform = Platform.OS;
  return styles[platform] || styles.default;
};

// 텍스트 줄바꿈 방지 스타일
export const noWrapText = {
  flexShrink: 1,
  flexWrap: 'nowrap' as const,
};

// 긴 텍스트 처리 스타일
export const ellipsisText = (lines: number = 1) => ({
  numberOfLines: lines,
  ellipsizeMode: 'tail' as const,
});

// 컨테이너 반응형 스타일
export const responsiveContainer = {
  flex: 1,
  width: '100%',
  maxWidth: Platform.select({
    web: 1200,
    default: '100%',
  }),
  alignSelf: 'center' as const,
};

// 버튼 반응형 스타일
export const responsiveButton = {
  minWidth: wp(20),
  maxWidth: wp(90),
  paddingHorizontal: spacing.md,
  paddingVertical: spacing.sm,
};

// 카드 반응형 스타일
export const responsiveCard = {
  width: deviceStyles({
    small: '95%',
    medium: '90%',
    large: '85%',
    xlarge: '80%',
    default: '90%',
  }),
  maxWidth: 600,
  alignSelf: 'center' as const,
};

export default {
  wp,
  hp,
  fp,
  spacing,
  getDeviceType,
  deviceStyles,
  platformStyles,
  noWrapText,
  ellipsisText,
  responsiveContainer,
  responsiveButton,
  responsiveCard,
};