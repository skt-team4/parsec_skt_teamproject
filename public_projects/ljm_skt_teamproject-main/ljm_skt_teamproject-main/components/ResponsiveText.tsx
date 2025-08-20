// components/ResponsiveText.tsx
// 반응형 텍스트 컴포넌트 - 줄바꿈 방지 및 말줄임 처리

import React from 'react';
import { Text, TextProps, Platform, TextStyle } from 'react-native';
import { fp } from '../utils/responsive';

interface ResponsiveTextProps extends TextProps {
  children: React.ReactNode;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  weight?: 'normal' | 'medium' | 'bold';
  color?: string;
  lines?: number;
  noWrap?: boolean;
  responsive?: boolean;
  style?: TextStyle | TextStyle[];
}

const fontSizes = {
  xs: 10,
  sm: 12,
  md: 14,
  lg: 16,
  xl: 20,
};

const fontWeights = {
  normal: '400' as const,
  medium: '600' as const,
  bold: '700' as const,
};

export const ResponsiveText: React.FC<ResponsiveTextProps> = ({
  children,
  size = 'md',
  weight = 'normal',
  color = '#333',
  lines,
  noWrap = false,
  responsive = true,
  style,
  ...props
}) => {
  const fontSize = responsive ? fp(fontSizes[size]) : fontSizes[size];
  
  const textStyle: TextStyle = {
    fontSize,
    fontWeight: fontWeights[weight],
    color,
    ...(noWrap && {
      flexWrap: 'nowrap',
      flexShrink: 1,
    }),
    // 웹에서 텍스트 선택 방지 (필요시)
    ...(Platform.OS === 'web' && {
      userSelect: 'none' as any,
      WebkitUserSelect: 'none' as any,
    }),
  };

  return (
    <Text
      style={[textStyle, style]}
      numberOfLines={lines || (noWrap ? 1 : undefined)}
      ellipsizeMode={lines || noWrap ? 'tail' : undefined}
      adjustsFontSizeToFit={Platform.OS === 'ios' && noWrap}
      minimumFontScale={0.7}
      {...props}
    >
      {children}
    </Text>
  );
};

// 제목용 텍스트
export const Title: React.FC<ResponsiveTextProps> = (props) => (
  <ResponsiveText size="xl" weight="bold" lines={2} {...props} />
);

// 부제목용 텍스트
export const Subtitle: React.FC<ResponsiveTextProps> = (props) => (
  <ResponsiveText size="lg" weight="medium" lines={2} {...props} />
);

// 본문용 텍스트
export const Body: React.FC<ResponsiveTextProps> = (props) => (
  <ResponsiveText size="md" weight="normal" {...props} />
);

// 캡션용 텍스트
export const Caption: React.FC<ResponsiveTextProps> = (props) => (
  <ResponsiveText size="sm" weight="normal" color="#666" lines={1} {...props} />
);

// 라벨용 텍스트
export const Label: React.FC<ResponsiveTextProps> = (props) => (
  <ResponsiveText size="xs" weight="medium" noWrap {...props} />
);

export default ResponsiveText;