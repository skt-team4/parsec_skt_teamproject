"""
간단한 날씨 서비스 - 코엑스 전시용
OpenWeatherMap API 사용 (빠른 구현용)
"""

import os
import requests
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SimpleWeatherService:
    """코엑스 전시용 간단한 날씨 서비스"""
    
    def __init__(self):
        # API 키 (무료 계정용)
        self.api_key = os.getenv('OPENWEATHERMAP_API_KEY', '72cade2afd8d0b233391812e15fda078')
        
        # 서울 위치 (기본값)
        self.SEOUL_LAT = 37.5665
        self.SEOUL_LON = 126.9780
        
        # API URL
        self.weather_url = "https://api.openweathermap.org/data/2.5/weather"
        
    def get_weather(self, lat: float = None, lon: float = None) -> Dict:
        """현재 날씨 조회"""
        try:
            # 위치 지정이 없으면 서울 기본값 사용
            if lat is None or lon is None:
                lat = self.SEOUL_LAT
                lon = self.SEOUL_LON
            
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': 'metric',  # 섭씨 온도
                'lang': 'kr'  # 한국어 설명
            }
            
            response = requests.get(self.weather_url, params=params, timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                
                # 날씨 정보 파싱
                weather_info = {
                    'temperature': round(data['main']['temp']),
                    'feels_like': round(data['main']['feels_like']),
                    'condition': data['weather'][0]['main'],
                    'description': data['weather'][0]['description'],
                    'humidity': data['main']['humidity'],
                    'is_raining': 'rain' in data,
                    'is_hot': data['main']['temp'] > 28,
                    'is_cold': data['main']['temp'] < 10
                }
                
                logger.debug(f"날씨 조회 성공: {weather_info['temperature']}°C, {weather_info['description']}")
                return weather_info
                
        except Exception as e:
            logger.warning(f"날씨 API 실패, 기본값 사용: {e}")
        
        # API 실패 시 기본값 (전시용)
        return {
            'temperature': 22,
            'feels_like': 22,
            'condition': 'Clear',
            'description': '맑음',
            'humidity': 60,
            'is_raining': False,
            'is_hot': False,
            'is_cold': False
        }
    
    def get_food_context(self) -> Dict:
        """날씨 기반 음식 추천 컨텍스트"""
        weather = self.get_weather()
        
        context = {
            'preferred_categories': [],
            'keywords': [],
            'message': "",
            'weather_info': weather
        }
        
        # 날씨별 추천 로직
        if weather['is_raining'] or 'rain' in weather['description'].lower():
            context['preferred_categories'] = ['한식', '분식']
            context['keywords'] = ['파전', '전', '국물']
            context['message'] = "비 오는 날엔 파전이지!"
            
        elif weather['is_hot']:
            context['preferred_categories'] = ['카페', '디저트', '일식']
            context['keywords'] = ['냉면', '빙수', '아이스', '냉']
            context['message'] = f"오늘 {weather['temperature']}도야! 시원한 거 어때?"
            
        elif weather['is_cold']:
            context['preferred_categories'] = ['한식', '찜탕', '일식']
            context['keywords'] = ['국물', '뜨거운', '라멘', '우동', '탕']
            context['message'] = f"추운 날씨네! 뜨끈한 국물 어때?"
            
        else:
            # 보통 날씨
            context['message'] = f"오늘 날씨 좋네! 뭐든 맛있겠다~"
            
        return context


# 싱글톤 인스턴스
_weather_service = None

def get_weather_service() -> SimpleWeatherService:
    """날씨 서비스 싱글톤"""
    global _weather_service
    if _weather_service is None:
        _weather_service = SimpleWeatherService()
    return _weather_service


def get_weather_message() -> str:
    """간단한 날씨 메시지 반환"""
    service = get_weather_service()
    context = service.get_food_context()
    weather = context['weather_info']
    
    # 날씨 정보를 포함한 인사말
    message = f"현재 코엑스 {weather['temperature']}도, {weather['description']}\n"
    if context['message']:
        message += context['message']
    
    return message