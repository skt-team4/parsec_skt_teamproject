"""
푸드 아바타 리포트 - 10대용 재미있는 영양 리포트
게이미피케이션 + 시각적 표현
"""

from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import random
import logging

logger = logging.getLogger(__name__)


class FoodAvatar:
    """사용자의 식습관을 반영하는 푸드 아바타"""
    
    # 아바타 상태 정의
    AVATARS = {
        "perfect": {"name": "슈퍼사이언", "emoji": "✨🦸", "desc": "완벽한 밸런스!"},
        "energetic": {"name": "활기찬 라이언", "emoji": "✨🦁", "desc": "에너지 넘침!"},
        "sleepy": {"name": "졸린 코알라", "emoji": "😴🐨", "desc": "영양 불균형..."},
        "burning": {"name": "불타는 치타", "emoji": "🔥🐆", "desc": "칼로리 과다!"},
        "hungry": {"name": "배고픈 팬더", "emoji": "😋🐼", "desc": "더 먹어도 돼!"},
        "junk": {"name": "정크푸드 몬스터", "emoji": "🍔👾", "desc": "패스트푸드 중독?"},
        "veggie": {"name": "베지터", "emoji": "🥗🦋", "desc": "채소 마스터!"},
    }
    
    def __init__(self):
        self.current_avatar = None
        self.badges = []
        self.stats = {}
    
    def analyze_meals(self, meals: List[str]) -> str:
        """식사 목록 분석하여 아바타 결정"""
        # 간단한 카테고리 분석
        categories = {
            "carbs": 0,     # 탄수화물
            "protein": 0,   # 단백질
            "fat": 0,       # 지방
            "veggie": 0,    # 채소
            "junk": 0       # 정크푸드
        }
        
        # 메뉴별 카테고리 계산
        for meal in meals:
            meal_lower = meal.lower()
            
            # 탄수화물
            if any(word in meal_lower for word in ['밥', '빵', '면', '파스타', '떡']):
                categories["carbs"] += 1
            
            # 단백질
            if any(word in meal_lower for word in ['고기', '치킨', '돈까스', '스테이크', '계란']):
                categories["protein"] += 1
            
            # 지방
            if any(word in meal_lower for word in ['치킨', '피자', '튀김', '마요', '치즈']):
                categories["fat"] += 1
            
            # 채소
            if any(word in meal_lower for word in ['샐러드', '채소', '야채', '나물', '김치']):
                categories["veggie"] += 1
            
            # 정크푸드
            if any(word in meal_lower for word in ['버거', '피자', '치킨', '콜라', '감튀']):
                categories["junk"] += 1
        
        self.stats = categories
        
        # 아바타 결정 로직
        total = sum(categories.values())
        if total == 0:
            return "hungry"
        
        # 균형잡힌 식사
        if categories["veggie"] >= 2 and categories["protein"] >= 1 and categories["carbs"] >= 1:
            return "perfect"
        
        # 정크푸드 과다
        if categories["junk"] >= total * 0.6:
            return "junk"
        
        # 지방 과다
        if categories["fat"] >= total * 0.5:
            return "burning"
        
        # 채소 위주
        if categories["veggie"] >= total * 0.5:
            return "veggie"
        
        # 부족한 식사
        if total <= 2:
            return "hungry"
        
        # 기본값
        return "energetic"


class FoodAvatarReport:
    """푸드 아바타 기반 영양 리포트 생성"""
    
    def __init__(self):
        self.avatar = FoodAvatar()
        
    def create_graph(self, value: int, max_value: int = 8) -> str:
        """이모지 막대 그래프 생성"""
        filled = min(value, max_value)
        empty = max_value - filled
        return "▇" * filled + "-" * empty
    
    def generate_daily_report(self, user_id: str, meals: List[Dict]) -> str:
        """일일 리포트 생성
        
        Args:
            user_id: 사용자 ID
            meals: [{"time": "아침", "menu": "김밥"}, ...]
        """
        # 메뉴 추출
        meal_names = [m.get("menu", "") for m in meals]
        
        # 아바타 분석
        avatar_type = self.avatar.analyze_meals(meal_names)
        avatar_info = FoodAvatar.AVATARS[avatar_type]
        
        # 시간대별 분석
        meal_times = {}
        for meal in meals:
            time = meal.get("time", "기타")
            if time not in meal_times:
                meal_times[time] = []
            meal_times[time].append(meal.get("menu", ""))
        
        # 리포트 생성
        report = f"""
.｡.:*･ﾟ☆ 오늘의 푸드 아바타 리포트 ☆.｡.:*･ﾟ

짜잔! 오늘의 너의 푸드 아바타는 [{avatar_info['emoji']} {avatar_info['name']}]!
{avatar_info['desc']} {self._get_random_comment(avatar_type)}

📊 너의 영양 밸런스 그래프

탄수화물: [{self.create_graph(self.avatar.stats.get('carbs', 0))}] {'든든!' if self.avatar.stats.get('carbs', 0) >= 3 else '더 먹어!'} 🍚
단백질:   [{self.create_graph(self.avatar.stats.get('protein', 0))}] {'근육뿜뿜!' if self.avatar.stats.get('protein', 0) >= 2 else '부족해!'} 💪
지방:     [{self.create_graph(self.avatar.stats.get('fat', 0))}] {'과했나?' if self.avatar.stats.get('fat', 0) >= 4 else '적당해!'} 🧈
채소과일: [{self.create_graph(self.avatar.stats.get('veggie', 0))}] {'훌륭해!' if self.avatar.stats.get('veggie', 0) >= 2 else '더 친해지자!'} 🥦

🧐 너의 식습관 패턴 분석
{self._analyze_patterns(meal_times)}

💡 푸드 아바타's 미션 제안
{self._generate_missions(avatar_type, self.avatar.stats)}

🏆 오늘 획득한 뱃지
{self._check_badges(meals)}

#오늘의푸드아바타 #먹스타그램 #식단일기
"""
        return report
    
    def _get_random_comment(self, avatar_type: str) -> str:
        """아바타별 랜덤 코멘트"""
        comments = {
            "perfect": ["완전 JMT 밸런스!", "영양 만점이야!", "이대로만 계속!"],
            "energetic": ["오늘도 힘차게!", "에너지 충전 완료!", "활력 넘치네!"],
            "junk": ["패스트푸드 좀 줄여볼까?", "몸이 힘들어해!", "내일은 건강식 어때?"],
            "burning": ["칼로리 폭탄이야!", "운동 필수!", "땀 좀 빼야겠다!"],
            "hungry": ["더 먹어도 돼!", "배고프겠다!", "든든하게 챙겨먹자!"],
            "veggie": ["채소 사랑이네!", "건강 챙기는구나!", "고기도 좀 먹어!"],
            "sleepy": ["영양 불균형이야!", "골고루 먹자!", "기운 없겠다!"]
        }
        return random.choice(comments.get(avatar_type, ["오늘도 수고했어!"]))
    
    def _analyze_patterns(self, meal_times: Dict) -> str:
        """식사 패턴 분석"""
        patterns = []
        
        # 아침 체크
        if "아침" not in meal_times or not meal_times["아침"]:
            patterns.append("- 아침 거른 날! 아침은 하루의 시작이야~")
        else:
            patterns.append("- 아침 든든하게 먹었네! 최고야 👍")
        
        # 간식 체크
        if "간식" in meal_times and len(meal_times["간식"]) >= 2:
            patterns.append("- 간식 러쉬! 스트레스 있었어?")
        
        # 저녁 체크
        if "저녁" in meal_times and meal_times["저녁"]:
            evening = meal_times["저녁"][0].lower()
            if any(word in evening for word in ['치킨', '피자', '버거']):
                patterns.append("- 저녁에 헤비한 선택! 내일은 가볍게~")
        
        return "\n".join(patterns) if patterns else "- 규칙적인 식사 패턴! 훌륭해!"
    
    def _generate_missions(self, avatar_type: str, stats: Dict) -> str:
        """개선 미션 생성"""
        missions = []
        
        # 채소 부족
        if stats.get('veggie', 0) < 2:
            missions.append("🎯 내일 점심에 샐러드 추가하기!")
        
        # 단백질 부족
        if stats.get('protein', 0) < 2:
            missions.append("🎯 계란이나 닭가슴살 먹어보기!")
        
        # 정크푸드 과다
        if stats.get('junk', 0) >= 3:
            missions.append("🎯 패스트푸드 하루 쉬기 챌린지!")
        
        # 칭찬
        if avatar_type in ["perfect", "veggie"]:
            missions.append("👍 이대로만 계속 가자! 넌 최고야!")
        
        return "\n".join(missions) if missions else "👍 오늘도 잘 먹었어!"
    
    def _check_badges(self, meals: List[Dict]) -> str:
        """뱃지 획득 체크"""
        badges = []
        
        # 아침 먹기 뱃지
        if any(m.get("time") == "아침" for m in meals):
            badges.append("🌅 얼리버드 (아침 먹기)")
        
        # 채소 먹기 뱃지
        if any("샐러드" in m.get("menu", "").lower() for m in meals):
            badges.append("🥗 베지 러버 (채소 먹기)")
        
        # 3끼 챙기기
        times = set(m.get("time") for m in meals)
        if {"아침", "점심", "저녁"}.issubset(times):
            badges.append("⭐ 삼시세끼 (3끼 완료)")
        
        return " / ".join(badges) if badges else "오늘은 뱃지 없음 (내일 도전!)"
    
    def generate_weekly_summary(self, user_id: str, week_data: List[List[Dict]]) -> str:
        """주간 요약 리포트"""
        total_meals = sum(len(day) for day in week_data)
        
        # 주간 통계
        avatar_counts = {}
        for day_meals in week_data:
            if day_meals:
                meal_names = [m.get("menu", "") for m in day_meals]
                avatar_type = self.avatar.analyze_meals(meal_names)
                avatar_counts[avatar_type] = avatar_counts.get(avatar_type, 0) + 1
        
        # 가장 많이 나온 아바타
        if avatar_counts:
            main_avatar = max(avatar_counts, key=avatar_counts.get)
            main_info = FoodAvatar.AVATARS[main_avatar]
        else:
            main_avatar = "hungry"
            main_info = FoodAvatar.AVATARS["hungry"]
        
        # 등급 계산
        grade = self._calculate_grade(avatar_counts)
        
        report = f"""
🏆 이번 주 푸드 아바타 종합 리포트 🏆

주간 대표 아바타: [{main_info['emoji']} {main_info['name']}]
식단 등급: {grade}
총 {total_meals}끼 기록!

📈 주간 아바타 변화
{self._weekly_avatar_chart(avatar_counts)}

🎖️ 주간 특별 뱃지
{self._weekly_badges(week_data)}

다음 주도 화이팅! 💪
"""
        return report
    
    def _calculate_grade(self, avatar_counts: Dict) -> str:
        """주간 등급 계산"""
        perfect_days = avatar_counts.get("perfect", 0)
        good_days = avatar_counts.get("energetic", 0) + avatar_counts.get("veggie", 0)
        
        total = sum(avatar_counts.values())
        if total == 0:
            return "F (기록 부족)"
        
        score = (perfect_days * 3 + good_days * 2) / (total * 3) * 100
        
        if score >= 90:
            return "A+ 🌟 (푸드 마스터!)"
        elif score >= 80:
            return "A (훌륭해!)"
        elif score >= 70:
            return "B+ (좋아!)"
        elif score >= 60:
            return "B (괜찮아!)"
        else:
            return "C (노력 필요!)"
    
    def _weekly_avatar_chart(self, avatar_counts: Dict) -> str:
        """주간 아바타 차트"""
        lines = []
        for avatar_type, count in avatar_counts.items():
            info = FoodAvatar.AVATARS[avatar_type]
            lines.append(f"{info['emoji']}: {'●' * count}")
        return "\n".join(lines) if lines else "기록 없음"
    
    def _weekly_badges(self, week_data: List[List[Dict]]) -> str:
        """주간 특별 뱃지"""
        badges = []
        
        # 7일 연속 아침
        morning_days = sum(1 for day in week_data 
                          if any(m.get("time") == "아침" for m in day))
        if morning_days >= 5:
            badges.append("🏅 아침형 인간 (5일+ 아침)")
        
        # 채소 마스터
        veggie_days = sum(1 for day in week_data 
                          if any("샐러드" in m.get("menu", "").lower() for m in day))
        if veggie_days >= 3:
            badges.append("🏅 채소 마스터 (3일+ 채소)")
        
        return " / ".join(badges) if badges else "다음 주 뱃지 도전!"


# 싱글톤 인스턴스
_report_generator = None

def get_report_generator() -> FoodAvatarReport:
    """리포트 생성기 싱글톤"""
    global _report_generator
    if _report_generator is None:
        _report_generator = FoodAvatarReport()
    return _report_generator


# 간편 함수
def generate_daily_report(meals: List[str]) -> str:
    """일일 리포트 간편 생성"""
    generator = get_report_generator()
    meal_data = [{"time": "기타", "menu": meal} for meal in meals]
    return generator.generate_daily_report("user", meal_data)