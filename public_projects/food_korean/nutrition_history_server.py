"""
영양소 분석 기록 저장 및 조회 서버
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)

# 데이터 저장 경로
DATA_DIR = 'nutrition_history'
os.makedirs(DATA_DIR, exist_ok=True)

def load_history():
    """저장된 기록 불러오기"""
    history_file = os.path.join(DATA_DIR, 'history.json')
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_history(history):
    """기록 저장"""
    history_file = os.path.join(DATA_DIR, 'history.json')
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

@app.route('/api/save-nutrition', methods=['POST'])
def save_nutrition():
    """영양소 분석 결과 저장"""
    try:
        data = request.json
        
        # 고유 ID 생성
        record_id = str(uuid.uuid4())
        
        # 기록 생성
        record = {
            'id': record_id,
            'timestamp': datetime.now().isoformat(),
            'foodName': data.get('foodName', ''),
            'mealType': data.get('mealType', ''),
            'imageUri': data.get('imageUri', ''),
            'calories': round(data.get('calories', 0)),  # 정수로 저장
            'nutritionInfo': data.get('nutritionInfo', {}),
            'nutriScore': data.get('nutriScore', {}),
            'userId': data.get('userId', 'guest')
        }
        
        # 기존 기록 불러오기
        history = load_history()
        
        # 새 기록 추가 (최신 기록이 앞에)
        history.insert(0, record)
        
        # 최대 1000개까지만 저장
        if len(history) > 1000:
            history = history[:1000]
        
        # 저장
        save_history(history)
        
        return jsonify({
            'status': 'success',
            'recordId': record_id,
            'message': '영양소 분석 기록이 저장되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/get-history')
def get_history():
    """저장된 기록 조회"""
    try:
        # 쿼리 파라미터
        user_id = request.args.get('userId', 'guest')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        date_from = request.args.get('dateFrom')
        date_to = request.args.get('dateTo')
        meal_type = request.args.get('mealType')
        
        # 전체 기록 불러오기
        history = load_history()
        
        # 필터링
        filtered = []
        for record in history:
            # 사용자 필터
            if user_id != 'all' and record.get('userId') != user_id:
                continue
            
            # 날짜 필터
            if date_from and record.get('timestamp') < date_from:
                continue
            if date_to and record.get('timestamp') > date_to:
                continue
            
            # 식사 타입 필터
            if meal_type and record.get('mealType') != meal_type:
                continue
            
            filtered.append(record)
        
        # 페이지네이션
        total = len(filtered)
        paginated = filtered[offset:offset + limit]
        
        return jsonify({
            'status': 'success',
            'total': total,
            'limit': limit,
            'offset': offset,
            'records': paginated
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/get-statistics')
def get_statistics():
    """통계 정보 조회"""
    try:
        user_id = request.args.get('userId', 'guest')
        
        history = load_history()
        
        # 사용자별 필터링
        user_records = [r for r in history if r.get('userId') == user_id]
        
        if not user_records:
            return jsonify({
                'status': 'success',
                'statistics': {
                    'totalRecords': 0,
                    'averageCalories': 0,
                    'mealTypeDistribution': {},
                    'nutriScoreDistribution': {}
                }
            })
        
        # 통계 계산
        total_calories = sum(r.get('calories', 0) for r in user_records)
        avg_calories = round(total_calories / len(user_records))
        
        # 식사 타입 분포
        meal_types = {}
        for record in user_records:
            meal_type = record.get('mealType', 'unknown')
            meal_types[meal_type] = meal_types.get(meal_type, 0) + 1
        
        # 영양 점수 분포
        nutri_scores = {}
        for record in user_records:
            score = record.get('nutriScore', {}).get('category', 'unknown')
            nutri_scores[score] = nutri_scores.get(score, 0) + 1
        
        return jsonify({
            'status': 'success',
            'statistics': {
                'totalRecords': len(user_records),
                'averageCalories': avg_calories,
                'mealTypeDistribution': meal_types,
                'nutriScoreDistribution': nutri_scores,
                'recentRecords': user_records[:5]
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/delete-record/<record_id>', methods=['DELETE'])
def delete_record(record_id):
    """특정 기록 삭제"""
    try:
        history = load_history()
        
        # 해당 ID의 기록 찾기
        new_history = [r for r in history if r.get('id') != record_id]
        
        if len(new_history) == len(history):
            return jsonify({
                'status': 'error',
                'message': '해당 기록을 찾을 수 없습니다.'
            }), 404
        
        save_history(new_history)
        
        return jsonify({
            'status': 'success',
            'message': '기록이 삭제되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/')
def serve_dashboard():
    """대시보드 HTML 제공"""
    return send_from_directory('.', 'nutrition_dashboard.html')

@app.route('/health')
def health():
    """헬스 체크"""
    return jsonify({
        'status': 'healthy',
        'service': 'nutrition-history-server'
    })

if __name__ == '__main__':
    print("Starting Nutrition History Server on port 5004...")
    app.run(host='0.0.0.0', port=5004, debug=True)