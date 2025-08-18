"""
영양 분석 서비스 - 메뉴명 기반 영양 정보 추정
LLM + 캐싱 + 등급제 방식
전시/데모용 간소화 버전
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class NutritionAnalyzer:
    """메뉴명 기반 영양 분석기"""
    
    def __init__(self, cache_dir: str = "outputs/nutrition_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "nutrition_data.json"
        
        # 캐시 로드
        self.cache = self._load_cache()
        
        # 10대 기준 영양 권장량 (1일)
        self.teen_daily_standard = {
            'calories': 2400,  # 남자 기준
            'protein': 65,
            'fat': 80,
            'carbs': 360,
            'sodium': 2000
        }
        
        # 한 끼 기준 (1/3)
        self.meal_standard = {k: v/3 for k, v in self.teen_daily_standard.items()}
        
        # 데모용 하드코딩 데이터 (자주 나올 메뉴들)
        self._init_demo_data()
    
    def _load_cache(self) -> Dict:
        """캐시 파일 로드"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_cache(self):
        """캐시 파일 저장"""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
    
    def _init_demo_data(self):
        """데모용 대표 메뉴 영양 정보 초기화"""
        demo_data = {
            # 10대 인기 메뉴들
            "마라탕": {"calories": 700, "protein": 30, "fat": 45, "carbs": 50, "sodium": 2200},
            "로제떡볶이": {"calories": 850, "protein": 20, "fat": 50, "carbs": 90, "sodium": 1500},
            "치즈돈까스": {"calories": 950, "protein": 35, "fat": 55, "carbs": 75, "sodium": 1200},
            "탕후루": {"calories": 350, "protein": 1, "fat": 0, "carbs": 90, "sodium": 10},
            "버블티": {"calories": 450, "protein": 2, "fat": 15, "carbs": 80, "sodium": 100},
            "불고기버거": {"calories": 450, "protein": 25, "fat": 20, "carbs": 40, "sodium": 800},
            "붕어빵": {"calories": 150, "protein": 3, "fat": 5, "carbs": 25, "sodium": 150},
            "치킨": {"calories": 900, "protein": 45, "fat": 50, "carbs": 60, "sodium": 1800},
            "피자": {"calories": 280, "protein": 12, "fat": 14, "carbs": 30, "sodium": 600},  # 1조각
            "라멘": {"calories": 500, "protein": 20, "fat": 25, "carbs": 55, "sodium": 1600},
            "우동": {"calories": 400, "protein": 15, "fat": 10, "carbs": 65, "sodium": 1200},
            "김밥": {"calories": 350, "protein": 10, "fat": 12, "carbs": 50, "sodium": 700},
            "떡볶이": {"calories": 600, "protein": 15, "fat": 20, "carbs": 95, "sodium": 1300},
        }
        
        # 캐시에 없는 것만 추가
        for menu, nutrition in demo_data.items():
            if menu not in self.cache:
                self.cache[menu] = nutrition
        
        self._save_cache()
    
    def _estimate_from_category(self, menu_name: str) -> Optional[Dict]:
        """카테고리 기반 영양 추정 (폴백)"""
        # 간단한 키워드 매칭
        category_patterns = {
            "버거": {"calories": 500, "protein": 25, "fat": 25, "carbs": 45, "sodium": 900},
            "치킨": {"calories": 850, "protein": 40, "fat": 45, "carbs": 55, "sodium": 1700},
            "피자": {"calories": 800, "protein": 35, "fat": 40, "carbs": 85, "sodium": 1800},
            "떡볶이": {"calories": 650, "protein": 18, "fat": 25, "carbs": 90, "sodium": 1400},
            "라면": {"calories": 500, "protein": 15, "fat": 20, "carbs": 70, "sodium": 1500},
            "김밥": {"calories": 350, "protein": 10, "fat": 12, "carbs": 50, "sodium": 700},
            "탕": {"calories": 600, "protein": 30, "fat": 35, "carbs": 45, "sodium": 1800},
            "찌개": {"calories": 450, "protein": 25, "fat": 20, "carbs": 40, "sodium": 1600},
            "빙수": {"calories": 400, "protein": 5, "fat": 10, "carbs": 75, "sodium": 50},
            "커피": {"calories": 150, "protein": 3, "fat": 5, "carbs": 25, "sodium": 100},
        }
        
        # 메뉴명에서 카테고리 찾기
        for category, nutrition in category_patterns.items():
            if category in menu_name:
                logger.info(f"카테고리 매칭: {menu_name} → {category}")
                return nutrition
        
        # 기본값
        return {"calories": 500, "protein": 20, "fat": 20, "carbs": 60, "sodium": 1000}
    
    def get_nutrition(self, menu_name: str) -> Dict:
        """메뉴의 영양 정보 조회"""
        # 1. 캐시 확인
        if menu_name in self.cache:
            logger.info(f"캐시에서 조회: {menu_name}")
            return self.cache[menu_name]
        
        # 2. 카테고리 기반 추정
        nutrition = self._estimate_from_category(menu_name)
        
        # 3. 캐시 저장
        self.cache[menu_name] = nutrition
        self._save_cache()
        
        logger.info(f"새로 추정: {menu_name}")
        return nutrition
    
    def get_grade(self, value: float, standard: float) -> str:
        """영양소 수치를 등급으로 변환"""
        if value > standard * 1.2:
            return "높음"
        elif value > standard * 0.8:
            return "보통"
        else:
            return "낮음"
    
    def analyze_menu(self, menu_name: str) -> Dict:
        """메뉴 영양 분석 결과 반환"""
        nutrition = self.get_nutrition(menu_name)
        
        # 등급 계산
        grades = {
            "칼로리": self.get_grade(nutrition['calories'], self.meal_standard['calories']),
            "단백질": self.get_grade(nutrition['protein'], self.meal_standard['protein']),
            "지방": self.get_grade(nutrition['fat'], self.meal_standard['fat']),
            "탄수화물": self.get_grade(nutrition['carbs'], self.meal_standard['carbs']),
            "나트륨": self.get_grade(nutrition['sodium'], self.meal_standard['sodium'])
        }
        
        # 조언 생성
        advice = []
        if grades["칼로리"] == "높음":
            advice.append("칼로리가 높은 편이야! 다음 끼는 가볍게~")
        if grades["나트륨"] == "높음":
            advice.append("짜게 먹었네! 물 많이 마셔")
        if grades["단백질"] == "낮음":
            advice.append("단백질이 부족해! 고기나 계란 추가 어때?")
        
        return {
            "menu": menu_name,
            "nutrition": nutrition,
            "grades": grades,
            "advice": advice if advice else ["균형잡힌 선택이야!"]
        }
    
    def analyze_daily_intake(self, menu_list: list) -> Dict:
        """하루 섭취 영양 분석"""
        total = {"calories": 0, "protein": 0, "fat": 0, "carbs": 0, "sodium": 0}
        
        for menu in menu_list:
            nutrition = self.get_nutrition(menu)
            for key in total:
                total[key] += nutrition.get(key, 0)
        
        # 일일 권장량 대비 퍼센트
        percentage = {}
        for key in total:
            percentage[key] = round((total[key] / self.teen_daily_standard[key]) * 100)
        
        # 부족/과다 영양소 파악
        lacking = [k for k, v in percentage.items() if v < 80]
        excess = [k for k, v in percentage.items() if v > 120]
        
        return {
            "total": total,
            "percentage": percentage,
            "lacking": lacking,
            "excess": excess,
            "message": self._generate_daily_advice(lacking, excess)
        }
    
    def _generate_daily_advice(self, lacking: list, excess: list) -> str:
        """일일 섭취 조언 생성"""
        if not lacking and not excess:
            return "오늘 영양 밸런스 완벽해! 👍"
        
        advice = []
        if excess:
            if "calories" in excess:
                advice.append("칼로리 초과! 운동 좀 하자")
            if "sodium" in excess:
                advice.append("나트륨 과다! 물 많이 마셔야 해")
        
        if lacking:
            if "protein" in lacking:
                advice.append("단백질 부족! 치킨이나 계란 어때?")
            if "carbs" in lacking:
                advice.append("탄수화물 부족! 밥이나 빵 먹자")
        
        return " / ".join(advice) if advice else "영양 밸런스 체크!"


# 싱글톤 인스턴스
_analyzer = None

def get_nutrition_analyzer() -> NutritionAnalyzer:
    """영양 분석기 싱글톤"""
    global _analyzer
    if _analyzer is None:
        _analyzer = NutritionAnalyzer()
    return _analyzer


# 간편 함수들
def analyze_menu(menu_name: str) -> str:
    """메뉴 영양 분석 메시지"""
    analyzer = get_nutrition_analyzer()
    result = analyzer.analyze_menu(menu_name)
    
    # 간단한 메시지 생성
    grades_str = ", ".join([f"{k} {v}" for k, v in result['grades'].items() if v == "높음"])
    if grades_str:
        message = f"{menu_name}: {grades_str}. "
    else:
        message = f"{menu_name}: 괜찮은 선택! "
    
    message += result['advice'][0]
    return message


def get_daily_summary(menu_list: list) -> str:
    """일일 섭취 요약"""
    analyzer = get_nutrition_analyzer()
    result = analyzer.analyze_daily_intake(menu_list)
    
    return result['message']