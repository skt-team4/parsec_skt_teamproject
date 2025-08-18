"""
영양정보 데이터 전처리 파이프라인
API로부터 수집된 데이터를 정제하고 RAG 시스템용으로 변환
"""

import pandas as pd
import numpy as np
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import re
from dataclasses import asdict

from .api_client import NutritionInfo, FoodSafetyAPIClient

logger = logging.getLogger(__name__)


class NutritionDataProcessor:
    """영양정보 데이터 전처리기"""
    
    def __init__(self, output_dir: str = "outputs/nutrition"):
        """
        전처리기 초기화
        
        Args:
            output_dir: 처리된 데이터 저장 경로
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 한국어 음식명 정규화를 위한 패턴
        self.food_name_patterns = {
            # 공통 단어 제거
            'remove_patterns': [r'\([^)]*\)', r'\[[^\]]*\]', r'생것', r'익힌것', r'조리된것'],
            # 동의어 매핑
            'synonyms': {
                '닭고기': ['치킨', '계육'],
                '돼지고기': ['돈육', '포크'],
                '소고기': ['우육', '비프'],
                '김치': ['배추김치', '포기김치'],
                '밥': ['쌀밥', '백미밥'],
                '국수': ['면', '누들']
            }
        }
    
    def clean_nutrition_data(self, nutrition_list: List[NutritionInfo]) -> pd.DataFrame:
        """
        영양정보 데이터 정제
        
        Args:
            nutrition_list: 원본 영양정보 리스트
            
        Returns:
            정제된 DataFrame
        """
        logger.info(f"Starting data cleaning for {len(nutrition_list)} items")
        
        # DataFrame 변환
        df = pd.DataFrame([asdict(info) for info in nutrition_list])
        
        if df.empty:
            logger.warning("Empty dataset provided")
            return df
        
        original_count = len(df)
        
        # 1. 기본 정제
        df = self._basic_cleaning(df)
        
        # 2. 음식명 정규화
        df = self._normalize_food_names(df)
        
        # 3. 영양성분 데이터 정제
        df = self._clean_nutrition_values(df)
        
        # 4. 중복 제거
        df = self._remove_duplicates(df)
        
        # 5. 이상치 처리
        df = self._handle_outliers(df)
        
        # 6. 아동 친화적 카테고리 추가
        df = self._add_child_friendly_categories(df)
        
        cleaned_count = len(df)
        logger.info(f"Data cleaning completed: {original_count} → {cleaned_count} items")
        
        return df
    
    def _basic_cleaning(self, df: pd.DataFrame) -> pd.DataFrame:
        """기본 데이터 정제"""
        logger.info("Performing basic data cleaning...")
        
        # 필수 컬럼 체크
        required_columns = ['food_name', 'calories', 'carbohydrate', 'protein', 'fat']
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        # 빈 음식명 제거
        df = df[df['food_name'].notna() & (df['food_name'].str.strip() != '')]
        
        # 음식명 기본 정제
        df['food_name'] = df['food_name'].str.strip()
        df['food_name_clean'] = df['food_name'].copy()
        
        # 카테고리 정제
        df['category'] = df['category'].fillna('기타').str.strip()
        
        return df
    
    def _normalize_food_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """음식명 정규화"""
        logger.info("Normalizing food names...")
        
        def normalize_name(name: str) -> str:
            if pd.isna(name):
                return name
            
            # 괄호, 대괄호 내용 제거
            for pattern in self.food_name_patterns['remove_patterns']:
                name = re.sub(pattern, '', name)
            
            # 여러 공백을 하나로
            name = re.sub(r'\s+', ' ', name).strip()
            
            return name
        
        df['food_name_normalized'] = df['food_name_clean'].apply(normalize_name)
        
        # 동의어 매핑 적용
        for standard, synonyms in self.food_name_patterns['synonyms'].items():
            for synonym in synonyms:
                mask = df['food_name_normalized'].str.contains(synonym, na=False)
                df.loc[mask, 'food_name_standardized'] = df.loc[mask, 'food_name_normalized'].str.replace(synonym, standard)
        
        # 표준화된 이름이 없으면 정규화된 이름 사용
        df['food_name_standardized'] = df.get('food_name_standardized', df['food_name_normalized'])
        
        return df
    
    def _clean_nutrition_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """영양성분 값 정제"""
        logger.info("Cleaning nutrition values...")
        
        nutrition_columns = ['calories', 'carbohydrate', 'protein', 'fat', 'sugar', 
                           'sodium', 'cholesterol', 'saturated_fat', 'trans_fat']
        
        for col in nutrition_columns:
            if col in df.columns:
                # 0 미만 값을 0으로 변경
                df[col] = df[col].clip(lower=0)
                
                # 극단적인 이상치 처리 (99.9 백분위수 기준)
                if col in ['calories']:
                    upper_limit = df[col].quantile(0.999)
                    df[col] = df[col].clip(upper=upper_limit)
        
        # 기본 영양성분이 모두 0인 항목 제거
        essential_nutrients = ['calories', 'carbohydrate', 'protein', 'fat']
        zero_mask = (df[essential_nutrients] == 0).all(axis=1)
        df = df[~zero_mask]
        
        return df
    
    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """중복 데이터 제거"""
        logger.info("Removing duplicates...")
        
        original_count = len(df)
        
        # 음식명과 주요 영양성분 기준으로 중복 제거
        duplicate_columns = ['food_name_standardized', 'calories', 'protein', 'carbohydrate', 'fat']
        df = df.drop_duplicates(subset=duplicate_columns, keep='first')
        
        removed_count = original_count - len(df)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} duplicate entries")
        
        return df
    
    def _handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """이상치 처리"""
        logger.info("Handling outliers...")
        
        # 칼로리 기준 이상치 검출 (IQR 방법)
        Q1 = df['calories'].quantile(0.25)
        Q3 = df['calories'].quantile(0.75)
        IQR = Q3 - Q1
        
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        # 극단적인 이상치만 제거 (3 IQR 기준)
        extreme_lower = Q1 - 3 * IQR
        extreme_upper = Q3 + 3 * IQR
        
        outlier_mask = (df['calories'] < extreme_lower) | (df['calories'] > extreme_upper)
        outlier_count = outlier_mask.sum()
        
        if outlier_count > 0:
            logger.warning(f"Removing {outlier_count} extreme outliers")
            df = df[~outlier_mask]
        
        return df
    
    def _add_child_friendly_categories(self, df: pd.DataFrame) -> pd.DataFrame:
        """아동 친화적 카테고리 추가"""
        logger.info("Adding child-friendly categories...")
        
        def categorize_for_children(row):
            """아동용 카테고리 분류"""
            food_name = str(row['food_name_standardized']).lower()
            category = str(row['category']).lower()
            
            # 과일
            if any(fruit in food_name for fruit in ['사과', '바나나', '딸기', '포도', '오렌지', '키위', '수박', '참외']):
                return '건강한 과일'
            
            # 채소
            elif any(veg in food_name for veg in ['당근', '브로콜리', '시금치', '배추', '무', '양배추']):
                return '몸에 좋은 채소'
            
            # 밥류
            elif any(rice in food_name for rice in ['밥', '비빔밥', '볶음밥', '김밥']):
                return '든든한 밥'
            
            # 면류
            elif any(noodle in food_name for noodle in ['면', '국수', '라면', '파스타', '우동', '냉면']):
                return '맛있는 면'
            
            # 고기류
            elif any(meat in food_name for meat in ['고기', '치킨', '불고기', '갈비', '삼겹살']):
                return '힘이 나는 고기'
            
            # 생선류
            elif any(fish in food_name for fish in ['생선', '고등어', '연어', '참치', '명태']):
                return '영양 만점 생선'
            
            # 국물류
            elif any(soup in food_name for soup in ['국', '찌개', '탕', '스프']):
                return '따뜻한 국물'
            
            # 간식류
            elif any(snack in food_name for snack in ['과자', '케이크', '쿠키', '사탕', '초콜릿']):
                return '달콤한 간식'
            
            # 음료
            elif any(drink in food_name for drink in ['음료', '주스', '우유', '요구르트']):
                return '시원한 음료'
            
            else:
                return '기타 음식'
        
        df['child_category'] = df.apply(categorize_for_children, axis=1)
        
        # 건강도 점수 추가 (5점 만점)
        def calculate_health_score(row):
            """간단한 건강도 점수 계산"""
            score = 3.0  # 기본 점수
            
            # 단백질 비율이 높으면 가점
            if row['protein'] > 15:
                score += 0.5
            
            # 나트륨이 적으면 가점
            if row['sodium'] < 500:
                score += 0.5
            
            # 당분이 많으면 감점
            if row['sugar'] > 20:
                score -= 0.5
            
            # 포화지방이 많으면 감점
            if row['saturated_fat'] > 10:
                score -= 0.5
            
            return max(1.0, min(5.0, score))
        
        df['health_score'] = df.apply(calculate_health_score, axis=1)
        
        return df
    
    def create_search_text(self, df: pd.DataFrame) -> pd.DataFrame:
        """검색용 텍스트 생성"""
        logger.info("Creating search text for RAG...")
        
        def generate_search_text(row):
            """RAG 검색용 텍스트 생성"""
            parts = []
            
            # 기본 정보
            parts.append(f"음식명: {row['food_name_standardized']}")
            parts.append(f"카테고리: {row['child_category']}")
            
            # 영양 정보 (아동 친화적 표현)
            parts.append(f"칼로리: {row['calories']:.0f}kcal")
            parts.append(f"단백질: {row['protein']:.1f}g (근육을 만들어줘요)")
            parts.append(f"탄수화물: {row['carbohydrate']:.1f}g (에너지를 줘요)")
            parts.append(f"지방: {row['fat']:.1f}g")
            
            if row['sugar'] > 0:
                parts.append(f"당분: {row['sugar']:.1f}g")
            
            if row['sodium'] > 0:
                parts.append(f"나트륨: {row['sodium']:.0f}mg")
            
            # 건강도 점수
            parts.append(f"건강도: {row['health_score']:.1f}/5점")
            
            # 아동용 설명 추가
            if row['health_score'] >= 4.0:
                parts.append("영양이 풍부해서 자주 먹으면 좋아요!")
            elif row['health_score'] >= 3.0:
                parts.append("적당히 먹으면 맛있고 건강해요!")
            else:
                parts.append("가끔 먹는 게 좋아요!")
            
            return " | ".join(parts)
        
        df['search_text'] = df.apply(generate_search_text, axis=1)
        
        return df
    
    def save_processed_data(self, df: pd.DataFrame, 
                          filename: str = "processed_nutrition_data") -> Tuple[str, str]:
        """
        처리된 데이터 저장
        
        Args:
            df: 처리된 DataFrame
            filename: 저장할 파일명 (확장자 제외)
            
        Returns:
            (parquet_path, json_path) 저장된 파일 경로들
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Parquet 파일로 저장 (효율적인 데이터 저장)
        parquet_path = self.output_dir / f"{filename}_{timestamp}.parquet"
        df.to_parquet(parquet_path, index=False)
        
        # JSON 파일로도 저장 (호환성)
        json_path = self.output_dir / f"{filename}_{timestamp}.json"
        df.to_json(json_path, orient='records', force_ascii=False, indent=2)
        
        # 메타데이터 저장
        metadata = {
            'created_at': datetime.now().isoformat(),
            'total_items': len(df),
            'columns': list(df.columns),
            'categories': df['child_category'].value_counts().to_dict(),
            'avg_health_score': float(df['health_score'].mean()),
            'parquet_file': str(parquet_path),
            'json_file': str(json_path)
        }
        
        metadata_path = self.output_dir / f"{filename}_{timestamp}_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Processed data saved to:")
        logger.info(f"  - Parquet: {parquet_path}")
        logger.info(f"  - JSON: {json_path}")
        logger.info(f"  - Metadata: {metadata_path}")
        
        return str(parquet_path), str(json_path)
    
    def get_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """처리된 데이터 통계 반환"""
        if df.empty:
            return {}
        
        stats = {
            'total_items': len(df),
            'categories': df['child_category'].value_counts().to_dict(),
            'nutrition_stats': {
                'avg_calories': float(df['calories'].mean()),
                'avg_protein': float(df['protein'].mean()),
                'avg_carbs': float(df['carbohydrate'].mean()),
                'avg_fat': float(df['fat'].mean()),
                'avg_health_score': float(df['health_score'].mean())
            },
            'top_healthy_foods': df.nlargest(10, 'health_score')[['food_name_standardized', 'health_score']].to_dict('records'),
            'sample_search_texts': df['search_text'].head(3).tolist()
        }
        
        return stats


def process_nutrition_data_pipeline(api_key: str, 
                                  max_items: Optional[int] = 1000,
                                  output_dir: str = "outputs/nutrition") -> Dict[str, Any]:
    """
    전체 영양정보 데이터 처리 파이프라인 실행
    
    Args:
        api_key: 식품안전처 API 키
        max_items: 수집할 최대 데이터 수
        output_dir: 출력 디렉토리
        
    Returns:
        처리 결과 정보
    """
    try:
        # 1. 데이터 수집
        logger.info("Step 1: Collecting nutrition data from API...")
        client = FoodSafetyAPIClient(api_key)
        nutrition_data = client.get_all_nutrition_data(max_items=max_items)
        
        if not nutrition_data:
            raise ValueError("No nutrition data collected from API")
        
        # 2. 데이터 전처리
        logger.info("Step 2: Processing nutrition data...")
        processor = NutritionDataProcessor(output_dir)
        processed_df = processor.clean_nutrition_data(nutrition_data)
        
        # 3. 검색용 텍스트 생성
        logger.info("Step 3: Creating search text...")
        processed_df = processor.create_search_text(processed_df)
        
        # 4. 데이터 저장
        logger.info("Step 4: Saving processed data...")
        parquet_path, json_path = processor.save_processed_data(processed_df)
        
        # 5. 통계 생성
        stats = processor.get_statistics(processed_df)
        
        result = {
            'status': 'success',
            'processed_items': len(processed_df),
            'parquet_file': parquet_path,
            'json_file': json_path,
            'statistics': stats
        }
        
        logger.info("Nutrition data processing pipeline completed successfully!")
        return result
        
    except Exception as e:
        logger.error(f"Error in nutrition data processing pipeline: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


if __name__ == "__main__":
    # 테스트 실행
    import sys
    
    if len(sys.argv) < 2:
        print("사용법: python data_processor.py <API_KEY> [max_items]")
        sys.exit(1)
    
    api_key = sys.argv[1]
    max_items = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    
    result = process_nutrition_data_pipeline(api_key, max_items)
    
    if result['status'] == 'success':
        print(f"✅ 처리 완료: {result['processed_items']}개 항목")
        print(f"📁 파일 저장: {result['parquet_file']}")
    else:
        print(f"❌ 처리 실패: {result['error']}")