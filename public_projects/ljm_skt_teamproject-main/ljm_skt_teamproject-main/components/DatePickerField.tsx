import React from 'react';
import { Platform, TouchableOpacity, Text, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface DatePickerFieldProps {
  value: Date;
  onChange: (date: Date) => void;
  showPicker: boolean;
  setShowPicker: (show: boolean) => void;
}

export default function DatePickerField({ value, onChange, showPicker, setShowPicker }: DatePickerFieldProps) {
  const formatDate = (date: Date) => {
    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  if (Platform.OS === 'web') {
    return (
      <input
        type="date"
        value={formatDate(value)}
        max={new Date().toISOString().split('T')[0]}
        onChange={(e) => {
          const date = new Date(e.target.value + 'T00:00:00');
          onChange(date);
        }}
        style={{
          padding: 12,
          borderRadius: 12,
          border: '1px solid #e0e0e0',
          fontSize: 16,
          width: '100%',
          backgroundColor: '#f5f5f5',
          color: '#007AFF',
          fontWeight: '500',
          cursor: 'pointer'
        }}
      />
    );
  }

  // 모바일용 DateTimePicker - 동적 import
  let DateTimePicker: any;
  try {
    DateTimePicker = require('@react-native-community/datetimepicker').default;
  } catch (e) {
    // DateTimePicker가 없는 경우 처리
    console.log('DateTimePicker not available');
    return (
      <TouchableOpacity
        style={styles.dateButton}
        onPress={() => alert('날짜 선택기를 사용할 수 없습니다.')}
      >
        <Text style={styles.dateButtonText}>{formatDate(value)}</Text>
        <Ionicons name="calendar-outline" size={20} color="#007AFF" />
      </TouchableOpacity>
    );
  }

  return (
    <>
      <TouchableOpacity
        style={styles.dateButton}
        onPress={() => setShowPicker(true)}
      >
        <Text style={styles.dateButtonText}>{formatDate(value)}</Text>
        <Ionicons name="calendar-outline" size={20} color="#007AFF" />
      </TouchableOpacity>
      
      {showPicker && (
        <DateTimePicker
          value={value}
          mode="date"
          display={Platform.OS === 'ios' ? 'spinner' : 'default'}
          onChange={(event: any, date?: Date) => {
            setShowPicker(Platform.OS === 'ios');
            if (date) {
              onChange(date);
            }
          }}
          maximumDate={new Date()}
          style={Platform.OS === 'ios' ? { height: 150 } : {}}
        />
      )}
    </>
  );
}

const styles = StyleSheet.create({
  dateButton: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  dateButtonText: {
    fontSize: 16,
    color: '#007AFF',
    fontWeight: '500',
  },
});