// eventEmitter.ts - 전역 이벤트 관리
type EventCallback = (...args: any[]) => void;

class EventEmitter {
  private events: Record<string, EventCallback[]> = {};

  // 이벤트 리스너 등록
  on(event: string, callback: EventCallback) {
    if (!this.events[event]) {
      this.events[event] = [];
    }
    this.events[event].push(callback);
  }

  // 이벤트 리스너 제거
  off(event: string, callback: EventCallback) {
    if (!this.events[event]) return;
    
    const index = this.events[event].indexOf(callback);
    if (index > -1) {
      this.events[event].splice(index, 1);
    }
  }

  // 이벤트 발생
  emit(event: string, ...args: any[]) {
    if (!this.events[event]) return;
    
    this.events[event].forEach(callback => {
      try {
        callback(...args);
      } catch (error) {
        console.error(`Event callback error for ${event}:`, error);
      }
    });
  }

  // 모든 이벤트 리스너 제거
  removeAllListeners(event?: string) {
    if (event) {
      delete this.events[event];
    } else {
      this.events = {};
    }
  }
}

// 글로벌 이벤트 emitter 인스턴스
export const globalEventEmitter = new EventEmitter();

// 이벤트 타입 정의
export const EVENTS = {
  FOOD_RECORDED: 'food_recorded', // 음식 기록 저장됨
  NUTRITION_UPDATED: 'nutrition_updated', // 영양 정보 업데이트됨
  RICE_PUL_UPDATED: 'rice_pul_updated', // 밥풀 업데이트됨
} as const;