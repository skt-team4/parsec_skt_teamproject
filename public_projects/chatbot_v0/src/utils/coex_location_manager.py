"""
코엑스 전시용 위치 관리 모듈
사용자 현재 위치를 코엑스로 고정하고, 출발지 선택 옵션 제공
"""

from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class CoexLocationManager:
    """코엑스 전시용 위치 관리"""
    
    # 코엑스 고정 위치 정보
    COEX_LOCATION = {
        "name": "코엑스",
        "address": "서울특별시 강남구 영동대로 513",
        "lat": 37.5119,  # 코엑스 위도
        "lon": 127.0592,  # 코엑스 경도
        "district": "강남구",
        "city": "서울"
    }
    
    # 주변 주요 랜드마크 (데모용)
    LANDMARKS = {
        "코엑스": {"lat": 37.5119, "lon": 127.0592},
        "삼성역": {"lat": 37.5088, "lon": 127.0631},
        "봉은사역": {"lat": 37.5142, "lon": 127.0599},
        "선정릉역": {"lat": 37.5104, "lon": 127.0440},
        "잠실역": {"lat": 37.5132, "lon": 127.1001},
        "강남역": {"lat": 37.4979, "lon": 127.0276},
        "역삼역": {"lat": 37.5003, "lon": 127.0364}
    }
    
    def __init__(self):
        self.current_location = self.COEX_LOCATION.copy()
        self.user_selected_start = None
        logger.info(f"코엑스 전시 모드 활성화: {self.COEX_LOCATION['name']}")
    
    def get_current_location(self) -> Dict:
        """현재 위치 반환 (코엑스 고정)"""
        return self.current_location
    
    def get_coordinates(self) -> Tuple[float, float]:
        """현재 위치 좌표 반환"""
        return self.current_location["lat"], self.current_location["lon"]
    
    def set_departure_location(self, location_name: Optional[str] = None) -> Dict:
        """출발지 설정
        
        Args:
            location_name: 출발지 이름 (None이면 현재 위치 사용)
            
        Returns:
            선택된 출발지 정보
        """
        if location_name is None or location_name == "현재 위치":
            self.user_selected_start = None
            return self.current_location
        
        # 랜드마크에서 찾기
        if location_name in self.LANDMARKS:
            self.user_selected_start = {
                "name": location_name,
                "lat": self.LANDMARKS[location_name]["lat"],
                "lon": self.LANDMARKS[location_name]["lon"]
            }
            logger.info(f"출발지 설정: {location_name}")
            return self.user_selected_start
        
        # 찾을 수 없으면 기본값
        logger.warning(f"알 수 없는 위치: {location_name}, 코엑스 사용")
        return self.current_location
    
    def get_departure_location(self) -> Dict:
        """현재 설정된 출발지 반환"""
        if self.user_selected_start:
            return self.user_selected_start
        return self.current_location
    
    def create_navigation_prompt(self, shop_name: str, shop_address: str) -> str:
        """길찾기 안내 메시지 생성"""
        departure = self.get_departure_location()
        
        prompt = f"""
🗺️ [{shop_name}] 길찾기 안내

📍 목적지: {shop_address}
📍 현재 출발지: {departure['name']}

길찾기를 시작하시겠어요?
- "네" / "응" → T맵 길찾기 시작
- "다른 곳에서" → 출발지 변경
  (예: "강남역에서 출발할게")
"""
        return prompt
    
    def parse_departure_change(self, user_input: str) -> Optional[str]:
        """사용자 입력에서 출발지 변경 요청 파싱"""
        # 출발지 변경 패턴
        change_patterns = [
            "에서 출발",
            "에서 갈게",
            "에서 가려고",
            "출발지",
            "에서"
        ]
        
        for pattern in change_patterns:
            if pattern in user_input:
                # 패턴 앞의 단어를 출발지로 추출
                parts = user_input.split(pattern)
                if parts[0]:
                    location = parts[0].strip()
                    # 조사 제거
                    for suffix in ["역", "에서", "부터", "서"]:
                        if location.endswith(suffix):
                            location = location[:-len(suffix)]
                    
                    # "역" 다시 붙이기 (지하철역인 경우)
                    if location in ["삼성", "봉은사", "선정릉", "잠실", "강남", "역삼"]:
                        location = location + "역"
                    
                    return location
        
        return None
    
    def get_demo_weather_location(self) -> Dict:
        """날씨 API용 위치 정보 반환 (코엑스 고정)"""
        return {
            "city": "Seoul",
            "lat": self.COEX_LOCATION["lat"],
            "lon": self.COEX_LOCATION["lon"],
            "district": self.COEX_LOCATION["district"]
        }


# 싱글톤 인스턴스
_coex_manager = None

def get_coex_manager() -> CoexLocationManager:
    """코엑스 위치 관리자 싱글톤 인스턴스"""
    global _coex_manager
    if _coex_manager is None:
        _coex_manager = CoexLocationManager()
    return _coex_manager