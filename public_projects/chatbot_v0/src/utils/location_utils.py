"""
위치 기반 필터링 유틸리티
주요 지역 좌표 및 거리 계산 기능
"""

import math
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
import os
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# 서울, 경기, 인천 주요 지역 좌표 (위도, 경도)
LOCATION_COORDINATES = {
    # === 서울 주요 역/지역 ===
    # 강남/서초
    "강남역": (37.497952, 127.027619),
    "강남": (37.5172, 127.0473),
    "역삼": (37.4954, 127.0331),
    "선릉": (37.5045, 127.0486),
    "삼성": (37.5140, 127.0630),
    "논현": (37.5112, 127.0216),
    "신논현": (37.5048, 127.0247),
    "서초": (37.4837, 127.0324),
    "교대": (37.4930, 127.0142),
    "방배": (37.4815, 126.9975),
    
    # 강북 주요 지역
    "명동": (37.5636, 126.9864),
    "을지로": (37.5660, 126.9910),
    "종로": (37.5704, 126.9792),
    "시청": (37.5663, 126.9779),
    "광화문": (37.5718, 126.9768),
    "경복궁": (37.5796, 126.9770),
    "안국": (37.5761, 126.9858),
    "인사동": (37.5741, 126.9869),
    
    # 홍대/신촌/마포
    "홍대": (37.5572, 126.9254),
    "홍대입구": (37.5572, 126.9254),
    "신촌": (37.5547, 126.9369),
    "이대": (37.5599, 126.9457),
    "합정": (37.5495, 126.9138),
    "상수": (37.5477, 126.9227),
    "망원": (37.5560, 126.9020),
    "마포": (37.5434, 126.9489),
    
    # 강동/송파
    "잠실": (37.5132, 127.1001),
    "석촌": (37.5057, 127.1065),
    "송파": (37.5146, 127.1055),
    "문정": (37.4860, 127.1229),
    "가락시장": (37.4921, 127.1184),
    "오금": (37.5023, 127.1280),
    "천호": (37.5387, 127.1237),
    "강동": (37.5301, 127.1238),
    
    # 노원/도봉/강북
    "노원": (37.6550, 127.0613),
    "수락산": (37.6770, 127.0550),
    "창동": (37.6530, 127.0479),
    "도봉": (37.6894, 127.0467),
    "쌍문": (37.6485, 127.0347),
    "수유": (37.6388, 127.0253),
    "미아": (37.6276, 127.0280),
    
    # 영등포/구로/금천
    "영등포": (37.5156, 126.9075),
    "여의도": (37.5219, 126.9245),
    "신림": (37.4844, 126.9298),
    "구로": (37.4954, 126.8874),
    "구로디지털단지": (37.4851, 126.9017),
    "가산디지털단지": (37.4782, 126.8897),
    "금천구청": (37.4569, 126.8954),
    
    # 성북/성동/용산
    "성신여대": (37.5926, 127.0163),
    "한성대": (37.5883, 127.0060),
    "왕십리": (37.5615, 127.0375),
    "성수": (37.5447, 127.0557),
    "건대입구": (37.5404, 127.0693),
    "용산": (37.5300, 126.9647),
    "이태원": (37.5347, 126.9945),
    "한남": (37.5290, 127.0093),
    
    # === 경기도 주요 지역 ===
    # 성남/분당
    "분당": (37.3826, 127.1223),
    "판교": (37.3948, 127.1113),
    "정자": (37.3660, 127.1084),
    "서현": (37.3850, 127.1229),
    "수내": (37.3784, 127.1146),
    "야탑": (37.4114, 127.1282),
    "모란": (37.4322, 127.1290),
    "성남": (37.4200, 127.1267),
    
    # 수원
    "수원": (37.2636, 127.0286),
    "수원역": (37.2658, 126.9996),
    "영통": (37.2518, 127.0710),
    "광교": (37.2873, 127.0447),
    "화서": (37.2842, 126.9897),
    "매탄": (37.2429, 127.0521),
    
    # 용인
    "용인": (37.2411, 127.1776),
    "수지": (37.3218, 127.0971),
    "죽전": (37.3247, 127.1074),
    "기흥": (37.2800, 127.1147),
    "동백": (37.2691, 127.1523),
    
    # 고양/일산
    "일산": (37.6582, 126.7699),
    "주엽": (37.6703, 126.7614),
    "정발산": (37.6597, 126.7732),
    "마두": (37.6521, 126.7778),
    "백석": (37.6431, 126.7876),
    "화정": (37.6342, 126.8327),
    "행신": (37.6120, 126.8340),
    
    # 안양/군포/의왕
    "안양": (37.3943, 126.9568),
    "평촌": (37.3943, 126.9765),
    "범계": (37.3901, 126.9507),
    "산본": (37.3584, 126.9313),
    "군포": (37.3616, 126.9351),
    "의왕": (37.3447, 126.9686),
    
    # 부천
    "부천": (37.5037, 126.7660),
    "부천시청": (37.5037, 126.7660),
    "상동": (37.5058, 126.7531),
    "중동": (37.5036, 126.7641),
    "송내": (37.4875, 126.7530),
    
    # 안산/시흥
    "안산": (37.3219, 126.8309),
    "중앙": (37.3199, 126.8309),
    "상록수": (37.3024, 126.8666),
    "시흥": (37.3800, 126.8028),
    "정왕": (37.3515, 126.7428),
    
    # 파주/김포
    "파주": (37.7595, 126.7802),
    "운정": (37.7272, 126.7476),
    "금촌": (37.7665, 126.7749),
    "김포": (37.6154, 126.7156),
    "김포공항": (37.5619, 126.8015),
    
    # 하남/광주/양평
    "하남": (37.5395, 127.2137),
    "미사": (37.5606, 127.1854),
    "광주": (37.4295, 127.2554),
    "양평": (37.4892, 127.4912),
    
    # === 인천 주요 지역 ===
    "인천": (37.4563, 126.7052),
    "부평": (37.5076, 126.7218),
    "부평구청": (37.5074, 126.7218),
    "주안": (37.4647, 126.6810),
    "간석": (37.4643, 126.6938),
    "동암": (37.4713, 126.7029),
    "구월": (37.4486, 126.7034),
    "송도": (37.3813, 126.6564),
    "연수": (37.4102, 126.6781),
    "논현동": (37.4012, 126.7220),
    "계양": (37.5374, 126.7377),
    "작전": (37.5308, 126.7229),
    "검단": (37.5942, 126.6757),
    "청라": (37.5333, 126.6537),
    "영종도": (37.4900, 126.5164),
    "을왕리": (37.4458, 126.3710),
}

# 구/군 레벨 매핑 (좌표 없이 텍스트 매칭용)
DISTRICT_MAPPING = {
    # 서울
    "강남구": "강남",
    "서초구": "서초", 
    "송파구": "송파",
    "강동구": "강동",
    "마포구": "마포",
    "용산구": "용산",
    "성동구": "성동",
    "광진구": "광진",
    "노원구": "노원",
    "도봉구": "도봉",
    "강북구": "강북",
    "성북구": "성북",
    "동대문구": "동대문",
    "중랑구": "중랑",
    "종로구": "종로",
    "중구": "중구",
    "서대문구": "서대문",
    "은평구": "은평",
    "강서구": "강서",
    "양천구": "양천",
    "구로구": "구로",
    "금천구": "금천",
    "영등포구": "영등포",
    "동작구": "동작",
    "관악구": "관악",
    
    # 경기
    "수원시": "수원",
    "성남시": "성남",
    "분당구": "분당",
    "용인시": "용인",
    "수지구": "수지",
    "안양시": "안양",
    "부천시": "부천",
    "고양시": "고양",
    "일산동구": "일산",
    "일산서구": "일산",
    "파주시": "파주",
    "김포시": "김포",
    "안산시": "안산",
    "시흥시": "시흥",
    "화성시": "화성",
    "평택시": "평택",
    "의정부시": "의정부",
    "남양주시": "남양주",
    "광명시": "광명",
    "군포시": "군포",
    "의왕시": "의왕",
    "하남시": "하남",
    "오산시": "오산",
    "이천시": "이천",
    "안성시": "안성",
    "광주시": "광주",
    "양평군": "양평",
    
    # 인천
    "부평구": "부평",
    "계양구": "계양",
    "서구": "서구",
    "연수구": "연수",
    "남동구": "남동",
    "미추홀구": "미추홀",
    "동구": "동구",
    "중구": "중구",
    "강화군": "강화",
    "옹진군": "옹진",
}


def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    두 좌표 간의 거리 계산 (Haversine 공식)
    
    Args:
        lat1, lng1: 첫 번째 좌표 (위도, 경도)
        lat2, lng2: 두 번째 좌표 (위도, 경도)
        
    Returns:
        거리 (km)
    """
    R = 6371  # 지구 반지름 (km)
    
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    
    a = (math.sin(dlat/2)**2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlng/2)**2)
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def normalize_location(location_input: str) -> Dict:
    """
    위치 입력을 정규화하여 좌표 또는 지역 정보 반환 (T맵 API 연동 강화)
    
    Args:
        location_input: 사용자 입력 위치 (예: "강남역", "강남역 근처")
        
    Returns:
        {'lat': 위도, 'lng': 경도, 'radius': 반경} 또는
        {'district': 구이름} 또는
        {'city': 도시이름}
    """
    # 전처리: 불필요한 단어 제거
    clean_input = location_input.strip()
    for remove_word in ["근처", "주변", "쪽", "인근", "부근", "에서", "으로"]:
        clean_input = clean_input.replace(remove_word, "").strip()
    
    # 1. 완전 일치 검색 (가장 정확)
    if clean_input in LOCATION_COORDINATES:
        lat, lng = LOCATION_COORDINATES[clean_input]
        return {'lat': lat, 'lng': lng, 'radius': 2.0, 'name': clean_input}
    
    # 2. '역' 처리 및 부분 매칭
    candidates = [clean_input]
    if clean_input.endswith("역"):
        candidates.append(clean_input[:-1])
    elif not clean_input.endswith(("구", "동")):
        candidates.append(clean_input + "역")
    
    for candidate in candidates:
        if candidate in LOCATION_COORDINATES:
            lat, lng = LOCATION_COORDINATES[candidate]
            return {'lat': lat, 'lng': lng, 'radius': 2.0, 'name': candidate}
        # 부분 매칭
        for loc_name, coords in LOCATION_COORDINATES.items():
            if candidate in loc_name:
                return {'lat': coords[0], 'lng': coords[1], 'radius': 2.0, 'name': loc_name}
    
    # 3. 구/군 단위 매칭
    for district, normalized in DISTRICT_MAPPING.items():
        if clean_input in district:
            if normalized in LOCATION_COORDINATES:
                lat, lng = LOCATION_COORDINATES[normalized]
                return {
                    'lat': lat,
                    'lng': lng,
                    'radius': 3.0,
                    'district': district,
                    'name': normalized
                }
            else:
                return {'district': district}
    
    # 4. T맵 API를 이용한 동적 좌표 조회 (최후의 수단)
    tmap_coords = _fetch_coords_from_tmap(clean_input)
    if tmap_coords:
        lat, lng = tmap_coords
        return {'lat': lat, 'lng': lng, 'radius': 1.5, 'name': clean_input}
    
    # 5. 광역 지역 확인 (좌표를 찾지 못한 경우)
    if "서울" in clean_input:
        return {'city': '서울특별시'}
    elif "경기" in clean_input:
        return {'city': '경기도'}
    elif "인천" in clean_input:
        return {'city': '인천광역시'}
    
    logger.warning(f"위치 정규화 최종 실패: {location_input}")
    return {}


def filter_shops_by_distance(shops: List, center_lat: float, center_lng: float, 
                            radius_km: float = 2.0) -> List[Dict]:
    """
    중심 좌표로부터 반경 내의 가게 필터링
    
    Args:
        shops: 가게 리스트
        center_lat, center_lng: 중심 좌표
        radius_km: 반경 (km)
        
    Returns:
        [{'shop': shop_object, 'distance': 거리}] 형태의 리스트
    """
    results = []
    
    for shop in shops:
        if hasattr(shop, 'latitude') and hasattr(shop, 'longitude'):
            if shop.latitude and shop.longitude:
                try:
                    distance = calculate_distance(
                        center_lat, center_lng,
                        shop.latitude, shop.longitude
                    )
                    
                    if distance <= radius_km:
                        results.append({
                            'shop': shop,
                            'distance': distance
                        })
                except Exception as e:
                    logger.warning(f"거리 계산 실패 - {shop.name}: {e}")
    
    # 거리순 정렬
    results.sort(key=lambda x: x['distance'])
    return results


def filter_shops_by_address(shops: List, location_keyword: str) -> List[Dict]:
    """
    주소 텍스트 매칭으로 가게 필터링
    
    Args:
        shops: 가게 리스트
        location_keyword: 위치 키워드
        
    Returns:
        [{'shop': shop_object}] 형태의 리스트
    """
    results = []
    
    for shop in shops:
        if hasattr(shop, 'address') and shop.address:
            if location_keyword in shop.address:
                results.append({
                    'shop': shop,
                    'distance': None
                })
    
    return results


def get_distance_description(distance_km: float) -> str:
    """
    거리를 사용자 친화적인 설명으로 변환
    
    Args:
        distance_km: 거리 (km)
        
    Returns:
        거리 설명 문자열
    """
    if distance_km < 0.3:
        return "도보 3분 이내"
    elif distance_km < 0.5:
        return "도보 5분 거리"
    elif distance_km < 1.0:
        return f"도보 {int(distance_km * 12)}분 거리"
    elif distance_km < 2.0:
        return f"약 {distance_km:.1f}km"
    else:
        return f"{distance_km:.1f}km 거리"


def haversine_filter(shops: List, center_coords: Tuple[float, float], 
                    radius_km: float = 5.0) -> List:
    """
    Haversine 거리 기반으로 반경 내 가게만 필터링
    
    Args:
        shops: 가게 리스트 (latitude, longitude 필드 필요)
        center_coords: 중심 좌표 (lat, lon)
        radius_km: 반경 (기본 5km)
    
    Returns:
        반경 내 가게 리스트 (거리 정보 추가됨)
    """
    center_lat, center_lon = center_coords
    filtered_shops = []
    
    for shop in shops:
        # 가게 좌표
        shop_lat = getattr(shop, 'latitude', 0)
        shop_lon = getattr(shop, 'longitude', 0)
        
        # 좌표가 없으면 스킵
        if shop_lat == 0 or shop_lon == 0:
            continue
        
        # 직선거리 계산 (기존 calculate_distance 함수 활용)
        distance = calculate_distance(center_lat, center_lon, shop_lat, shop_lon)
        
        # 반경 내에 있으면 추가
        if distance <= radius_km:
            # 거리 정보를 속성으로 추가
            shop.haversine_distance = distance
            filtered_shops.append(shop)
    
    # 거리순 정렬
    filtered_shops.sort(key=lambda x: x.haversine_distance)
    
    logger.info(f"Haversine filter: {len(shops)} → {len(filtered_shops)} shops within {radius_km}km")
    
    return filtered_shops


def get_coords_from_text(location_text: str) -> Optional[Tuple[float, float]]:
    """
    텍스트 위치를 좌표로 변환 (캐싱 적용)
    
    Args:
        location_text: 위치 텍스트 (예: "부천", "강남역")
    
    Returns:
        (latitude, longitude) 또는 None
    """
    # 정규화 (공백 제거)
    normalized = location_text.strip().replace(" ", "")
    
    # LOCATION_COORDINATES에서 찾기
    if normalized in LOCATION_COORDINATES:
        logger.info(f"Location found: {normalized}")
        return LOCATION_COORDINATES[normalized]
    
    # 부분 매칭 시도
    for key in LOCATION_COORDINATES:
        if normalized in key or key in normalized:
            logger.info(f"Partial match found: {normalized} → {key}")
            return LOCATION_COORDINATES[key]
    
    # DISTRICT_MAPPING에서 찾기
    if normalized in DISTRICT_MAPPING:
        mapped = DISTRICT_MAPPING[normalized]
        if mapped in LOCATION_COORDINATES:
            logger.info(f"District mapping: {normalized} → {mapped}")
            return LOCATION_COORDINATES[mapped]
    
    # T맵 API로 시도 (옵션)
    coords = _fetch_coords_from_tmap(location_text)
    if coords:
        return coords
    
    logger.warning(f"Could not find coordinates for: {location_text}")
    return None


def _fetch_coords_from_tmap(location_text: str) -> Optional[Tuple[float, float]]:
    """
    T맵 Geocoding API로 좌표 조회
    
    Args:
        location_text: 위치 텍스트
    
    Returns:
        (latitude, longitude) 또는 None
    """
    api_key = os.getenv('TMAP_API_KEY')
    if not api_key:
        logger.warning("TMAP_API_KEY not set, cannot use geocoding")
        return None
    
    try:
        # T맵 POI 검색 API
        url = "https://apis.openapi.sk.com/tmap/pois"
        params = {
            'version': 1,
            'searchKeyword': location_text,
            'searchType': 'all',
            'count': 1,
            'appKey': api_key
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('searchPoiInfo', {}).get('pois', {}).get('poi'):
                poi = data['searchPoiInfo']['pois']['poi'][0]
                lat = float(poi['frontLat'])
                lon = float(poi['frontLon'])
                logger.info(f"Fetched coords from T-map: {location_text} → ({lat}, {lon})")
                return (lat, lon)
    except Exception as e:
        logger.error(f"T-map geocoding failed: {e}")
    
    return None


def get_location_type(user_input: Dict) -> str:
    """
    사용자 입력에서 위치 타입 판단
    
    Args:
        user_input: 사용자 입력 데이터
    
    Returns:
        'gps' 또는 'text'
    """
    # GPS 좌표가 있으면 GPS 모드
    if user_input.get('latitude') and user_input.get('longitude'):
        return 'gps'
    
    # 텍스트 위치 정보가 있으면 텍스트 모드
    if user_input.get('location_text') or user_input.get('text'):
        return 'text'
    
    return 'unknown'


# 테스트 함수
def test_location_utils():
    """위치 유틸리티 테스트"""
    
    test_inputs = [
        "강남역",
        "강남역 근처",
        "홍대 주변",
        "분당",
        "송도",
        "서울",
        "강남구"
    ]
    
    for input_str in test_inputs:
        result = normalize_location(input_str)
        print(f"\n입력: {input_str}")
        print(f"결과: {result}")
        
        if 'lat' in result and 'lng' in result:
            print(f"좌표: ({result['lat']:.4f}, {result['lng']:.4f})")
            print(f"반경: {result.get('radius', 2.0)}km")
    
    # 거리 계산 테스트
    gangnam_lat, gangnam_lng = LOCATION_COORDINATES["강남역"]
    seocho_lat, seocho_lng = LOCATION_COORDINATES["서초"]
    
    distance = calculate_distance(gangnam_lat, gangnam_lng, seocho_lat, seocho_lng)
    print(f"\n강남역 - 서초 거리: {distance:.2f}km")
    print(f"설명: {get_distance_description(distance)}")


if __name__ == "__main__":
    test_location_utils()