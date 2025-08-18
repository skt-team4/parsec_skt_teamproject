"""
나비얌 챗봇 모니터링 시스템

프로덕션 레벨 로깅, 메트릭 수집, 알림
"""

import logging
import time
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import threading

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """성능 메트릭"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = None


@dataclass
class ErrorEvent:
    """에러 이벤트"""
    error_type: str
    message: str
    timestamp: datetime
    user_id: Optional[str] = None
    context: Dict[str, Any] = None


class MetricsCollector:
    """메트릭 수집기"""
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.counters: Dict[str, int] = defaultdict(int)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """메트릭 기록"""
        with self._lock:
            metric = PerformanceMetric(
                name=name,
                value=value,
                timestamp=datetime.now(),
                tags=tags or {}
            )
            self.metrics[name].append(metric)
    
    def increment_counter(self, name: str, value: int = 1):
        """카운터 증가"""
        with self._lock:
            self.counters[name] += value
    
    def record_time(self, name: str, duration: float):
        """시간 측정 기록"""
        with self._lock:
            self.timers[name].append(duration)
            # 최근 1000개만 유지
            if len(self.timers[name]) > 1000:
                self.timers[name] = self.timers[name][-1000:]
    
    def get_summary(self, metric_name: str, minutes: int = 5) -> Dict[str, Any]:
        """메트릭 요약 통계"""
        with self._lock:
            if metric_name not in self.metrics:
                return {}
            
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            recent_metrics = [
                m for m in self.metrics[metric_name]
                if m.timestamp > cutoff_time
            ]
            
            if not recent_metrics:
                return {}
            
            values = [m.value for m in recent_metrics]
            return {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "last": values[-1] if values else None
            }
    
    def get_all_summaries(self, minutes: int = 5) -> Dict[str, Any]:
        """모든 메트릭 요약"""
        summaries = {}
        for metric_name in self.metrics:
            summaries[metric_name] = self.get_summary(metric_name, minutes)
        
        # 카운터 추가
        summaries["counters"] = dict(self.counters)
        
        # 타이머 통계 추가
        timer_stats = {}
        for timer_name, durations in self.timers.items():
            if durations:
                timer_stats[timer_name] = {
                    "count": len(durations),
                    "avg": sum(durations) / len(durations),
                    "p50": sorted(durations)[len(durations) // 2],
                    "p95": sorted(durations)[int(len(durations) * 0.95)],
                    "p99": sorted(durations)[int(len(durations) * 0.99)]
                }
        summaries["timers"] = timer_stats
        
        return summaries


class ErrorTracker:
    """에러 추적기"""
    
    def __init__(self, max_errors: int = 1000):
        self.max_errors = max_errors
        self.errors: deque = deque(maxlen=max_errors)
        self.error_counts: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
    
    def track_error(self, error_type: str, message: str, 
                   user_id: Optional[str] = None, context: Dict[str, Any] = None):
        """에러 추적"""
        with self._lock:
            error = ErrorEvent(
                error_type=error_type,
                message=message,
                timestamp=datetime.now(),
                user_id=user_id,
                context=context or {}
            )
            self.errors.append(error)
            self.error_counts[error_type] += 1
    
    def get_recent_errors(self, minutes: int = 5) -> List[ErrorEvent]:
        """최근 에러 조회"""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            return [e for e in self.errors if e.timestamp > cutoff_time]
    
    def get_error_summary(self) -> Dict[str, Any]:
        """에러 요약"""
        with self._lock:
            return {
                "total_errors": len(self.errors),
                "error_types": dict(self.error_counts),
                "recent_errors": len(self.get_recent_errors(5))
            }


class HealthChecker:
    """시스템 헬스 체크"""
    
    def __init__(self):
        self.checks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
    
    def register_check(self, name: str, check_func):
        """헬스 체크 등록"""
        self.checks[name] = {
            "func": check_func,
            "last_status": None,
            "last_check": None
        }
    
    def run_checks(self) -> Dict[str, Any]:
        """모든 헬스 체크 실행"""
        results = {}
        
        for name, check_info in self.checks.items():
            try:
                status = check_info["func"]()
                results[name] = {
                    "status": "healthy" if status else "unhealthy",
                    "checked_at": datetime.now().isoformat()
                }
                check_info["last_status"] = status
                check_info["last_check"] = datetime.now()
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e),
                    "checked_at": datetime.now().isoformat()
                }
        
        return results


class ProductionMonitor:
    """프로덕션 모니터링 통합 시스템"""
    
    def __init__(self, log_dir: Optional[Path] = None):
        self.metrics = MetricsCollector()
        self.errors = ErrorTracker()
        self.health = HealthChecker()
        self.log_dir = log_dir
        
        if log_dir:
            log_dir.mkdir(exist_ok=True, parents=True)
        
        # 기본 헬스 체크 등록
        self._register_default_checks()
    
    def _register_default_checks(self):
        """기본 헬스 체크 등록"""
        # 메모리 사용량 체크
        def check_memory():
            import psutil
            memory_percent = psutil.virtual_memory().percent
            return memory_percent < 90  # 90% 미만이면 healthy
        
        # 디스크 사용량 체크
        def check_disk():
            import psutil
            disk_percent = psutil.disk_usage('/').percent
            return disk_percent < 90  # 90% 미만이면 healthy
        
        self.health.register_check("memory", check_memory)
        self.health.register_check("disk", check_disk)
    
    def record_request(self, user_id: str, request_type: str, duration: float, success: bool):
        """API 요청 기록"""
        self.metrics.record_metric("request_duration", duration, {
            "type": request_type,
            "status": "success" if success else "failure"
        })
        
        self.metrics.increment_counter(f"requests_{request_type}")
        if success:
            self.metrics.increment_counter("requests_success")
        else:
            self.metrics.increment_counter("requests_failure")
        
        self.metrics.record_time(f"request_time_{request_type}", duration)
    
    def record_model_inference(self, model_name: str, duration: float, tokens: int):
        """모델 추론 기록"""
        self.metrics.record_metric("model_inference_time", duration, {
            "model": model_name
        })
        self.metrics.record_metric("model_tokens", tokens, {
            "model": model_name
        })
        self.metrics.increment_counter(f"model_inferences_{model_name}")
    
    def record_cache_hit(self, cache_type: str, hit: bool):
        """캐시 히트 기록"""
        if hit:
            self.metrics.increment_counter(f"cache_hits_{cache_type}")
        else:
            self.metrics.increment_counter(f"cache_misses_{cache_type}")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """대시보드용 데이터"""
        metrics_summary = self.metrics.get_all_summaries()
        error_summary = self.errors.get_error_summary()
        health_status = self.health.run_checks()
        
        # 요청 성공률 계산
        total_requests = self.metrics.counters.get("requests_success", 0) + \
                        self.metrics.counters.get("requests_failure", 0)
        success_rate = (self.metrics.counters.get("requests_success", 0) / total_requests * 100) \
                      if total_requests > 0 else 0
        
        return {
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics_summary,
            "errors": error_summary,
            "health": health_status,
            "summary": {
                "total_requests": total_requests,
                "success_rate": f"{success_rate:.1f}%",
                "active_errors": error_summary["recent_errors"]
            }
        }
    
    def save_snapshot(self):
        """현재 상태 스냅샷 저장"""
        if not self.log_dir:
            return
        
        snapshot = self.get_dashboard_data()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        snapshot_file = self.log_dir / f"monitor_snapshot_{timestamp}.json"
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)


# 전역 모니터 인스턴스
_production_monitor: Optional[ProductionMonitor] = None


def get_production_monitor(log_dir: Optional[Path] = None) -> ProductionMonitor:
    """전역 프로덕션 모니터 반환"""
    global _production_monitor
    if _production_monitor is None:
        from utils.config import PathConfig
        path_config = PathConfig()
        log_dir = log_dir or path_config.LOG_DIR / "monitoring"
        _production_monitor = ProductionMonitor(log_dir)
    return _production_monitor


# 간편 함수들
def record_api_request(user_id: str, request_type: str, duration: float, success: bool):
    """API 요청 기록 (간편 함수)"""
    monitor = get_production_monitor()
    monitor.record_request(user_id, request_type, duration, success)


def record_error(error_type: str, message: str, user_id: Optional[str] = None):
    """에러 기록 (간편 함수)"""
    monitor = get_production_monitor()
    monitor.errors.track_error(error_type, message, user_id)