"""
T맵 길찾기 연동 유틸리티
사용자 위치에서 가게까지 T맵 길찾기 URL 생성
"""

from typing import Dict, Optional, Tuple
from urllib.parse import quote
import logging
from .tmap_api import TMapRouteAPI

logger = logging.getLogger(__name__)


class TmapURLGenerator:
    """T맵 길찾기 URL 생성기"""
    
    # T맵 웹 베이스 URL
    TMAP_WEB_BASE = "https://tmap.life"
    
    # T맵 앱 딥링크 스키마
    TMAP_APP_SCHEME = "tmap://"
    
    def __init__(self):
        """T맵 URL 생성기 초기화"""
        pass
    
    def generate_web_url(self, 
                        start_lat: float, start_lng: float,
                        end_lat: float, end_lng: float,
                        start_name: str = "출발지",
                        end_name: str = "도착지",
                        route_type: str = "transit") -> str:
        """
        T맵 웹 길찾기 URL 생성
        
        Args:
            start_lat, start_lng: 출발지 좌표
            end_lat, end_lng: 도착지 좌표
            start_name: 출발지 이름
            end_name: 도착지 이름
            route_type: 경로 타입 (transit:대중교통, car:자동차, walk:도보)
            
        Returns:
            T맵 웹 URL
        """
        # URL 인코딩
        start_name_encoded = quote(start_name)
        end_name_encoded = quote(end_name)
        
        # T맵 웹 파라미터
        params = {
            'startX': start_lng,  # 경도
            'startY': start_lat,  # 위도
            'startName': start_name_encoded,
            'endX': end_lng,
            'endY': end_lat,
            'endName': end_name_encoded,
        }
        
        # 경로 타입별 URL
        if route_type == "car":
            url = f"{self.TMAP_WEB_BASE}/route"
        elif route_type == "walk":
            url = f"{self.TMAP_WEB_BASE}/walk"
        else:  # transit (대중교통)
            url = f"{self.TMAP_WEB_BASE}/transit"
        
        # 파라미터 추가
        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}?{param_str}"
        
        return full_url
    
    def generate_app_deeplink(self,
                             start_lat: float, start_lng: float,
                             end_lat: float, end_lng: float,
                             start_name: str = "출발지",
                             end_name: str = "도착지",
                             route_type: str = "transit") -> str:
        """
        T맵 앱 딥링크 생성
        
        Args:
            start_lat, start_lng: 출발지 좌표
            end_lat, end_lng: 도착지 좌표
            start_name: 출발지 이름
            end_name: 도착지 이름
            route_type: 경로 타입
            
        Returns:
            T맵 앱 딥링크 URL
        """
        # T맵 앱 딥링크 파라미터
        # rGoName: 도착지명
        # rGoX, rGoY: 도착지 좌표
        # rStName: 출발지명
        # rStX, rStY: 출발지 좌표
        
        params = {
            'rGoName': quote(end_name),
            'rGoX': end_lng,
            'rGoY': end_lat,
            'rStName': quote(start_name),
            'rStX': start_lng,
            'rStY': start_lat
        }
        
        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        deeplink = f"{self.TMAP_APP_SCHEME}?{param_str}"
        
        return deeplink
    
    def generate_universal_url(self,
                              start_lat: float, start_lng: float,
                              end_lat: float, end_lng: float,
                              start_name: str = "출발지",
                              end_name: str = "도착지",
                              route_type: str = "transit") -> Dict[str, str]:
        """
        웹과 앱 모두를 위한 URL 생성
        
        Returns:
            {'web': 웹URL, 'app': 앱딥링크}
        """
        return {
            'web': self.generate_web_url(
                start_lat, start_lng, end_lat, end_lng,
                start_name, end_name, route_type
            ),
            'app': self.generate_app_deeplink(
                start_lat, start_lng, end_lat, end_lng,
                start_name, end_name, route_type
            )
        }


class NaviyamTmapIntegration:
    """나비얌 챗봇용 T맵 통합"""
    
    def __init__(self):
        self.url_generator = TmapURLGenerator()
        # location_utils에서 좌표 가져오기
        from utils.location_utils import LOCATION_COORDINATES
        self.location_coords = LOCATION_COORDINATES
    
    def get_user_location_coords(self, location_name: str) -> Optional[Tuple[float, float]]:
        """
        사용자 위치명으로부터 좌표 획득
        
        Args:
            location_name: 위치명 (예: "강남역")
            
        Returns:
            (위도, 경도) 또는 None
        """
        # 정규화
        from utils.location_utils import normalize_location
        location_info = normalize_location(location_name)
        
        if location_info and 'lat' in location_info and 'lng' in location_info:
            return (location_info['lat'], location_info['lng'])
        
        # 직접 매핑 시도
        if location_name in self.location_coords:
            return self.location_coords[location_name]
        
        # 부분 매칭
        for loc_name, coords in self.location_coords.items():
            if location_name in loc_name or loc_name in location_name:
                return coords
        
        logger.warning(f"위치 좌표를 찾을 수 없음: {location_name}")
        return None
    
    def generate_navigation_options(self,
                                   user_location: Dict,
                                   shop_location: Dict,
                                   shop_name: str,
                                   user_location_name: str = None) -> Dict:
        """
        사용자 위치에서 가게까지 길찾기 옵션 생성
        
        Args:
            user_location: {'lat': 위도, 'lng': 경도} 또는 {'name': '강남역'}
            shop_location: {'lat': 위도, 'lng': 경도}
            shop_name: 가게 이름
            user_location_name: 사용자 위치 이름 (선택)
            
        Returns:
            길찾기 옵션 딕셔너리
        """
        # 사용자 위치 좌표 확인
        if 'lat' in user_location and 'lng' in user_location:
            user_lat = user_location['lat']
            user_lng = user_location['lng']
        elif 'name' in user_location:
            coords = self.get_user_location_coords(user_location['name'])
            if coords:
                user_lat, user_lng = coords
                user_location_name = user_location['name']
            else:
                return {'error': f"위치를 찾을 수 없습니다: {user_location['name']}"}
        else:
            return {'error': "사용자 위치 정보가 없습니다"}
        
        # 가게 위치 확인
        if not ('lat' in shop_location and 'lng' in shop_location):
            return {'error': "가게 위치 정보가 없습니다"}
        
        shop_lat = shop_location['lat']
        shop_lng = shop_location['lng']
        
        # 출발지 이름 설정
        if not user_location_name:
            user_location_name = "현재 위치"
        
        # 각 교통수단별 URL 생성
        navigation_options = {
            'transit': self.url_generator.generate_universal_url(
                user_lat, user_lng, shop_lat, shop_lng,
                user_location_name, shop_name, 'transit'
            ),
            'car': self.url_generator.generate_universal_url(
                user_lat, user_lng, shop_lat, shop_lng,
                user_location_name, shop_name, 'car'
            ),
            'walk': self.url_generator.generate_universal_url(
                user_lat, user_lng, shop_lat, shop_lng,
                user_location_name, shop_name, 'walk'
            )
        }
        
        # 사용자 친화적 응답 생성
        response = {
            'shop_name': shop_name,
            'user_location': user_location_name,
            'navigation_options': navigation_options,
            'message': self._generate_user_message(shop_name, user_location_name)
        }
        
        return response
    
    def _generate_user_message(self, shop_name: str, user_location: str) -> str:
        """사용자 친화적 메시지 생성"""
        return f"""
[T맵 길찾기] {shop_name}

출발: {user_location}
도착: {shop_name}

아래 버튼을 눌러서 T맵으로 길찾기를 시작하세요!
• 대중교통 🚇 - 지하철, 버스 이용
• 자동차 🚗 - 최적 경로 안내
• 도보 🚶 - 걸어서 가는 길

[안내]
- 모바일에서는 T맵 앱이 자동으로 실행됩니다
- PC에서는 T맵 웹사이트가 열립니다
"""


def create_navigation_button(url_dict: Dict, transport_type: str, label: str) -> Dict:
    """
    네비게이션 버튼 생성 (챗봇 UI용)
    
    Args:
        url_dict: {'web': 웹URL, 'app': 앱URL}
        transport_type: 교통수단 타입
        label: 버튼 라벨
        
    Returns:
        버튼 정보 딕셔너리
    """
    return {
        'type': 'url_button',
        'label': label,
        'web_url': url_dict['web'],
        'app_url': url_dict['app'],
        'transport_type': transport_type
    }


def create_quick_reply_buttons(navigation_options: Dict) -> list:
    """
    Quick Reply 버튼 리스트 생성
    
    Args:
        navigation_options: 네비게이션 옵션 딕셔너리
        
    Returns:
        Quick Reply 버튼 리스트
    """
    buttons = []
    
    if 'transit' in navigation_options:
        buttons.append(create_navigation_button(
            navigation_options['transit'],
            'transit',
            '🚇 대중교통'
        ))
    
    if 'car' in navigation_options:
        buttons.append(create_navigation_button(
            navigation_options['car'],
            'car',
            '🚗 자동차'
        ))
    
    if 'walk' in navigation_options:
        buttons.append(create_navigation_button(
            navigation_options['walk'],
            'walk',
            '🚶 도보'
        ))
    
    return buttons


# 간편 사용 함수
def create_tmap_navigation_response(shop_name: str, 
                                   shop_lat: float, 
                                   shop_lng: float,
                                   user_location_name: str = None,
                                   include_route_info: bool = True) -> Dict:
    """
    T맵 네비게이션 응답 생성 (간편 버전)
    
    Args:
        shop_name: 가게 이름
        shop_lat, shop_lng: 가게 좌표
        user_location_name: 사용자 위치 이름 (None이면 코엑스 사용)
        include_route_info: API를 통한 실제 경로 정보 포함 여부
        
    Returns:
        챗봇 응답용 딕셔너리
    """
    # 코엑스 전시 모드 통합
    from .coex_location_manager import get_coex_manager
    coex_mgr = get_coex_manager()
    
    # 출발지 설정
    if user_location_name:
        departure = coex_mgr.set_departure_location(user_location_name)
    else:
        departure = coex_mgr.get_departure_location()
    
    user_lat = departure.get('lat')
    user_lng = departure.get('lon') or departure.get('lng')
    user_location_name = departure.get('name', '코엑스')
    
    if not user_lat or not user_lng:
        return {
            'text': f"죄송해요, '{user_location_name}'의 위치를 찾을 수 없어요.",
            'quick_reply_buttons': []
        }
    
    # T맵 통합 객체 생성
    tmap = NaviyamTmapIntegration()
    
    # 기본 네비게이션 옵션 생성
    result = tmap.generate_navigation_options(
        user_location={'lat': user_lat, 'lng': user_lng, 'name': user_location_name},
        shop_location={'lat': shop_lat, 'lng': shop_lng},
        shop_name=shop_name,
        user_location_name=user_location_name
    )
    
    if 'error' in result:
        return {
            'text': f"죄송해요, 길찾기를 실행할 수 없어요: {result['error']}",
            'quick_reply_buttons': []
        }
    
    # API를 통한 실제 경로 정보 추가
    route_info_text = ""
    if include_route_info:
        try:
            api = TMapRouteAPI()
            if api.api_key:
                # 대중교통 정보 우선
                transit_info = api.get_route_info(user_lat, user_lng, shop_lat, shop_lng, "transit")
                car_info = api.get_route_info(user_lat, user_lng, shop_lat, shop_lng, "car")
                walk_info = api.get_route_info(user_lat, user_lng, shop_lat, shop_lng, "pedestrian")
                
                route_info_parts = []
                
                if transit_info:
                    route_info_parts.append(f"🚇 대중교통: {transit_info['time_text']} ({transit_info['distance_text']})")
                    if 'fare' in transit_info and transit_info['fare'] > 0:
                        route_info_parts[-1] += f" - {transit_info['fare']:,}원"
                
                if car_info:
                    route_info_parts.append(f"🚗 자동차: {car_info['time_text']} ({car_info['distance_text']})")
                    if 'taxi_fare' in car_info and car_info['taxi_fare'] > 0:
                        route_info_parts[-1] += f" - 택시 약 {car_info['taxi_fare']:,}원"
                
                if walk_info:
                    route_info_parts.append(f"🚶 도보: {walk_info['time_text']} ({walk_info['distance_text']})")
                
                if route_info_parts:
                    route_info_text = "\n\n📊 예상 소요시간:\n" + "\n".join(route_info_parts)
                    logger.info(f"T맵 API 경로 정보 조회 성공: {shop_name}")
            else:
                logger.info("T맵 API Key가 없어 경로 정보를 생략합니다.")
        except Exception as e:
            logger.error(f"T맵 API 조회 실패: {e}")
            # API 실패해도 기본 길찾기 링크는 제공
    
    # 최종 메시지 구성
    base_message = result['message']
    if route_info_text:
        final_message = f"{base_message}{route_info_text}\n\n아래 버튼을 눌러 상세 경로를 확인하세요! 👇"
    else:
        final_message = f"{base_message}\n\n아래 버튼을 눌러 T맵에서 경로를 확인하세요! 👇"
    
    # Web URL 추출 (첫 번째 옵션 사용)
    tmap_web_url = None
    if 'navigation_options' in result and 'transit' in result['navigation_options']:
        tmap_web_url = result['navigation_options']['transit'].get('web')
    
    return {
        'text': final_message,
        'quick_reply_buttons': create_quick_reply_buttons(result['navigation_options']),
        'metadata': {
            'has_route_info': bool(route_info_text),
            'user_location': user_location_name,
            'shop_name': shop_name,
            'tmap_web_url': tmap_web_url
        }
    }


# 테스트 함수
def test_tmap_integration():
    """T맵 통합 테스트"""
    
    print("T맵 길찾기 URL 생성 테스트")
    print("=" * 50)
    
    # 테스트 케이스
    test_cases = [
        {
            'user_location': '강남역',
            'shop_name': '맛있는 치킨집',
            'shop_lat': 37.5172,
            'shop_lng': 127.0473
        },
        {
            'user_location': '홍대입구',
            'shop_name': '홍대 파스타',
            'shop_lat': 37.5580,
            'shop_lng': 126.9270
        }
    ]
    
    tmap = NaviyamTmapIntegration()
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n테스트 {i}: {test['user_location']} → {test['shop_name']}")
        print("-" * 40)
        
        result = tmap.generate_navigation_options(
            user_location={'name': test['user_location']},
            shop_location={'lat': test['shop_lat'], 'lng': test['shop_lng']},
            shop_name=test['shop_name']
        )
        
        if 'error' in result:
            print(f"오류: {result['error']}")
        else:
            print(f"출발: {result['user_location']}")
            print(f"도착: {result['shop_name']}")
            print("\n생성된 URL:")
            for transport, urls in result['navigation_options'].items():
                print(f"\n[{transport}]")
                print(f"  웹: {urls['web'][:70]}...")
                print(f"  앱: {urls['app'][:70]}...")


if __name__ == "__main__":
    test_tmap_integration()