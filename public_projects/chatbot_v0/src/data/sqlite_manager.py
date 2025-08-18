"""
간단한 SQLite 기반 데이터 영속성 관리자
서버 재시작해도 데이터 유지
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class SQLiteDataManager:
    """간단한 SQLite 데이터 관리자"""
    
    def __init__(self, db_path: str = "data/naviyam.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()
        
    def _init_database(self):
        """데이터베이스 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 대화 로그 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    input_text TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    intent TEXT,
                    entities TEXT,
                    recommendations TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 사용자 프로필 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    preferred_categories TEXT,
                    average_budget INTEGER,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 학습 데이터 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    input_text TEXT NOT NULL,
                    output_text TEXT NOT NULL,
                    context TEXT,
                    feedback REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            logger.info("SQLite 데이터베이스 초기화 완료")
    
    def save_conversation(self, user_id: str, input_text: str, response_text: str,
                         intent: str = None, entities: Dict = None, 
                         recommendations: List = None):
        """대화 저장"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversations 
                (user_id, input_text, response_text, intent, entities, recommendations)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                input_text,
                response_text,
                intent,
                json.dumps(entities) if entities else None,
                json.dumps(recommendations) if recommendations else None
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_user_conversations(self, user_id: str, limit: int = 10) -> List[Dict]:
        """사용자 대화 이력 조회"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, input_text, response_text, intent, entities, 
                       recommendations, timestamp
                FROM conversations
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, limit))
            
            rows = cursor.fetchall()
            conversations = []
            for row in rows:
                conversations.append({
                    'id': row[0],
                    'input_text': row[1],
                    'response_text': row[2],
                    'intent': row[3],
                    'entities': json.loads(row[4]) if row[4] else None,
                    'recommendations': json.loads(row[5]) if row[5] else None,
                    'timestamp': row[6]
                })
            return conversations
    
    def update_user_profile(self, user_id: str, preferred_categories: List[str] = None,
                           average_budget: int = None):
        """사용자 프로필 업데이트"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO user_profiles 
                (user_id, preferred_categories, average_budget, last_updated)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                user_id,
                json.dumps(preferred_categories) if preferred_categories else None,
                average_budget
            ))
            conn.commit()
    
    def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """사용자 프로필 조회"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT preferred_categories, average_budget, last_updated
                FROM user_profiles
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'user_id': user_id,
                    'preferred_categories': json.loads(row[0]) if row[0] else [],
                    'average_budget': row[1],
                    'last_updated': row[2]
                }
            return None
    
    def save_learning_data(self, input_text: str, output_text: str, 
                          context: Dict = None, feedback: float = None):
        """학습 데이터 저장"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO learning_data 
                (input_text, output_text, context, feedback)
                VALUES (?, ?, ?, ?)
            """, (
                input_text,
                output_text,
                json.dumps(context) if context else None,
                feedback
            ))
            conn.commit()
    
    def get_learning_data(self, limit: int = 100) -> List[Dict]:
        """학습 데이터 조회"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT input_text, output_text, context, feedback, timestamp
                FROM learning_data
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            data = []
            for row in rows:
                data.append({
                    'input_text': row[0],
                    'output_text': row[1],
                    'context': json.loads(row[2]) if row[2] else None,
                    'feedback': row[3],
                    'timestamp': row[4]
                })
            return data
    
    def get_statistics(self) -> Dict[str, Any]:
        """통계 정보"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 총 대화 수
            cursor.execute("SELECT COUNT(*) FROM conversations")
            total_conversations = cursor.fetchone()[0]
            
            # 사용자 수
            cursor.execute("SELECT COUNT(DISTINCT user_id) FROM conversations")
            total_users = cursor.fetchone()[0]
            
            # 학습 데이터 수
            cursor.execute("SELECT COUNT(*) FROM learning_data")
            total_learning_data = cursor.fetchone()[0]
            
            # 인기 인텐트
            cursor.execute("""
                SELECT intent, COUNT(*) as cnt
                FROM conversations
                WHERE intent IS NOT NULL
                GROUP BY intent
                ORDER BY cnt DESC
                LIMIT 5
            """)
            popular_intents = cursor.fetchall()
            
            return {
                'total_conversations': total_conversations,
                'total_users': total_users,
                'total_learning_data': total_learning_data,
                'popular_intents': popular_intents,
                'database_size_mb': self.db_path.stat().st_size / (1024 * 1024)
            }

# 편의 함수
_manager = None

def get_data_manager() -> SQLiteDataManager:
    """싱글톤 데이터 매니저"""
    global _manager
    if _manager is None:
        _manager = SQLiteDataManager()
    return _manager