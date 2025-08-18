import * as WebBrowser from 'expo-web-browser';
import * as Google from 'expo-auth-session/providers/google';
import { makeRedirectUri } from 'expo-auth-session';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

WebBrowser.maybeCompleteAuthSession();

// Redirect URI 생성
export const redirectUri = makeRedirectUri({
  scheme: undefined, // 웹에서는 scheme을 사용하지 않음
  preferLocalhost: true,
  isTripleSlashed: false,
  path: 'redirect'
});

console.log('Redirect URI:', redirectUri);

// Google OAuth 설정
const googleConfig = {
  clientId: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID || '',
  iosClientId: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID || '',
  androidClientId: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID || '',
  webClientId: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID || '',
  scopes: ['openid', 'profile', 'email'],
  redirectUri,
};

export interface GoogleUser {
  id: string;
  email: string;
  name: string;
  picture?: string;
  givenName?: string;
  familyName?: string;
}

class GoogleAuthService {
  private static instance: GoogleAuthService;

  private constructor() {}

  static getInstance(): GoogleAuthService {
    if (!GoogleAuthService.instance) {
      GoogleAuthService.instance = new GoogleAuthService();
    }
    return GoogleAuthService.instance;
  }

  // Google 로그인 요청 생성
  createAuthRequest() {
    const [request, response, promptAsync] = Google.useAuthRequest(googleConfig);
    return { request, response, promptAsync };
  }

  // 액세스 토큰으로 사용자 정보 가져오기
  async getUserInfo(accessToken: string): Promise<GoogleUser | null> {
    try {
      const response = await fetch(
        'https://www.googleapis.com/oauth2/v2/userinfo',
        {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        }
      );

      if (response.ok) {
        const userInfo = await response.json();
        return {
          id: userInfo.id,
          email: userInfo.email,
          name: userInfo.name,
          picture: userInfo.picture,
          givenName: userInfo.given_name,
          familyName: userInfo.family_name,
        };
      }
      return null;
    } catch (error) {
      console.error('Error fetching user info:', error);
      return null;
    }
  }

  // 로그인 처리
  async handleGoogleLogin(response: any): Promise<{
    success: boolean;
    user?: GoogleUser;
    error?: string;
  }> {
    try {
      if (response?.type === 'success') {
        const { authentication } = response;
        
        if (authentication?.accessToken) {
          // 사용자 정보 가져오기
          const userInfo = await this.getUserInfo(authentication.accessToken);
          
          if (userInfo) {
            // 토큰과 사용자 정보 저장
            await this.saveAuthData({
              accessToken: authentication.accessToken,
              refreshToken: authentication.refreshToken,
              user: userInfo,
            });

            // 백엔드 서버에 로그인 정보 전송
            await this.sendLoginToBackend(userInfo, authentication.accessToken);

            return { success: true, user: userInfo };
          }
        }
      }
      
      return { 
        success: false, 
        error: response?.type === 'cancel' ? '로그인이 취소되었습니다.' : '로그인에 실패했습니다.' 
      };
    } catch (error) {
      console.error('Google login error:', error);
      return { success: false, error: '로그인 처리 중 오류가 발생했습니다.' };
    }
  }

  // 백엔드 서버에 로그인 정보 전송
  private async sendLoginToBackend(user: GoogleUser, accessToken: string) {
    try {
      const response = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/auth/google`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          googleId: user.id,
          email: user.email,
          name: user.name,
          picture: user.picture,
          accessToken,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        // 서버에서 받은 JWT 토큰 저장
        if (data.token) {
          await AsyncStorage.setItem('jwt_token', data.token);
        }
        return data;
      }
    } catch (error) {
      console.error('Error sending login to backend:', error);
      // 백엔드 연결 실패해도 로컬 로그인은 성공으로 처리
    }
  }

  // 인증 데이터 저장
  private async saveAuthData(data: any) {
    try {
      await AsyncStorage.setItem('google_auth', JSON.stringify(data));
      await AsyncStorage.setItem('user_info', JSON.stringify(data.user));
    } catch (error) {
      console.error('Error saving auth data:', error);
    }
  }

  // 로그아웃
  async logout() {
    try {
      await AsyncStorage.multiRemove(['google_auth', 'user_info', 'jwt_token']);
      return { success: true };
    } catch (error) {
      console.error('Error during logout:', error);
      return { success: false, error: '로그아웃 처리 중 오류가 발생했습니다.' };
    }
  }

  // 현재 로그인된 사용자 정보 가져오기
  async getCurrentUser(): Promise<GoogleUser | null> {
    try {
      const userInfo = await AsyncStorage.getItem('user_info');
      if (userInfo) {
        return JSON.parse(userInfo);
      }
      return null;
    } catch (error) {
      console.error('Error getting current user:', error);
      return null;
    }
  }

  // 로그인 상태 확인
  async isLoggedIn(): Promise<boolean> {
    try {
      const authData = await AsyncStorage.getItem('google_auth');
      return authData !== null;
    } catch (error) {
      console.error('Error checking login status:', error);
      return false;
    }
  }
}

export default GoogleAuthService.getInstance();