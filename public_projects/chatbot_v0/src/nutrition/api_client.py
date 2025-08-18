"""
식품안전처 영양정보 API 클라이언트
공공데이터 OPEN API를 통한 영양정보 수집
"""

import requests
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import pandas as pd
from datetime import datetime
import json

logger = logging.getLogger(__name__)


@dataclass
class NutritionInfo:
    """영양정보 데이터 클래스"""
    food_code: str
    food_name: str
    food_name_en: Optional[str]
    category: str
    serving_size: float  # 1회 제공량 (g)
    calories: float  # 칼로리 (kcal)
    carbohydrate: float  # 탄수화물 (g)
    protein: float  # 단백질 (g) 
    fat: float  # 지방 (g)
    sugar: float  # 당류 (g)
    sodium: float  # 나트륨 (mg)
    cholesterol: float  # 콜레스테롤 (mg)
    saturated_fat: float  # 포화지방 (g)
    trans_fat: float  # 트랜스지방 (g)
    manufacturer: Optional[str]  # 제조사
    research_year: str  # 조사년도
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'food_code': self.food_code,
            'food_name': self.food_name,
            'food_name_en': self.food_name_en,
            'category': self.category,
            'serving_size': self.serving_size,
            'calories': self.calories,
            'carbohydrate': self.carbohydrate,
            'protein': self.protein,
            'fat': self.fat,
            'sugar': self.sugar,
            'sodium': self.sodium,
            'cholesterol': self.cholesterol,
            'saturated_fat': self.saturated_fat,
            'trans_fat': self.trans_fat,
            'manufacturer': self.manufacturer,
            'research_year': self.research_year,
            'created_at': self.created_at.isoformat()
        }


class FoodSafetyAPIClient:
    """식품안전처 영양정보 API 클라이언트"""
    
    def __init__(self, api_key: str, base_url: str = "http://openapi.foodsafetykorea.go.kr/api"):
        """
        API 클라이언트 초기화
        
        Args:
            api_key: 식품안전처 API 키
            base_url: API 기본 URL
        """
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NaviyamChatbot/1.0'
        })
        
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        API 요청 실행
        
        Args:
            endpoint: API 엔드포인트
            params: 요청 파라미터
            
        Returns:
            API 응답 데이터
        """
        url = f"{self.base_url}/{self.api_key}/{endpoint}/json"
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # API 오류 체크
            if 'RESULT' in data and data['RESULT']['CODE'] != 'INFO-000':
                error_msg = data['RESULT'].get('MSG', 'Unknown error')
                logger.error(f"API Error: {error_msg}")
                raise APIError(f"API returned error: {error_msg}")
                
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise APIError(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise APIError(f"Invalid JSON response: {e}")
    
    def get_nutrition_info(self, start_idx: int = 1, end_idx: int = 100, 
                          food_name: Optional[str] = None) -> List[NutritionInfo]:
        """
        영양정보 조회
        
        Args:
            start_idx: 시작 인덱스
            end_idx: 종료 인덱스  
            food_name: 특정 음식명으로 검색 (선택사항)
            
        Returns:
            영양정보 리스트
        """
        params = {
            'START_IDX': start_idx,
            'END_IDX': end_idx
        }
        
        if food_name:
            params['DESC_KOR'] = food_name
            
        try:
            data = self._make_request('I2790', params)
            
            if 'I2790' not in data or 'row' not in data['I2790']:
                logger.warning("No data found in API response")
                return []
                
            nutrition_list = []
            for item in data['I2790']['row']:
                try:
                    nutrition_info = self._parse_nutrition_item(item)
                    nutrition_list.append(nutrition_info)
                except Exception as e:
                    logger.warning(f"Failed to parse nutrition item: {e}")
                    continue
                    
            logger.info(f"Retrieved {len(nutrition_list)} nutrition items")
            return nutrition_list
            
        except APIError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in get_nutrition_info: {e}")
            raise APIError(f"Unexpected error: {e}")
    
    def _parse_nutrition_item(self, item: Dict[str, Any]) -> NutritionInfo:
        """
        API 응답 항목을 NutritionInfo 객체로 변환
        
        Args:
            item: API 응답 항목
            
        Returns:
            NutritionInfo 객체
        """
        def safe_float(value: Any, default: float = 0.0) -> float:
            """안전한 float 변환"""
            if value is None or value == '' or value == '-':
                return default
            try:
                return float(str(value).replace(',', ''))
            except (ValueError, TypeError):
                return default
        
        def safe_str(value: Any, default: str = '') -> str:
            """안전한 string 변환"""
            if value is None:
                return default
            return str(value).strip()
        
        return NutritionInfo(
            food_code=safe_str(item.get('FOOD_CD')),
            food_name=safe_str(item.get('DESC_KOR')),
            food_name_en=safe_str(item.get('DESC_ENG')),
            category=safe_str(item.get('GROUP_NAME')),
            serving_size=safe_float(item.get('SERVING_SIZE')),
            calories=safe_float(item.get('NUTR_CONT1')),  # 에너지(kcal)
            carbohydrate=safe_float(item.get('NUTR_CONT2')),  # 탄수화물(g)
            protein=safe_float(item.get('NUTR_CONT3')),  # 단백질(g)
            fat=safe_float(item.get('NUTR_CONT4')),  # 지방(g)
            sugar=safe_float(item.get('NUTR_CONT5')),  # 당류(g)
            sodium=safe_float(item.get('NUTR_CONT6')),  # 나트륨(mg)
            cholesterol=safe_float(item.get('NUTR_CONT7')),  # 콜레스테롤(mg)
            saturated_fat=safe_float(item.get('NUTR_CONT8')),  # 포화지방산(g)
            trans_fat=safe_float(item.get('NUTR_CONT9')),  # 트랜스지방산(g)
            manufacturer=safe_str(item.get('MAKER_NAME')),
            research_year=safe_str(item.get('RESEARCH_YEAR', str(datetime.now().year))),
            created_at=datetime.now()
        )
    
    def get_all_nutrition_data(self, batch_size: int = 1000, 
                              max_items: Optional[int] = None,
                              delay: float = 0.1) -> List[NutritionInfo]:
        """
        전체 영양정보 데이터 수집
        
        Args:
            batch_size: 한 번에 가져올 데이터 수
            max_items: 최대 수집할 데이터 수 (None이면 전체)
            delay: 요청 간 지연시간 (초)
            
        Returns:
            전체 영양정보 리스트
        """
        all_nutrition_data = []
        current_idx = 1
        
        logger.info("Starting bulk nutrition data collection...")
        
        while True:
            if max_items and len(all_nutrition_data) >= max_items:
                break
                
            end_idx = current_idx + batch_size - 1
            
            try:
                batch_data = self.get_nutrition_info(current_idx, end_idx)
                
                if not batch_data:
                    logger.info("No more data available")
                    break
                    
                all_nutrition_data.extend(batch_data)
                logger.info(f"Collected {len(all_nutrition_data)} items so far...")
                
                current_idx += batch_size
                
                # API 부하 방지를 위한 지연
                if delay > 0:
                    time.sleep(delay)
                    
            except APIError as e:
                logger.error(f"API error at index {current_idx}: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error at index {current_idx}: {e}")
                break
        
        logger.info(f"Completed data collection. Total items: {len(all_nutrition_data)}")
        return all_nutrition_data
    
    def search_food(self, food_name: str, limit: int = 20) -> List[NutritionInfo]:
        """
        특정 음식명으로 영양정보 검색
        
        Args:
            food_name: 검색할 음식명
            limit: 반환할 최대 결과 수
            
        Returns:
            검색된 영양정보 리스트
        """
        try:
            results = self.get_nutrition_info(1, limit, food_name)
            logger.info(f"Found {len(results)} results for '{food_name}'")
            return results
        except Exception as e:
            logger.error(f"Error searching for '{food_name}': {e}")
            return []


class APIError(Exception):
    """API 관련 예외"""
    pass


def create_sample_data(api_key: str, output_file: str = "sample_nutrition_data.json"):
    """
    샘플 영양정보 데이터 생성 (테스트용)
    
    Args:
        api_key: API 키
        output_file: 출력 파일명
    """
    client = FoodSafetyAPIClient(api_key)
    
    try:
        # 한국 대표 음식들 검색
        sample_foods = ['김치', '비빔밥', '불고기', '삼계탕', '냉면', '떡볶이', '짜장면', '치킨']
        
        all_sample_data = []
        for food in sample_foods:
            results = client.search_food(food, limit=5)
            all_sample_data.extend([item.to_dict() for item in results])
            time.sleep(0.5)  # API 부하 방지
        
        # JSON 파일로 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_sample_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Sample data saved to {output_file}")
        print(f"✅ 샘플 데이터 {len(all_sample_data)}개 항목이 {output_file}에 저장되었습니다.")
        
    except Exception as e:
        logger.error(f"Error creating sample data: {e}")
        print(f"❌ 샘플 데이터 생성 중 오류 발생: {e}")


if __name__ == "__main__":
    # 테스트 실행
    import sys
    
    if len(sys.argv) < 2:
        print("사용법: python api_client.py <API_KEY>")
        sys.exit(1)
    
    api_key = sys.argv[1]
    create_sample_data(api_key)