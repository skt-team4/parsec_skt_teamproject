import { useRouter } from 'expo-router';
import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';
import React, { useEffect, useState } from 'react';
import {
    Alert,
    KeyboardAvoidingView,
    Platform,
    SafeAreaView,
    ScrollView,
    StyleSheet,
    Text,
    TextInput,
    TouchableOpacity,
    View,
} from 'react-native';
import authConfig from '../../config/auth.config';
import googleAuthService from '../../services/googleAuthService';
import StorageService from '../../utils/storage';

// WebBrowser 설정 (구글 로그인용)
WebBrowser.maybeCompleteAuthSession();

export default function LoginScreen() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);

  // Google OAuth 설정 - authConfig 사용
  const [request, response, promptAsync] = Google.useAuthRequest({
    clientId: authConfig.googleClientId,
    scopes: ['openid', 'profile', 'email'],
    redirectUri: authConfig.redirectUri,
  });

  // 디버깅을 위해 redirect URI 출력
  useEffect(() => {
    console.log('Current Redirect URI:', authConfig.redirectUri);
    console.log('Environment:', process.env.EXPO_PUBLIC_ENV || 'development');
  }, []);

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert('오류', '이메일과 비밀번호를 모두 입력해주세요.');
      return;
    }

    setIsLoading(true);

    try {
      // TODO: 실제 API 호출로 교체
      // 임시 로그인 로직
      if (email === 'test@test.com' && password === 'password') {
        const userToken = 'dummy_token_' + Date.now();
        const userId = 'user_123';
        
        console.log('🔐 Login attempt successful');
        
        // StorageService를 통한 통합 처리
        await StorageService.setAuthData(userToken, userId);
        await StorageService.initializeUserData();
        
        console.log('✅ Login data saved, navigating to home...');
        
        // 로그인 성공 시 바로 홈으로 이동
        router.replace('/(tabs)');
        
      } else {
        Alert.alert('로그인 실패', '이메일 또는 비밀번호가 올바르지 않습니다.');
      }
    } catch (error) {
      console.error('로그인 오류:', error);
      Alert.alert('오류', '로그인 중 문제가 발생했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  // Google 로그인 응답 처리
  useEffect(() => {
    if (response) {
      handleGoogleResponse();
    }
  }, [response]);

  // Google 로그인 응답 처리
  const handleGoogleResponse = async () => {
    if (response?.type === 'success') {
      setIsGoogleLoading(true);
      const result = await googleAuthService.handleGoogleLogin(response);
      
      if (result.success && result.user) {
        console.log('✅ Google 로그인 성공:', result.user.name);
        
        // StorageService에 사용자 정보 저장
        const userToken = 'google_token_' + Date.now();
        const userId = result.user.id;
        
        await StorageService.setAuthData(userToken, userId);
        await StorageService.initializeUserData();
        
        // 홈 화면으로 이동
        router.replace('/(tabs)');
      } else {
        Alert.alert('로그인 실패', result.error || '구글 로그인에 실패했습니다.');
      }
      setIsGoogleLoading(false);
    } else if (response?.type === 'error') {
      setIsGoogleLoading(false);
      Alert.alert('구글 로그인 실패', '로그인 중 오류가 발생했습니다.');
    } else if (response?.type === 'cancel') {
      setIsGoogleLoading(false);
    }
  };

  // Google 로그인 시작
  const handleGoogleLogin = async () => {
    if (request) {
      setIsGoogleLoading(true);
      try {
        await promptAsync();
      } catch (error) {
        console.error('Google 로그인 오류:', error);
        Alert.alert('오류', 'Google 로그인을 시작할 수 없습니다.');
        setIsGoogleLoading(false);
      }
    } else {
      Alert.alert('오류', 'Google 로그인 설정을 불러올 수 없습니다.');
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView 
        style={styles.keyboardContainer}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView contentContainerStyle={styles.scrollContainer}>
          {/* 상단 타이틀 */}
          <View style={styles.headerContainer}>
            <TouchableOpacity 
              onPress={() => router.back()}
              style={styles.backButton}
            >
              <Text style={styles.backButtonText}>←</Text>
            </TouchableOpacity>
            
            <View style={styles.titleContainer}>
              <Text style={styles.title}>로그인</Text>
              <Text style={styles.subtitle}>다시 만나서 반가워요! 🦋</Text>
            </View>
          </View>

          {/* 입력 폼 */}
          <View style={styles.formContainer}>
            <View style={styles.inputContainer}>
              <Text style={styles.inputLabel}>이메일</Text>
              <TextInput
                style={styles.textInput}
                value={email}
                onChangeText={setEmail}
                placeholder="이메일을 입력해주세요"
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
              />
            </View>

            <View style={styles.inputContainer}>
              <Text style={styles.inputLabel}>비밀번호</Text>
              <TextInput
                style={styles.textInput}
                value={password}
                onChangeText={setPassword}
                placeholder="비밀번호를 입력해주세요"
                secureTextEntry
              />
            </View>

            {/* 로그인 버튼 */}
            <TouchableOpacity
              style={[styles.loginButton, isLoading && styles.loginButtonDisabled]}
              onPress={handleLogin}
              disabled={isLoading || isGoogleLoading}
            >
              <Text style={styles.loginButtonText}>
                {isLoading ? '로그인 중...' : '로그인'}
              </Text>
            </TouchableOpacity>

            {/* 구분선 */}
            <View style={styles.dividerContainer}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerText}>또는</Text>
              <View style={styles.dividerLine} />
            </View>

            {/* 구글 로그인 버튼 */}
            <TouchableOpacity
              style={[styles.googleLoginButton, isGoogleLoading && styles.loginButtonDisabled]}
              onPress={handleGoogleLogin}
              disabled={isLoading || isGoogleLoading}
            >
              <Text style={styles.googleLoginIcon}>🟢</Text>
              <Text style={styles.googleLoginButtonText}>
                {isGoogleLoading ? '구글 로그인 중...' : 'Google로 계속하기'}
              </Text>
            </TouchableOpacity>
          </View>

          {/* 데모용 안내 */}
          <View style={styles.demoContainer}>
            <Text style={styles.demoTitle}>📝 데모용 계정</Text>
            <Text style={styles.demoInfo}>이메일: test@test.com</Text>
            <Text style={styles.demoInfo}>비밀번호: password</Text>
          </View>

          {/* 하단 링크 */}
          <View style={styles.bottomContainer}>
            <TouchableOpacity onPress={() => router.push('/(auth)/register')}>
              <Text style={styles.linkText}>아직 계정이 없으신가요? 회원가입 →</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  keyboardContainer: {
    flex: 1,
  },
  scrollContainer: {
    flexGrow: 1,
    paddingHorizontal: 24,
  },
  headerContainer: {
    paddingTop: 20,
    paddingBottom: 40,
    position: 'relative',
  },
  backButton: {
    position: 'absolute',
    left: 0,
    top: 20,
    width: 44,
    height: 44,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 22,
    backgroundColor: '#fff',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  backButtonText: {
    fontSize: 24,
    color: '#333',
  },
  titleContainer: {
    alignItems: 'center',
    marginTop: 20,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
  },
  formContainer: {
    flex: 1,
  },
  inputContainer: {
    marginBottom: 24,
  },
  inputLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  textInput: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e0e0e0',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  loginButton: {
    backgroundColor: '#FFBF00',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 20,
    shadowColor: '#FFBF00',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
  loginButtonDisabled: {
    backgroundColor: '#ccc',
    shadowOpacity: 0,
  },
  loginButtonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
  },
  googleLoginButton: {
    backgroundColor: '#fff',
    borderWidth: 2,
    borderColor: '#4285F4',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 16,
    flexDirection: 'row',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  googleLoginIcon: {
    fontSize: 20,
    marginRight: 12,
  },
  googleLoginButtonText: {
    color: '#4285F4',
    fontSize: 16,
    fontWeight: 'bold',
  },
  dividerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 24,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#e0e0e0',
  },
  dividerText: {
    fontSize: 14,
    color: '#666',
    paddingHorizontal: 16,
    backgroundColor: '#f8f9fa',
  },
  demoContainer: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 20,
    marginTop: 32,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: '#e9ecef',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  demoTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 12,
    textAlign: 'center',
  },
  demoInfo: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    marginBottom: 4,
  },
  bottomContainer: {
    paddingVertical: 20,
    alignItems: 'center',
  },
  linkText: {
    fontSize: 14,
    color: '#FFBF00',
    fontWeight: '600',
  },
});