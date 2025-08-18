import React from 'react';
import { Text } from 'react-native';

interface GoogleLogoProps {
  size?: number;
}

export default function GoogleLogo({ size = 20 }: GoogleLogoProps) {
  // Using Google colors in text form as a simple workaround
  return (
    <Text style={{ fontSize: size, fontWeight: 'bold' }}>
      <Text style={{ color: '#4285F4' }}>G</Text>
      <Text style={{ color: '#EA4335' }}>o</Text>
      <Text style={{ color: '#FBBC04' }}>o</Text>
      <Text style={{ color: '#4285F4' }}>g</Text>
      <Text style={{ color: '#34A853' }}>l</Text>
      <Text style={{ color: '#EA4335' }}>e</Text>
    </Text>
  );
}