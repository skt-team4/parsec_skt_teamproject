"""
사용자 위치 파악 유틸리티
1. 사용자 입력에서 위치 추출
2. GPS 좌표 → 장소명 변환
"""

import re
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class UserLocationManager:
    """사용자 위치 관리"""
    
    def __init__(self):
        # 위치 키워드 패턴
        self.location_patterns = [
            r'(.+?)\s*근처',           # "강남역 근처"
            r'(.+?)\s*주변',           # "홍대 주변"
            r'(.+?)에서',              # "판교에서"
            r'(.+?)쪽(?!으로)',        # "신촌쪽" (단, "쪽으로"는 제외)
            r'(.+?)\s*근방',           # "서울역 근방"
            r'(.+?)\s*인근',           # "강남 인근"
            r'(.+?)\s*부근',           # "명동 부근"
        ]
        
        # 음식 카테고리 (위치로 인식하지 않을 단어들)
        self.food_keywords = {
            '한식', '중식', '일식', '양식', '치킨', '피자', '떡볶이', '김밥',
            '라면', '죽', '도시락', '샐러드', '디저트', '카페', '빵', '버거',
            '분식', '패스트푸드', '편의점', '마라탕', '짜장면', '짬뽕', '초밥',
            '베이커리', '브런치', '스테이크', '파스타', '리조또', '샤브샤브',
            '곱창', '막창', '족발', '보쌈', '찜닭', '불고기', '갈비', '삼겹살'
        }
        
        # 세션별 사용자 위치 저장
        self.user_locations = {}
    
    def extract_location_from_text(self, text: str) -> Optional[str]:
        """
        텍스트에서 위치 정보 추출
        
        Args:
            text: 사용자 입력 텍스트
            
        Returns:
            추출된 위치명 또는 None
        """
        # 패턴 매칭
        for pattern in self.location_patterns:
            match = re.search(pattern, text)
            if match:
                location = match.group(1).strip()
                
                # 음식 카테고리는 위치로 인식하지 않음
                if location in self.food_keywords:
                    continue
                    
                # 불필요한 조사 제거
                location = re.sub(r'[의|에|서|도|시|구|동]$', '', location)
                logger.info(f"위치 추출: '{text}' → '{location}'")
                return location
        
        # 지역명 직접 매칭 (서울 주요 지역)
        major_locations = [
            '강남', '강북', '홍대', '신촌', '명동', '종로', '이태원',
            '성수', '판교', '분당', '수원', '인천', '부천', '일산',
            '강남역', '서울역', '용산역', '신도림', '건대', '왕십리',
            '노원', '잠실', '송파', '마포', '서초', '관악', '동작'
        ]
        
        for loc in major_locations:
            if loc in text:
                logger.info(f"위치 매칭: '{text}' → '{loc}'")
                return loc
        
        return None
    
    def set_user_location(self, user_id: str, location: str = None, 
                         lat: float = None, lng: float = None):
        """
        사용자 위치 설정
        
        Args:
            user_id: 사용자 ID
            location: 위치명
            lat, lng: GPS 좌표
        """
        if user_id not in self.user_locations:
            self.user_locations[user_id] = {}
        
        if location:
            self.user_locations[user_id]['location_name'] = location
            
            # location_utils에서 좌표 가져오기
            from utils.location_utils import normalize_location
            location_info = normalize_location(location)
            if location_info:
                self.user_locations[user_id]['lat'] = location_info.get('lat')
                self.user_locations[user_id]['lng'] = location_info.get('lng')
        
        if lat and lng:
            self.user_locations[user_id]['lat'] = lat
            self.user_locations[user_id]['lng'] = lng
            
            # 좌표를 장소명으로 변환 (역지오코딩)
            if not location:
                location_name = self.reverse_geocode(lat, lng)
                if location_name:
                    self.user_locations[user_id]['location_name'] = location_name
        
        logger.info(f"사용자 위치 설정: {user_id} → {self.user_locations[user_id]}")
    
    def get_user_location(self, user_id: str) -> Optional[Dict]:
        """
        사용자 위치 가져오기
        
        Returns:
            {'location_name': str, 'lat': float, 'lng': float}
        """
        return self.user_locations.get(user_id)
    
    def reverse_geocode(self, lat: float, lng: float) -> Optional[str]:
        """
        좌표를 장소명으로 변환 (간단한 구현)
        
        Args:
            lat, lng: GPS 좌표
            
        Returns:
            가장 가까운 장소명
        """
        from utils.location_utils import LOCATION_COORDINATES
        import math
        
        min_distance = float('inf')
        closest_location = None
        
        # 가장 가까운 장소 찾기
        for name, (loc_lat, loc_lng) in LOCATION_COORDINATES.items():
            # 거리 계산 (간단한 유클리드 거리)
            distance = math.sqrt((lat - loc_lat)**2 + (lng - loc_lng)**2)
            if distance < min_distance:
                min_distance = distance
                closest_location = name
        
        # 0.01도 (약 1km) 이내면 해당 장소로 간주
        if min_distance < 0.01:
            return closest_location
        
        # 그 외는 구 단위로 표시
        if 126.8 < lng < 127.2 and 37.4 < lat < 37.7:
            if lng < 127.0:
                if lat > 37.55:
                    return "서울 서북부"
                else:
                    return "서울 서남부"
            else:
                if lat > 37.55:
                    return "서울 동북부"
                else:
                    return "서울 동남부"
        
        return "현재 위치"
    
    def update_from_user_input(self, user_id: str, user_input: str) -> bool:
        """
        사용자 입력에서 위치 정보 업데이트
        
        Returns:
            위치 정보가 업데이트되었는지 여부
        """
        location = self.extract_location_from_text(user_input)
        if location:
            self.set_user_location(user_id, location)
            return True
        return False


# 전역 인스턴스
user_location_manager = UserLocationManager()


# GPS 좌표 처리를 위한 웹 API 엔드포인트 (Flask/FastAPI 예시)
def create_location_endpoint():
    """
    웹 환경에서 GPS 좌표를 받기 위한 엔드포인트 예시
    실제 구현은 웹 프레임워크에 따라 다름
    """
    example_js = """
    // 프론트엔드 JavaScript 예시
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                // 서버로 좌표 전송
                fetch('/api/location', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        user_id: 'current_user',
                        lat: position.coords.latitude,
                        lng: position.coords.longitude
                    })
                });
            },
            function(error) {
                console.error('위치 정보를 가져올 수 없습니다:', error);
            }
        );
    }
    """
    
    example_api = """
    from flask import Flask, request, jsonify
    
    app = Flask(__name__)
    
    @app.route('/api/location', methods=['POST'])
    def update_location():
        data = request.json
        user_id = data.get('user_id')
        lat = data.get('lat')
        lng = data.get('lng')
        
        # 위치 업데이트
        user_location_manager.set_user_location(user_id, lat=lat, lng=lng)
        
        return jsonify({'status': 'success'})
    """
    
    return example_js, example_api


# 테스트 함수
def test_location_extraction():
    """위치 추출 테스트"""
    manager = UserLocationManager()
    
    test_cases = [
        "강남역 근처 맛집 추천해줘",
        "홍대 주변에 치킨집 있어?",
        "판교에서 점심 먹을 곳",
        "신촌쪽 카페 알려줘",
        "서울역 근방 한식당",
        "명동 인근 맛집",
        "이태원 부근 양식당",
        "맛집 추천해줘",  # 위치 없음
    ]
    
    print("=" * 60)
    print("위치 추출 테스트")
    print("=" * 60)
    
    for text in test_cases:
        location = manager.extract_location_from_text(text)
        print(f"입력: {text}")
        print(f"  → 위치: {location if location else '없음'}")
        print()
    
    # GPS 좌표 테스트
    print("\nGPS 좌표 → 장소명 변환")
    print("-" * 40)
    
    test_coords = [
        (37.497952, 127.027619),  # 강남역
        (37.557192, 126.925381),  # 홍대입구역
        (37.566535, 126.977969),  # 서울시청
    ]
    
    for lat, lng in test_coords:
        place = manager.reverse_geocode(lat, lng)
        print(f"좌표: ({lat:.6f}, {lng:.6f})")
        print(f"  → 장소: {place}")
        print()


if __name__ == "__main__":
    test_location_extraction()