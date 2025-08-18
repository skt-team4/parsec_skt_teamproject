"""
T맵 경로 API 클라이언트
실제 경로 시간/거리 정보를 가져오는 모듈
"""

import os
import requests
import logging
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class TMapRouteAPI:
    """T맵 경로 API 클라이언트"""
    
    # API 엔드포인트
    BASE_URL = "https://apis.openapi.sk.com"
    ROUTE_CAR = "/tmap/routes"  # 자동차
    ROUTE_PEDESTRIAN = "/tmap/routes/pedestrian"  # 도보
    ROUTE_TRANSIT = "/transit/routes"  # 대중교통
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: T맵 API Key (없으면 환경변수에서 읽음)
        """
        self.api_key = api_key or os.getenv('TMAP_API_KEY')
        
        if not self.api_key:
            logger.warning("T맵 API Key가 설정되지 않았습니다. .env 파일에 TMAP_API_KEY를 추가하세요.")
    
    def get_route_info(self, 
                      start_lat: float, start_lng: float,
                      end_lat: float, end_lng: float,
                      route_type: str = "car") -> Optional[Dict]:
        """
        경로 정보 조회 (시간, 거리)
        
        Args:
            start_lat, start_lng: 출발지 좌표
            end_lat, end_lng: 도착지 좌표
            route_type: 경로 타입 ("car", "pedestrian", "transit")
            
        Returns:
            {
                "distance": 거리(미터),
                "time": 시간(초),
                "distance_text": "2.1km",
                "time_text": "15분",
                "fare": 택시요금(원) - 자동차만
            }
        """
        if not self.api_key:
            logger.error("API Key가 없어 경로 정보를 가져올 수 없습니다.")
            return None
        
        try:
            # 엔드포인트 선택
            if route_type == "pedestrian":
                endpoint = self.ROUTE_PEDESTRIAN
            elif route_type == "transit":
                endpoint = self.ROUTE_TRANSIT
            else:
                endpoint = self.ROUTE_CAR
            
            url = f"{self.BASE_URL}{endpoint}"
            
            # 헤더 설정 (appKey만 필요)
            headers = {
                "appKey": self.api_key
            }
            
            # 자동차/도보 API 파라미터
            if route_type != "transit":
                if route_type == "pedestrian":
                    # 도보는 필수 파라미터가 다름
                    params = {
                        "version": "1",
                        "startX": str(start_lng),
                        "startY": str(start_lat),
                        "endX": str(end_lng),
                        "endY": str(end_lat),
                        "startName": "출발지",
                        "endName": "도착지",
                        "reqCoordType": "WGS84GEO",
                        "resCoordType": "WGS84GEO"
                    }
                else:
                    # 자동차
                    params = {
                        "version": "1",
                        "startX": str(start_lng),
                        "startY": str(start_lat),
                        "endX": str(end_lng),
                        "endY": str(end_lat),
                        "reqCoordType": "WGS84GEO",
                        "resCoordType": "WGS84GEO",
                        "searchOption": "0"  # 최적 경로
                    }
                
                # POST 요청 (form-data로 전송)
                response = requests.post(url, headers=headers, data=params, timeout=5)
                
            else:
                # 대중교통 API는 GET 요청
                params = {
                    "startX": str(start_lng),
                    "startY": str(start_lat),
                    "endX": str(end_lng),
                    "endY": str(end_lat),
                    "format": "json",
                    "count": "1"  # 결과 1개만
                }
                
                # GET 요청 (대중교통은 GET)
                response = requests.get(url, headers=headers, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_route_response(data, route_type)
            else:
                logger.error(f"T맵 API 오류: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("T맵 API 요청 시간 초과")
            return None
        except Exception as e:
            logger.error(f"T맵 API 호출 실패: {e}")
            return None
    
    def _parse_route_response(self, data: Dict, route_type: str) -> Optional[Dict]:
        """응답 데이터 파싱"""
        try:
            if route_type == "transit":
                # 대중교통 응답 파싱
                if "itineraries" in data and len(data["itineraries"]) > 0:
                    itinerary = data["itineraries"][0]
                    
                    total_time = itinerary.get("totalTime", 0)  # 초
                    total_distance = itinerary.get("totalDistance", 0)  # 미터
                    fare = itinerary.get("fare", {}).get("regular", {}).get("totalFare", 0)
                    
                    return {
                        "distance": total_distance,
                        "time": total_time,
                        "distance_text": self._format_distance(total_distance),
                        "time_text": self._format_time(total_time),
                        "fare": fare,
                        "type": "transit"
                    }
            else:
                # 자동차/도보 응답 파싱
                if "features" in data and len(data["features"]) > 0:
                    # 첫 번째 feature에 전체 경로 정보가 있음
                    properties = data["features"][0].get("properties", {})
                    
                    total_distance = properties.get("totalDistance", 0)  # 미터
                    total_time = properties.get("totalTime", 0)  # 초
                    
                    result = {
                        "distance": total_distance,
                        "time": total_time,
                        "distance_text": self._format_distance(total_distance),
                        "time_text": self._format_time(total_time),
                        "type": route_type
                    }
                    
                    # 자동차인 경우 택시 요금 추가
                    if route_type == "car":
                        result["taxi_fare"] = properties.get("taxiFare", 0)
                        result["toll_fare"] = properties.get("totalFare", 0)  # 통행료
                    
                    return result
            
            logger.warning(f"예상치 못한 응답 형식: {route_type}")
            return None
            
        except Exception as e:
            logger.error(f"응답 파싱 실패: {e}")
            return None
    
    def _format_distance(self, meters: int) -> str:
        """거리 포맷팅"""
        if meters < 1000:
            return f"{meters}m"
        else:
            km = meters / 1000
            return f"{km:.1f}km"
    
    def _format_time(self, seconds: int) -> str:
        """시간 포맷팅"""
        if seconds < 60:
            return f"{seconds}초"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}분"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                return f"{hours}시간 {minutes}분"
            else:
                return f"{hours}시간"
    
    def get_multi_route_info(self,
                           start_lat: float, start_lng: float,
                           end_lat: float, end_lng: float) -> Dict:
        """
        모든 이동수단의 경로 정보 한번에 조회
        
        Returns:
            {
                "car": {...},
                "pedestrian": {...},
                "transit": {...}
            }
        """
        results = {}
        
        for route_type in ["car", "pedestrian", "transit"]:
            info = self.get_route_info(start_lat, start_lng, end_lat, end_lng, route_type)
            if info:
                results[route_type] = info
        
        return results


# 테스트 함수
def test_tmap_route():
    """T맵 경로 API 테스트"""
    
    # API 클라이언트 생성
    api = TMapRouteAPI()
    
    if not api.api_key:
        print("❌ T맵 API Key가 설정되지 않았습니다.")
        print("📝 .env 파일에 다음을 추가하세요:")
        print("   TMAP_API_KEY=your_api_key_here")
        return
    
    # 테스트 좌표 (강남역 → 판교역)
    start_lat, start_lng = 37.497952, 127.027619  # 강남역
    end_lat, end_lng = 37.394765, 127.111202  # 판교역
    
    print("=" * 60)
    print("T맵 경로 API 테스트")
    print("=" * 60)
    print(f"출발: 강남역 ({start_lat}, {start_lng})")
    print(f"도착: 판교역 ({end_lat}, {end_lng})")
    print("-" * 60)
    
    # 자동차 경로
    print("\n🚗 자동차 경로:")
    car_info = api.get_route_info(start_lat, start_lng, end_lat, end_lng, "car")
    if car_info:
        print(f"  거리: {car_info['distance_text']}")
        print(f"  시간: {car_info['time_text']}")
        if 'taxi_fare' in car_info:
            print(f"  예상 택시요금: {car_info['taxi_fare']:,}원")
    else:
        print("  ❌ 조회 실패")
    
    # 도보 경로
    print("\n🚶 도보 경로:")
    walk_info = api.get_route_info(start_lat, start_lng, end_lat, end_lng, "pedestrian")
    if walk_info:
        print(f"  거리: {walk_info['distance_text']}")
        print(f"  시간: {walk_info['time_text']}")
    else:
        print("  ❌ 조회 실패")
    
    # 대중교통 경로
    print("\n🚌 대중교통 경로:")
    transit_info = api.get_route_info(start_lat, start_lng, end_lat, end_lng, "transit")
    if transit_info:
        print(f"  거리: {transit_info['distance_text']}")
        print(f"  시간: {transit_info['time_text']}")
        if 'fare' in transit_info:
            print(f"  요금: {transit_info['fare']:,}원")
    else:
        print("  ❌ 조회 실패")


if __name__ == "__main__":
    test_tmap_route()