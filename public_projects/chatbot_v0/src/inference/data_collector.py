"""
학습 데이터 수집 및 저장 전담 클래스
실시간 데이터 수집, 검증, 저장 관리
"""

import json
import csv
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import asdict, dataclass
import logging
from collections import defaultdict, deque
import threading
import queue
import time

from src.data.data_structure import UserProfile, ExtractedInfo, LearningData, UserState

logger = logging.getLogger(__name__)


@dataclass
class CollectionSession:
    """데이터 수집 세션"""
    session_id: str
    user_id: str
    start_time: datetime
    data_points: List[Dict[str, Any]]
    status: str = "active"  # active, completed, error


@dataclass
class DataQualityMetrics:
    """데이터 품질 지표"""
    total_collected: int = 0
    valid_samples: int = 0
    invalid_samples: int = 0
    missing_fields: Dict[str, int] = None
    confidence_distribution: Dict[str, int] = None

    def __post_init__(self):
        if self.missing_fields is None:
            self.missing_fields = {}
        if self.confidence_distribution is None:
            self.confidence_distribution = {}


class LearningDataCollector:
    """나비얌 학습 데이터 수집기"""

    def __init__(self, save_path: str, buffer_size: int = 100, auto_save_interval: int = 300):
        """
        Args:
            save_path: 데이터 저장 경로
            buffer_size: 버퍼링할 데이터 개수
            auto_save_interval: 자동 저장 간격 (초)
        """
        self.save_path = Path(save_path)
        self.buffer_size = buffer_size
        self.auto_save_interval = auto_save_interval

        # 디렉토리 생성
        self.save_path.mkdir(parents=True, exist_ok=True)
        (self.save_path / "raw").mkdir(exist_ok=True)
        (self.save_path / "processed").mkdir(exist_ok=True)
        (self.save_path / "sessions").mkdir(exist_ok=True)

        # 데이터 버퍼들
        self.nlu_buffer = deque(maxlen=buffer_size)
        self.interaction_buffer = deque(maxlen=buffer_size)
        self.recommendation_buffer = deque(maxlen=buffer_size)
        self.feedback_buffer = deque(maxlen=buffer_size)

        # 실시간 세션 관리
        self.active_sessions: Dict[str, CollectionSession] = {}
        self.session_timeout = timedelta(hours=2)

        # 데이터 품질 관리
        self.quality_metrics = DataQualityMetrics()

        # 스레드 안전성
        self.lock = threading.Lock()
        self.save_queue = queue.Queue()

        # 자동 저장 스레드
        self.auto_save_thread = None
        self.is_running = False
        self._start_auto_save_thread()

        logger.info(f"학습 데이터 수집기 초기화 완료: {self.save_path}")

    def _start_auto_save_thread(self):
        """자동 저장 스레드 시작"""
        if self.auto_save_thread and self.auto_save_thread.is_alive():
            return

        self.is_running = True
        self.auto_save_thread = threading.Thread(target=self._auto_save_worker, daemon=True)
        self.auto_save_thread.start()

    def _auto_save_worker(self):
        """자동 저장 워커"""
        while self.is_running:
            try:
                time.sleep(self.auto_save_interval)
                if self.is_running:  # 종료 체크
                    self._flush_all_buffers()
                    self._cleanup_old_sessions()
            except Exception as e:
                logger.error(f"자동 저장 실패: {e}")

    def collect_nlu_features(self, user_id: str, features: Dict[str, Any]):
        """NLU에서 추출된 Feature 수집"""
        try:
            data_point = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "data_type": "nlu_features",
                "features": features.copy()
            }

            with self.lock:
                self.nlu_buffer.append(data_point)
                self.quality_metrics.total_collected += 1

            # 세션에 추가
            self._add_to_session(user_id, data_point)

            logger.debug(f"NLU Feature 수집: {user_id}, {len(features)} features")

        except Exception as e:
            logger.error(f"NLU Feature 수집 실패: {e}")

    def collect_interaction_data(self, user_id: str, interaction_data: Dict[str, Any]):
        """사용자 상호작용 데이터 수집"""
        try:
            data_point = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "data_type": "interaction",
                "interaction": interaction_data.copy()
            }

            with self.lock:
                self.interaction_buffer.append(data_point)
                self.quality_metrics.total_collected += 1

            self._add_to_session(user_id, data_point)

            logger.debug(f"상호작용 데이터 수집: {user_id}")

        except Exception as e:
            logger.error(f"상호작용 데이터 수집 실패: {e}")

    def collect_recommendation_data(self, user_id: str, recommendations: List[Dict],
                                    user_selection: Optional[Dict] = None):
        """추천 및 선택 데이터 수집"""
        try:
            data_point = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "data_type": "recommendation",
                "recommendations": recommendations.copy(),
                "user_selection": user_selection.copy() if user_selection else None,
                "recommendation_count": len(recommendations)
            }

            with self.lock:
                self.recommendation_buffer.append(data_point)
                self.quality_metrics.total_collected += 1

            self._add_to_session(user_id, data_point)

            logger.debug(f"추천 데이터 수집: {user_id}, {len(recommendations)} recommendations")

        except Exception as e:
            logger.error(f"추천 데이터 수집 실패: {e}")

    def collect_feedback_data(self, user_id: str, feedback_type: str, feedback_content: Any,
                              context: Dict[str, Any] = None):
        """사용자 피드백 데이터 수집"""
        try:
            data_point = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "data_type": "feedback",
                "feedback_type": feedback_type,  # "selection", "rating", "text", "implicit"
                "feedback_content": feedback_content,
                "context": context.copy() if context else {}
            }

            with self.lock:
                self.feedback_buffer.append(data_point)
                self.quality_metrics.total_collected += 1

            self._add_to_session(user_id, data_point)

            logger.debug(f"피드백 데이터 수집: {user_id}, type: {feedback_type}")

        except Exception as e:
            logger.error(f"피드백 데이터 수집 실패: {e}")

    def collect_learning_data(self, user_id: str, learning_data: LearningData):
        """구조화된 학습 데이터 수집"""
        try:
            data_point = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "data_type": "structured_learning",
                "learning_data": asdict(learning_data)
            }

            # 데이터 품질 검증
            is_valid, quality_score = self._validate_learning_data(learning_data)
            data_point["quality_score"] = quality_score
            data_point["is_valid"] = is_valid

            with self.lock:
                if is_valid:
                    self.quality_metrics.valid_samples += 1
                else:
                    self.quality_metrics.invalid_samples += 1

            # 버퍼에는 검증 결과와 함께 저장
            self._add_to_appropriate_buffer(data_point)
            self._add_to_session(user_id, data_point)

            logger.debug(f"구조화 학습 데이터 수집: {user_id}, quality: {quality_score:.2f}")

        except Exception as e:
            logger.error(f"구조화 학습 데이터 수집 실패: {e}")

    def _validate_learning_data(self, learning_data: LearningData) -> Tuple[bool, float]:
        """학습 데이터 품질 검증"""
        score = 0.0
        max_score = 10.0

        # 필수 필드 체크
        if learning_data.user_id:
            score += 2.0
        if learning_data.extracted_entities:
            score += 2.0
        if learning_data.intent_confidence > 0:
            score += 1.0

        # 선택적 필드 체크 (더 풍부한 데이터)
        if learning_data.food_preferences:
            score += 1.0
        if learning_data.budget_patterns:
            score += 1.0
        if learning_data.companion_patterns:
            score += 1.0
        if learning_data.taste_preferences:
            score += 1.0
        if learning_data.user_selection:
            score += 1.0

        # 신뢰도 기반 가중치
        confidence_weight = learning_data.intent_confidence
        final_score = (score / max_score) * confidence_weight

        is_valid = final_score >= 0.5  # 50% 이상이면 유효

        return is_valid, final_score

    def _add_to_appropriate_buffer(self, data_point: Dict[str, Any]):
        """데이터 타입에 따라 적절한 버퍼에 추가"""
        data_type = data_point.get("data_type", "unknown")

        with self.lock:
            if data_type == "nlu_features":
                self.nlu_buffer.append(data_point)
            elif data_type == "interaction":
                self.interaction_buffer.append(data_point)
            elif data_type == "recommendation":
                self.recommendation_buffer.append(data_point)
            elif data_type == "feedback":
                self.feedback_buffer.append(data_point)
            else:
                # 기본적으로 interaction 버퍼에
                self.interaction_buffer.append(data_point)

    def _add_to_session(self, user_id: str, data_point: Dict[str, Any]):
        """세션에 데이터 포인트 추가"""
        session_id = f"{user_id}_{datetime.now().strftime('%Y%m%d')}"

        with self.lock:
            if session_id not in self.active_sessions:
                self.active_sessions[session_id] = CollectionSession(
                    session_id=session_id,
                    user_id=user_id,
                    start_time=datetime.now(),
                    data_points=[]
                )

            self.active_sessions[session_id].data_points.append(data_point)

    def get_user_learning_data(self, user_id: str, days: int = 7) -> List[Dict[str, Any]]:
        """사용자별 학습 데이터 조회"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        user_data = []

        # 활성 세션에서 검색
        with self.lock:
            for session in self.active_sessions.values():
                if session.user_id == user_id:
                    for data_point in session.data_points:
                        timestamp = datetime.fromisoformat(data_point["timestamp"])
                        if start_date <= timestamp <= end_date:
                            user_data.append(data_point)

        # 저장된 파일에서도 검색 (구현 시 추가)

        return user_data

    def get_data_completeness_score(self, user_id: str) -> float:
        """사용자 데이터 완성도 점수 계산"""
        user_data = self.get_user_learning_data(user_id, days=30)

        if not user_data:
            return 0.0

        # 데이터 타입별 점수
        type_scores = {
            "nlu_features": 0,
            "interaction": 0,
            "recommendation": 0,
            "feedback": 0
        }

        for data in user_data:
            data_type = data.get("data_type", "unknown")
            if data_type in type_scores:
                type_scores[data_type] += 1

        # 각 타입별 최소 요구사항
        requirements = {
            "nlu_features": 5,  # 최소 5개 NLU 기록
            "interaction": 3,  # 최소 3개 상호작용
            "recommendation": 2,  # 최소 2개 추천 기록
            "feedback": 1  # 최소 1개 피드백
        }

        total_score = 0.0
        for data_type, required in requirements.items():
            actual = type_scores[data_type]
            score = min(actual / required, 1.0)  # 최대 1.0
            total_score += score

        return total_score / len(requirements)  # 평균 점수

    def _flush_all_buffers(self):
        """모든 버퍼 데이터 저장"""
        try:
            current_time = datetime.now()
            date_str = current_time.strftime("%Y%m%d")

            with self.lock:
                # 각 버퍼별로 저장
                self._save_buffer_to_file(self.nlu_buffer, f"nlu_features_{date_str}")
                self._save_buffer_to_file(self.interaction_buffer, f"interactions_{date_str}")
                self._save_buffer_to_file(self.recommendation_buffer, f"recommendations_{date_str}")
                self._save_buffer_to_file(self.feedback_buffer, f"feedback_{date_str}")

                # 버퍼 클리어
                self.nlu_buffer.clear()
                self.interaction_buffer.clear()
                self.recommendation_buffer.clear()
                self.feedback_buffer.clear()

            logger.info("모든 버퍼 데이터 저장 완료")

        except Exception as e:
            logger.error(f"버퍼 저장 실패: {e}")

    def _make_json_serializable(self, obj: Any, visited=None) -> Any:
        """객체를 JSON 직렬화 가능한 형태로 변환 (순환 참조 방지)"""
        if visited is None:
            visited = set()
        
        # 순환 참조 체크
        obj_id = id(obj)
        if obj_id in visited:
            return None  # 순환 참조 발견 시 None 반환
        
        if isinstance(obj, (str, int, float, bool, type(None))):
            if isinstance(obj, str):
                # 문자열에서 이모지 제거 (저장 시만)
                import re
                emoji_pattern = re.compile('[\U00010000-\U0010ffff]', flags=re.UNICODE)
                return emoji_pattern.sub('', obj)
            return obj
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            visited.add(obj_id)
            return {k: self._make_json_serializable(v, visited) for k, v in obj.items()}
        elif isinstance(obj, (list, deque)):
            visited.add(obj_id)
            return [self._make_json_serializable(item, visited) for item in obj]
        elif hasattr(obj, '__dict__'):
            visited.add(obj_id)
            # mappingproxy 타입 처리
            if type(obj.__dict__).__name__ == 'mappingproxy':
                return self._make_json_serializable(dict(obj.__dict__), visited)
            return self._make_json_serializable(obj.__dict__, visited)
        else:
            return str(obj)  # 기타 타입은 문자열로 변환
    
    def _save_buffer_to_file(self, buffer: deque, filename: str):
        """버퍼 데이터를 파일로 저장"""
        if not buffer:
            return

        file_path = self.save_path / "raw" / f"{filename}.jsonl"

        try:
            # 기존 파일이 있으면 append 모드
            mode = 'a' if file_path.exists() else 'w'

            with open(file_path, mode, encoding='utf-8') as f:
                for data_point in buffer:
                    # 직렬화 가능한 형태로 변환
                    serializable_data = self._make_json_serializable(data_point)
                    f.write(json.dumps(serializable_data, ensure_ascii=False) + '\n')

            logger.debug(f"버퍼 저장 완료: {filename}, {len(buffer)} items")

        except Exception as e:
            logger.error(f"버퍼 저장 실패 ({filename}): {e}")

    def _cleanup_old_sessions(self):
        """오래된 세션 정리"""
        current_time = datetime.now()
        expired_sessions = []

        with self.lock:
            for session_id, session in self.active_sessions.items():
                if current_time - session.start_time > self.session_timeout:
                    expired_sessions.append(session_id)

        # 만료된 세션 저장 후 제거
        for session_id in expired_sessions:
            self._save_session(self.active_sessions[session_id])
            del self.active_sessions[session_id]

        if expired_sessions:
            logger.info(f"만료된 세션 {len(expired_sessions)}개 정리")

    def _save_session(self, session: CollectionSession):
        """세션 데이터 저장"""
        try:
            session_file = self.save_path / "sessions" / f"{session.session_id}.json"

            session_data = {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "start_time": session.start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "data_points_count": len(session.data_points),
                "status": "completed",
                "data_points": session.data_points
            }

            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)

            logger.debug(f"세션 저장 완료: {session.session_id}")

        except Exception as e:
            logger.error(f"세션 저장 실패 ({session.session_id}): {e}")

    def export_training_data(self, output_path: str, format: str = "jsonl", days: int = 30) -> bool:
        """학습용 데이터 익스포트"""
        try:
            output_path = Path(output_path)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # 모든 데이터 수집
            all_data = []

            # 원시 데이터 파일들에서 수집
            raw_files = list((self.save_path / "raw").glob("*.jsonl"))

            for file_path in raw_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            data = json.loads(line.strip())
                            timestamp = datetime.fromisoformat(data["timestamp"])
                            if start_date <= timestamp <= end_date:
                                all_data.append(data)
                except Exception as e:
                    logger.warning(f"파일 읽기 실패 ({file_path}): {e}")

            # 활성 버퍼에서도 수집
            with self.lock:
                for buffer in [self.nlu_buffer, self.interaction_buffer,
                               self.recommendation_buffer, self.feedback_buffer]:
                    for data in buffer:
                        timestamp = datetime.fromisoformat(data["timestamp"])
                        if start_date <= timestamp <= end_date:
                            all_data.append(data)

            # 데이터 정렬 (시간순)
            all_data.sort(key=lambda x: x["timestamp"])

            # 포맷에 따라 저장
            if format.lower() == "jsonl":
                with open(output_path, 'w', encoding='utf-8') as f:
                    for data in all_data:
                        f.write(json.dumps(data, ensure_ascii=False) + '\n')

            elif format.lower() == "json":
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(all_data, f, ensure_ascii=False, indent=2)

            elif format.lower() == "csv":
                # CSV는 플랫한 구조로 변환 필요
                self._export_to_csv(all_data, output_path)

            logger.info(f"학습 데이터 익스포트 완료: {output_path}, {len(all_data)} records")
            return True

        except Exception as e:
            logger.error(f"학습 데이터 익스포트 실패: {e}")
            return False

    def _export_to_csv(self, data: List[Dict], output_path: Path):
        """CSV 형태로 데이터 익스포트"""
        if not data:
            return

        # 플랫한 구조로 변환
        flat_data = []
        for item in data:
            flat_item = {
                "timestamp": item["timestamp"],
                "user_id": item["user_id"],
                "data_type": item["data_type"]
            }

            # 타입별로 중요 필드 추출
            if item["data_type"] == "nlu_features":
                features = item.get("features", {})
                flat_item.update({
                    "intent": features.get("nlu_intent", ""),
                    "confidence": features.get("nlu_confidence", 0),
                    "food_mentioned": features.get("food_category_mentioned", ""),
                    "budget_mentioned": features.get("budget_mentioned", 0)
                })

            elif item["data_type"] == "recommendation":
                flat_item.update({
                    "recommendation_count": item.get("recommendation_count", 0),
                    "user_selected": item.get("user_selection") is not None
                })

            # 기타 공통 필드들...

            flat_data.append(flat_item)

        # CSV 작성
        if flat_data:
            fieldnames = flat_data[0].keys()
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(flat_data)

    def get_collection_statistics(self) -> Dict[str, Any]:
        """데이터 수집 통계 반환"""
        with self.lock:
            buffer_stats = {
                "nlu_buffer_size": len(self.nlu_buffer),
                "interaction_buffer_size": len(self.interaction_buffer),
                "recommendation_buffer_size": len(self.recommendation_buffer),
                "feedback_buffer_size": len(self.feedback_buffer),
                "total_buffer_size": (len(self.nlu_buffer) + len(self.interaction_buffer) +
                                      len(self.recommendation_buffer) + len(self.feedback_buffer))
            }

            session_stats = {
                "active_sessions": len(self.active_sessions),
                "total_sessions_today": len([s for s in self.active_sessions.values()
                                             if s.start_time.date() == datetime.now().date()])
            }

            quality_stats = {
                "total_collected": self.quality_metrics.total_collected,
                "valid_samples": self.quality_metrics.valid_samples,
                "invalid_samples": self.quality_metrics.invalid_samples,
                "validity_rate": (self.quality_metrics.valid_samples /
                                  max(self.quality_metrics.total_collected, 1)) * 100
            }

        return {
            "collection_status": "running" if self.is_running else "stopped",
            "buffer_stats": buffer_stats,
            "session_stats": session_stats,
            "quality_stats": quality_stats,
            "save_path": str(self.save_path)
        }

    def force_save(self):
        """강제 저장 (즉시 실행)"""
        self._flush_all_buffers()
        self._cleanup_old_sessions()
        logger.info("강제 저장 완료")

    def shutdown(self):
        """정상 종료"""
        logger.info("데이터 수집기 종료 시작...")

        # 자동 저장 스레드 종료
        self.is_running = False
        if self.auto_save_thread and self.auto_save_thread.is_alive():
            self.auto_save_thread.join(timeout=5)

        # 남은 데이터 모두 저장
        self._flush_all_buffers()

        # 활성 세션 모두 저장
        with self.lock:
            for session in self.active_sessions.values():
                self._save_session(session)
            self.active_sessions.clear()

        logger.info("데이터 수집기 종료 완료")

    def __del__(self):
        """소멸자"""
        try:
            self.shutdown()
        except:
            pass


# 편의 함수들
def create_data_collector(save_path: str, buffer_size: int = 100) -> LearningDataCollector:
    """데이터 수집기 생성 (편의 함수)"""
    return LearningDataCollector(save_path, buffer_size)


def collect_conversation_data(collector: LearningDataCollector, user_id: str, conversation_data: Dict):
    """대화 데이터 일괄 수집 (편의 함수)"""
    if "nlu_features" in conversation_data:
        collector.collect_nlu_features(user_id, conversation_data["nlu_features"])

    if "interaction" in conversation_data:
        collector.collect_interaction_data(user_id, conversation_data["interaction"])

    if "recommendations" in conversation_data:
        collector.collect_recommendation_data(
            user_id,
            conversation_data["recommendations"],
            conversation_data.get("user_selection")
        )

    if "feedback" in conversation_data:
        feedback = conversation_data["feedback"]
        collector.collect_feedback_data(
            user_id,
            feedback.get("type", "implicit"),
            feedback.get("content", ""),
            feedback.get("context", {})
        )