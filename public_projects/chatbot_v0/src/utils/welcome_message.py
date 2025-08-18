"""
나비얌 챗봇 환영 메시지 생성기
날짜, 시간, 날씨 정보를 포함한 다양한 환영 메시지 제공
"""

import random
import requests
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class WelcomeMessageGenerator:
    """환영 메시지 생성기"""
    
    def __init__(self, weather_api_key: Optional[str] = None):
        """
        Args:
            weather_api_key: OpenWeatherMap API 키 (선택사항)
        """
        self.weather_api_key = weather_api_key
        
        # 시간대별 메시지 템플릿
        self.time_messages = {
            "morning": [
                " 좋은 아침이에요! 오늘도 맛있는 하루 시작해볼까요?",
                " 활기찬 아침이네요! 든든한 아침식사는 어떠세요?",
                " 상쾌한 아침입니다! 맛있는 브런치 어떠세요?",
                "️ 새로운 하루의 시작! 오늘은 어떤 맛집을 찾아볼까요?",
                " 좋은 아침이에요! 오늘 첫 끼니를 함께 찾아드릴게요!"
            ],
            "afternoon": [
                " 따뜻한 오후네요! 점심은 드셨나요?",
                " 화창한 오후입니다! 간단한 간식은 어떠세요?",
                " 여유로운 오후시간이네요! 달콤한 디저트 어떠세요?",
                " 바쁜 오후시간! 간편한 식사 추천해드릴게요!",
                "️ 포근한 오후예요! 맛있는 것 드시러 가볼까요?"
            ],
            "evening": [
                " 하루 마무리 시간이네요! 저녁식사 준비해볼까요?",
                " 오늘 하루 고생하셨어요! 맛있는 저녁 어떠세요?",
                "️ 따뜻한 저녁시간이에요! 특별한 만찬은 어떠세요?",
                " 편안한 저녁입니다! 든든한 저녁식사 함께 찾아볼게요!",
                " 하루의 마무리! 맛있는 저녁으로 기분 좋게 마무리해요!"
            ],
            "night": [
                " 늦은 시간이네요! 간단한 야식은 어떠세요?",
                " 고요한 밤시간이에요! 달콤한 야식 어떠세요?",
                " 야식이 생각나는 시간이네요! 맛있는 것 찾아드릴게요!",
                " 배고픈 밤이에요! 따뜻한 야식 추천해드릴게요!",
                " 달콤한 밤! 특별한 야식으로 하루를 마무리해볼까요?"
            ]
        }
        
        # 날씨별 메시지
        self.weather_messages = {
            "sunny": [" 맑고 화창한 날씨네요!", " 따사로운 햇살이 좋아요!", " 완벽한 나들이 날씨예요!"],
            "cloudy": [" 구름이 낀 하루네요!", "️ 차분한 날씨예요!", " 포근한 구름 하늘이네요!"],
            "rainy": ["️ 비 오는 날이네요!", " 촉촉한 비가 내려요!", "️ 비 때문에 집에 있고 싶어져요!"],
            "snowy": [" 눈 오는 날이에요!", " 하얀 눈이 예뻐요!", " 겨울 분위기가 물씬!"],
            "cold": [" 쌀쌀한 날씨네요!", " 추운 하루예요!", " 따뜻한 게 생각나는 날씨!"],
            "hot": [" 더운 날씨네요!", "️ 시원한 게 생각나요!", " 무더운 여름이에요!"]
        }
        
        # 요일별 메시지  
        self.weekday_messages = {
            "monday": [" 월요일 화이팅!", " 새로운 한 주 시작!", " 월요병을 날려버려요!"],
            "tuesday": [" 화요일도 힘내요!", " 이번 주 잘 가고 있어요!", " 오늘도 좋은 하루!"],
            "wednesday": [" 수요일 절반 왔어요!", " 수요일 에너지 충전!", " 한 주의 중간점!"],
            "thursday": [" 목요일! 거의 다 왔어요!", " 주말이 코앞!", " 목요일도 즐겁게!"],
            "friday": [" 불금이에요!", " 주말 앞둔 금요일!", " TGIF! 즐거운 금요일!"],
            "saturday": ["️ 즐거운 토요일!", " 여유로운 주말!", "️ 토요일 나들이 어떠세요?"],
            "sunday": [" 편안한 일요일!", " 느긋한 휴일!", " 일요일 여유시간!"]
        }
        
        # 특별한 날 메시지
        self.special_day_messages = {
            "new_year": " 새해 복 많이 받으세요!",
            "valentine": " 발렌타인데이! 달콤한 하루!",
            "white_day": " 화이트데이! 특별한 하루!",
            "children_day": " 어린이날! 맛있는 것 많이 드세요!",
            "christmas": " 메리 크리스마스!",
            "birthday": " 생일 축하해요!"
        }

    def get_current_time_period(self) -> str:
        """현재 시간대 반환"""
        hour = datetime.now().hour
        
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon" 
        elif 17 <= hour < 22:
            return "evening"
        else:
            return "night"

    def get_current_weekday(self) -> str:
        """현재 요일 반환"""
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        return weekdays[datetime.now().weekday()]

    def get_weather_info(self, city: str = "Seoul") -> Dict[str, str]:
        """날씨 정보 가져오기"""
        if not self.weather_api_key:
            return {"condition": "unknown", "temperature": "?", "description": "날씨 정보를 가져올 수 없어요"}
        
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": city,
                "appid": self.weather_api_key,
                "units": "metric",
                "lang": "kr"
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                weather = data["weather"][0]
                main = data["main"]
                
                # 날씨 상태 매핑
                condition_map = {
                    "clear": "sunny",
                    "clouds": "cloudy", 
                    "rain": "rainy",
                    "drizzle": "rainy",
                    "thunderstorm": "rainy",
                    "snow": "snowy",
                    "mist": "cloudy",
                    "fog": "cloudy"
                }
                
                condition = condition_map.get(weather["main"].lower(), "cloudy")
                temp = int(main["temp"])
                
                # 온도 기반 조건 추가
                if temp < 5:
                    condition = "cold"
                elif temp > 28:
                    condition = "hot"
                
                return {
                    "condition": condition,
                    "temperature": f"{temp}°C",
                    "description": weather["description"]
                }
                
        except Exception as e:
            logger.warning(f"날씨 정보 가져오기 실패: {e}")
        
        return {"condition": "unknown", "temperature": "?", "description": "날씨 정보를 가져올 수 없어요"}

    def get_date_info(self) -> Dict[str, str]:
        """날짜 정보 반환"""
        now = datetime.now()
        
        weekday_kr = ["월", "화", "수", "목", "금", "토", "일"]
        weekday_name = weekday_kr[now.weekday()]
        
        return {
            "date": now.strftime("%Y년 %m월 %d일"),
            "weekday": f"{weekday_name}요일",
            "time": now.strftime("%H시 %M분")
        }

    def check_special_day(self) -> Optional[str]:
        """특별한 날 확인"""
        now = datetime.now()
        month, day = now.month, now.day
        
        special_days = {
            (1, 1): "new_year",
            (2, 14): "valentine", 
            (3, 14): "white_day",
            (5, 5): "children_day",
            (12, 25): "christmas"
        }
        
        return special_days.get((month, day))

    def generate_welcome_message(self, city: str = "Seoul", include_weather: bool = True) -> str:
        """환영 메시지 생성"""
        
        # 기본 정보 수집
        time_period = self.get_current_time_period()
        weekday = self.get_current_weekday()
        date_info = self.get_date_info()
        special_day = self.check_special_day()
        
        # 메시지 구성 요소들
        message_parts = []
        
        # 1. 날짜와 시간 정보
        message_parts.append(f"[{date_info['date']} {date_info['weekday']}, {date_info['time']}]")
        
        # 2. 특별한 날 확인
        if special_day:
            message_parts.append(self.special_day_messages[special_day])
        
        # 3. 날씨 정보 (옵션)
        if include_weather:
            weather_info = self.get_weather_info(city)
            if weather_info["condition"] != "unknown":
                weather_msg = random.choice(self.weather_messages[weather_info["condition"]])
                message_parts.append(f"{weather_msg} 현재 {weather_info['temperature']}")
        
        # 4. 시간대별 인사
        time_greeting = random.choice(self.time_messages[time_period])
        message_parts.append(time_greeting)
        
        # 5. 요일별 메시지 (가끔)
        if random.random() < 0.3:  # 30% 확률
            weekday_msg = random.choice(self.weekday_messages[weekday])
            message_parts.append(weekday_msg)
        
        # 6. 챗봇 소개
        intro_messages = [
            "나비얌이 맛있는 착한가게를 찾아드릴게요!",
            " 오늘도 최고의 맛집을 추천해드릴게요!",
            " 여러분의 입맛에 딱 맞는 가게를 찾아볼까요?",
            " 맛있고 착한 가게들이 기다리고 있어요!",
            " 나비얌과 함께 맛있는 여행 떠나요!"
        ]
        message_parts.append(random.choice(intro_messages))
        
        return "\n".join(message_parts)

    def generate_simple_welcome(self) -> str:
        """간단한 환영 메시지 (날씨 API 없이)"""
        return self.generate_welcome_message(include_weather=False)

    def generate_custom_welcome(self, user_name: str = None, preferences: List[str] = None) -> str:
        """개인화된 환영 메시지"""
        base_message = self.generate_welcome_message(include_weather=False)
        
        custom_parts = []
        
        if user_name:
            custom_parts.append(f"{user_name}님, 다시 만나서 반가워요!")
        
        if preferences and user_name and user_name.lower() != "guest":
            pref_text = ", ".join(preferences[:2])  # 최대 2개까지
            custom_parts.append(f"평소 좋아하시는 {pref_text} 맛집도 준비되어 있어요!")
        
        if custom_parts:
            custom_message = "\n".join(custom_parts)
            return f"{custom_message}\n\n{base_message}"
        
        return base_message


def create_welcome_generator(weather_api_key: Optional[str] = None) -> WelcomeMessageGenerator:
    """환영 메시지 생성기 생성 (편의 함수)"""
    return WelcomeMessageGenerator(weather_api_key)


def get_quick_welcome() -> str:
    """빠른 환영 메시지 (API 키 없이)"""
    generator = WelcomeMessageGenerator()
    return generator.generate_simple_welcome()


# 테스트용 함수
if __name__ == "__main__":
    # 테스트 실행
    generator = WelcomeMessageGenerator()
    
    print("=== 기본 환영 메시지 ===")
    print(generator.generate_simple_welcome())
    
    print("\n=== 개인화 환영 메시지 ===")
    print(generator.generate_custom_welcome("김철수", ["치킨", "피자"]))
    
    print("\n=== 날씨 포함 환영 메시지 (API 키 필요) ===")
    # generator_with_weather = WelcomeMessageGenerator("your_api_key_here")
    # print(generator_with_weather.generate_welcome_message())