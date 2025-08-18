"""
사용자 프로필 및 세션 관리
"""

import json
import pickle
from pathlib import Path
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
import logging

from src.data.data_structure import UserProfile, ExtractedInfo, ChatbotResponse, IntentType, UserState, LearningData
from src.nlp.preprocessor import EmotionType

logger = logging.getLogger(__name__)

class NaviyamUserManager:
    """나비얌 사용자 관리자"""

    def __init__(self, save_path: str, enable_personalization: bool = True):
        """
        Args:
            save_path: 사용자 프로필 저장 경로
            enable_personalization: 개인화 기능 활성화 여부
        """
        self.save_path = Path(save_path)
        self.enable_personalization = enable_personalization
        self.user_profiles: Dict[str, UserProfile] = {}

        # 디렉토리 생성
        self.save_path.mkdir(parents=True, exist_ok=True)

        # 기존 프로필 로드
        self._load_existing_profiles()

    def determine_user_strategy(self, user_id: str) -> str:
        """사용자 상태에 따른 전략 결정"""
        profile = self.get_user_profile(user_id)

        if not profile or profile.interaction_count < 3:
            return "onboarding_mode"  # 신규 유저
        elif profile.data_completeness < 0.6:
            return "data_building_mode"  # 데이터 부족 유저
        else:
            return "normal_mode"  # 충분한 데이터를 가진 유저

    def calculate_data_completeness(self, profile: UserProfile) -> float:
        """데이터 완성도 계산"""
        total_fields = 8  # 중요한 필드 개수
        completed_fields = 0

        if profile.preferred_categories:
            completed_fields += 1
        if profile.average_budget:
            completed_fields += 1
        if profile.taste_preferences:
            completed_fields += 1
        if profile.companion_patterns:
            completed_fields += 1
        if profile.location_preferences:
            completed_fields += 1
        if profile.favorite_shops:
            completed_fields += 1
        if profile.interaction_count >= 5:
            completed_fields += 1
        if len(profile.recent_orders) >= 3:
            completed_fields += 1

        return completed_fields / total_fields

    def update_learning_data(self, user_id: str, learning_data: LearningData):
        """학습 데이터로 프로필 업데이트"""
        profile = self.get_or_create_user_profile(user_id)

        # 상호작용 횟수 증가
        profile.interaction_count += 1

        # 새로운 데이터 통합
        if learning_data.food_preferences:
            for food in learning_data.food_preferences:
                if food not in profile.preferred_categories:
                    profile.preferred_categories.append(food)

        if learning_data.budget_patterns:
            avg_budget = sum(learning_data.budget_patterns) / len(learning_data.budget_patterns)
            if profile.average_budget:
                profile.average_budget = int((profile.average_budget + avg_budget) / 2)
            else:
                profile.average_budget = int(avg_budget)

        if learning_data.taste_preferences:
            profile.taste_preferences.update(learning_data.taste_preferences)

        if learning_data.companion_patterns:
            for companion in learning_data.companion_patterns:
                if companion not in profile.companion_patterns:
                    profile.companion_patterns.append(companion)

        # 데이터 완성도 재계산
        profile.data_completeness = self.calculate_data_completeness(profile)

        # 프로필 저장
        self._save_user_profile(profile)

    def _load_existing_profiles(self):
        """기존 사용자 프로필 로드"""
        if not self.enable_personalization:
            return

        try:
            profile_files = list(self.save_path.glob("*.json"))
            loaded_count = 0

            for profile_file in profile_files:
                user_id = profile_file.stem
                try:
                    with open(profile_file, 'r', encoding='utf-8') as f:
                        profile_data = json.load(f)

                    # JSON을 UserProfile 객체로 변환
                    profile = UserProfile(
                        user_id=profile_data["user_id"],
                        preferred_categories=profile_data.get("preferred_categories", []),
                        average_budget=profile_data.get("average_budget"),
                        favorite_shops=profile_data.get("favorite_shops", []),
                        recent_orders=profile_data.get("recent_orders", []),
                        conversation_style=profile_data.get("conversation_style", "friendly"),
                        last_updated=datetime.fromisoformat(profile_data.get("last_updated", datetime.now().isoformat()))
                    )

                    self.user_profiles[user_id] = profile
                    loaded_count += 1

                except Exception as e:
                    logger.warning(f"프로필 로드 실패 ({profile_file}): {e}")

            logger.info(f"사용자 프로필 {loaded_count}개 로드 완료")

        except Exception as e:
            logger.warning(f"프로필 로드 실패: {e}")

    def get_or_create_user_profile(self, user_id: str) -> UserProfile:
        """사용자 프로필 조회 또는 생성"""
        if not self.enable_personalization:
            # 개인화 비활성화시 기본 프로필 반환
            return UserProfile(user_id=user_id)

        if user_id not in self.user_profiles:
            # 새 사용자 프로필 생성
            new_profile = UserProfile(
                user_id=user_id,
                conversation_style="friendly",  # 기본값
                last_updated=datetime.now()
            )

            self.user_profiles[user_id] = new_profile
            self._save_user_profile(new_profile)

            logger.info(f"새 사용자 프로필 생성: {user_id}")

        return self.user_profiles[user_id]

    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """사용자 프로필 조회만"""
        return self.user_profiles.get(user_id)

    def update_user_interaction(
        self,
        user_id: str,
        extracted_info: ExtractedInfo,
        emotion: EmotionType = EmotionType.NEUTRAL
    ):
        """사용자 상호작용 업데이트"""
        if not self.enable_personalization:
            return

        profile = self.get_or_create_user_profile(user_id)

        profile.interaction_count += 1

        # 선호 카테고리 업데이트
        if extracted_info.entities and extracted_info.entities.food_type:
            food_type = extracted_info.entities.food_type
            if food_type not in profile.preferred_categories:
                profile.preferred_categories.append(food_type)
                # 최대 5개까지만 유지
                if len(profile.preferred_categories) > 5:
                    profile.preferred_categories = profile.preferred_categories[-5:]

        # 예산 정보 업데이트
        if extracted_info.entities and extracted_info.entities.budget:
            budget = extracted_info.entities.budget
            if profile.average_budget is None:
                profile.average_budget = budget
            else:
                # 이동 평균으로 업데이트
                profile.average_budget = int((profile.average_budget * 0.7) + (budget * 0.3))

        profile.data_completeness = self.calculate_data_completeness(profile)
        # 대화 스타일 학습
        self._update_conversation_style(profile, emotion)

        # 최근 주문 정보 추가
        if extracted_info.intent == IntentType.FOOD_REQUEST:#ExtractedInfo.FOOD_REQUEST:
            order_info = {
                "timestamp": datetime.now().isoformat(),
                "intent": extracted_info.intent.value,
                "food_type": extracted_info.entities.food_type if extracted_info.entities else None,
                "budget": extracted_info.entities.budget if extracted_info.entities else None,
                "emotion": emotion.value
            }
            profile.update_preferences(order_info)

        profile.data_completeness = self.calculate_data_completeness(profile)
        # 프로필 저장
        self._save_user_profile(profile)

    def _update_conversation_style(self, profile: UserProfile, emotion: EmotionType):
        """대화 스타일 학습"""
        # 감정 기반 스타일 조정
        emotion_to_style = {
            EmotionType.EXCITED: "excited",
            EmotionType.POSITIVE: "friendly",
            EmotionType.NEUTRAL: "professional",
            EmotionType.NEGATIVE: "polite",
            EmotionType.DISAPPOINTED: "encouraging"
        }

        suggested_style = emotion_to_style.get(emotion, "friendly")

        # 기존 스타일과 새 스타일 블렌딩 (점진적 변화)
        if profile.conversation_style != suggested_style:
            # 간단한 업데이트 로직 (실제로는 더 정교할 수 있음)
            style_weights = {
                "excited": 1,
                "friendly": 2,
                "professional": 1,
                "polite": 1,
                "encouraging": 1
            }

            current_weight = style_weights.get(profile.conversation_style, 1)
            suggested_weight = style_weights.get(suggested_style, 1)

            # 가중치가 높은 스타일로 점진적 변화
            if suggested_weight > current_weight:
                profile.conversation_style = suggested_style

    def _save_user_profile(self, profile: UserProfile):
        """사용자 프로필 저장"""
        if not self.enable_personalization:
            return

        try:
            profile_file = self.save_path / f"{profile.user_id}.json"

            # UserProfile을 JSON으로 변환
            profile_data = {
                "user_id": profile.user_id,
                "preferred_categories": profile.preferred_categories,
                "average_budget": profile.average_budget,
                "favorite_shops": profile.favorite_shops,
                "recent_orders": profile.recent_orders,
                "conversation_style": profile.conversation_style,
                "last_updated": profile.last_updated.isoformat(),
                "taste_preferences": profile.taste_preferences,
                "companion_patterns": profile.companion_patterns,
                "location_preferences": profile.location_preferences,
                "good_influence_preference": profile.good_influence_preference,
                "interaction_count": profile.interaction_count,
                "data_completeness": profile.data_completeness
            }

            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"프로필 저장 실패 ({profile.user_id}): {e}")

    def add_favorite_shop(self, user_id: str, shop_id: int):
        """즐겨찾는 가게 추가"""
        profile = self.get_or_create_user_profile(user_id)

        if shop_id not in profile.favorite_shops:
            profile.favorite_shops.append(shop_id)
            # 최대 10개까지만 유지
            if len(profile.favorite_shops) > 10:
                profile.favorite_shops = profile.favorite_shops[-10:]

            self._save_user_profile(profile)
            logger.info(f"사용자 {user_id} 즐겨찾기 추가: {shop_id}")

    def remove_favorite_shop(self, user_id: str, shop_id: int):
        """즐겨찾는 가게 제거"""
        profile = self.get_user_profile(user_id)
        if profile and shop_id in profile.favorite_shops:
            profile.favorite_shops.remove(shop_id)
            self._save_user_profile(profile)
            logger.info(f"사용자 {user_id} 즐겨찾기 제거: {shop_id}")

    def get_user_preferences_summary(self, user_id: str) -> Dict[str, Any]:
        """사용자 선호도 요약"""
        profile = self.get_user_profile(user_id)

        if not profile:
            return {
                "user_id": user_id,
                "has_profile": False,
                "preferred_categories": [],
                "average_budget": None,
                "favorite_count": 0,
                "conversation_style": "friendly",
                "interaction_count": 0
            }

        return {
            "user_id": user_id,
            "has_profile": True,
            "preferred_categories": profile.preferred_categories,
            "average_budget": profile.average_budget,
            "favorite_count": len(profile.favorite_shops),
            "conversation_style": profile.conversation_style,
            "interaction_count": len(profile.recent_orders),
            "last_updated": profile.last_updated.isoformat(),
            "days_since_last_interaction": (datetime.now() - profile.last_updated).days
        }

    def personalize_response(self, response: ChatbotResponse, profile: UserProfile) -> ChatbotResponse:
        """응답 개인화"""
        if not self.enable_personalization or not profile:
            return response

        # 대화 스타일에 맞게 응답 톤 조정
        personalized_text = self._adjust_response_tone(response.text, profile.conversation_style)

        # 개인 선호도 기반 추가 정보
        additional_info = self._add_personalized_info(response, profile)

        if additional_info:
            personalized_text += f" {additional_info}"

        # 응답 복사 후 수정
        personalized_response = ChatbotResponse(
            text=personalized_text,
            recommendations=response.recommendations,
            follow_up_questions=response.follow_up_questions,
            action_required=response.action_required,
            metadata=response.metadata.copy()
        )

        # 메타데이터에 개인화 정보 추가
        personalized_response.metadata["personalized"] = True
        personalized_response.metadata["user_style"] = profile.conversation_style

        return personalized_response

    def _adjust_response_tone(self, text: str, conversation_style: str) -> str:
        """대화 스타일에 맞게 응답 톤 조정"""

        if conversation_style == "excited":
            # 신나는 톤으로 변환
            text = text.replace("좋아요", "완전 좋아요!")
            text = text.replace("추천드려요", "강추해요!")
            if not text.endswith('!'):
                text = text.rstrip('.') + "!"

        elif conversation_style == "casual":
            # 캐주얼한 톤으로 변환
            text = text.replace("습니다", "어요")
            text = text.replace("드세요", "보세요")
            if not any(emote in text for emote in ['ㅋㅋ', 'ㅎㅎ', '^^']):
                text += " ㅎㅎ"

        elif conversation_style == "professional":
            # 전문적인 톤으로 변환
            text = text.replace("어요", "습니다")
            text = text.replace("좋아요", "좋습니다")
            text = text.replace("!", ".")

        elif conversation_style == "polite":
            # 정중한 톤으로 변환
            text = text.replace("해요", "해드리겠습니다")
            text = text.replace("드세요", "드시기 바랍니다")

        elif conversation_style == "encouraging":
            # 격려하는 톤으로 변환
            encouraging_words = ["화이팅!", "좋은 선택이에요!", "멋져요!"]
            import random
            text += f" {random.choice(encouraging_words)}"

        return text

    def _add_personalized_info(self, response: ChatbotResponse, profile: UserProfile) -> str:
        """개인 선호도 기반 추가 정보"""
        additional_info = []

        # 선호 카테고리 기반 정보 (guest 제외)
        if (profile.preferred_categories and 
            response.recommendations and 
            hasattr(profile, 'user_name') and 
            profile.user_name != 'guest'):
            for rec in response.recommendations:
                if rec.get('category') in profile.preferred_categories:
                    category = rec.get('category')
                    additional_info.append(f"평소 {category} 좋아하시니까 입맛에 맞을 거예요!")
                    break

        # 예산 기반 정보 (guest 제외)
        if (profile.average_budget and 
            response.recommendations and
            hasattr(profile, 'user_name') and 
            profile.user_name != 'guest'):
            rec = response.recommendations[0]
            rec_price = rec.get('price', 0)

            if rec_price <= profile.average_budget * 0.8:
                additional_info.append("평소 예산보다 저렴해서 더 좋네요!")
            elif rec_price > profile.average_budget * 1.2:
                additional_info.append("평소보다 조금 비싸지만 특별한 날에 좋을 것 같아요!")

        # 즐겨찾는 가게 정보
        if profile.favorite_shops and response.recommendations:
            for rec in response.recommendations:
                if rec.get('shop_id') in profile.favorite_shops:
                    additional_info.append("즐겨찾으시는 가게네요!")
                    break

        return " ".join(additional_info[:1])  # 최대 1개까지만

    def get_user_recommendations_based_on_history(self, user_id: str) -> List[Dict[str, Any]]:
        """사용자 이력 기반 추천"""
        profile = self.get_user_profile(user_id)

        if not profile:
            return []

        recommendations = []

        # 선호 카테고리 기반 추천
        for category in profile.preferred_categories[:3]:  # 상위 3개
            recommendations.append({
                "type": "preferred_category",
                "category": category,
                "reason": f"평소 {category} 자주 드시더라고요!",
                "confidence": 0.8
            })

        # 예산 기반 추천
        if profile.average_budget:
            recommendations.append({
                "type": "budget_friendly",
                "budget_range": f"{profile.average_budget-1000}~{profile.average_budget+1000}원",
                "reason": f"평소 예산인 {profile.average_budget}원 내외로 추천드릴게요!",
                "confidence": 0.7
            })

        # 즐겨찾는 가게 기반 추천
        if profile.favorite_shops:
            recommendations.append({
                "type": "favorite_shops",
                "shop_ids": profile.favorite_shops[:3],
                "reason": "즐겨찾으시는 가게들이에요!",
                "confidence": 0.9
            })

        return recommendations

    def cleanup_old_profiles(self, days_threshold: int = 30):
        """오래된 프로필 정리"""
        if not self.enable_personalization:
            return

        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        removed_count = 0

        for user_id in list(self.user_profiles.keys()):
            profile = self.user_profiles[user_id]
            if profile.last_updated < cutoff_date:
                # 프로필 파일 삭제
                profile_file = self.save_path / f"{user_id}.json"
                if profile_file.exists():
                    profile_file.unlink()

                # 메모리에서 제거
                del self.user_profiles[user_id]
                removed_count += 1

        logger.info(f"오래된 프로필 {removed_count}개 정리 완료")

    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """사용자 데이터 내보내기"""
        profile = self.get_user_profile(user_id)

        if not profile:
            return {"error": "사용자 프로필을 찾을 수 없습니다"}

        return {
            "user_id": user_id,
            "profile_data": {
                "preferred_categories": profile.preferred_categories,
                "average_budget": profile.average_budget,
                "favorite_shops": profile.favorite_shops,
                "recent_orders": profile.recent_orders,
                "conversation_style": profile.conversation_style,
                "last_updated": profile.last_updated.isoformat()
            },
            "export_timestamp": datetime.now().isoformat()
        }

    def delete_user_data(self, user_id: str) -> bool:
        """사용자 데이터 삭제 (GDPR 대응)"""
        try:
            # 메모리에서 제거
            if user_id in self.user_profiles:
                del self.user_profiles[user_id]

            # 파일에서 제거
            profile_file = self.save_path / f"{user_id}.json"
            if profile_file.exists():
                profile_file.unlink()

            logger.info(f"사용자 {user_id} 데이터 삭제 완료")
            return True

        except Exception as e:
            logger.error(f"사용자 데이터 삭제 실패 ({user_id}): {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """사용자 관리 통계"""
        total_users = len(self.user_profiles)

        if total_users == 0:
            return {
                "total_users": 0,
                "personalization_enabled": self.enable_personalization
            }

        # 대화 스타일 분포
        style_distribution = {}
        budget_stats = []
        category_frequency = {}

        for profile in self.user_profiles.values():
            # 스타일 분포
            style = profile.conversation_style
            style_distribution[style] = style_distribution.get(style, 0) + 1

            # 예산 통계
            if profile.average_budget:
                budget_stats.append(profile.average_budget)

            # 카테고리 빈도
            for category in profile.preferred_categories:
                category_frequency[category] = category_frequency.get(category, 0) + 1

        # 통계 계산
        avg_budget = sum(budget_stats) / len(budget_stats) if budget_stats else 0
        most_popular_category = max(category_frequency, key=category_frequency.get) if category_frequency else None

        return {
            "total_users": total_users,
            "personalization_enabled": self.enable_personalization,
            "conversation_style_distribution": style_distribution,
            "average_user_budget": int(avg_budget),
            "users_with_budget_info": len(budget_stats),
            "most_popular_category": most_popular_category,
            "category_distribution": category_frequency,
            "users_with_favorites": sum(1 for p in self.user_profiles.values() if p.favorite_shops),
            "avg_favorite_count": sum(len(p.favorite_shops) for p in self.user_profiles.values()) / total_users
        }

# 편의 함수들
def create_user_manager(save_path: str, enable_personalization: bool = True) -> NaviyamUserManager:
    """사용자 관리자 생성 (편의 함수)"""
    return NaviyamUserManager(save_path, enable_personalization)

def quick_user_update(user_manager: NaviyamUserManager, user_id: str, food_type: str, budget: int = None):
    """빠른 사용자 정보 업데이트 (편의 함수)"""
    from data.data_structure import ExtractedInfo, ExtractedEntity, IntentType

    entities = ExtractedEntity(food_type=food_type, budget=budget)
    extracted_info = ExtractedInfo(
        intent=IntentType.FOOD_REQUEST,
        entities=entities,
        confidence=1.0,
        raw_text=""
    )

    user_manager.update_user_interaction(user_id, extracted_info)