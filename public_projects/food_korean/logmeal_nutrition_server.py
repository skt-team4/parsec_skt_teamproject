"""
LogMeal API 기반 실시간 영양소 분석 서버
이미지를 직접 LogMeal API로 전송하여 정확한 영양 정보를 반환
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import tempfile
import os

app = Flask(__name__)
CORS(app)

# LogMeal API 설정
LOGMEAL_API_TOKEN = '4c50bb4d8b94d9000863b373212be8a7959734f6'
LOGMEAL_HEADERS = {'Authorization': f'Bearer {LOGMEAL_API_TOKEN}'}

# LogMeal API 엔드포인트
LOGMEAL_DISH_DETECTION_URL = 'https://api.logmeal.com/v2/image/segmentation/complete'
LOGMEAL_NUTRITION_URL = 'https://api.logmeal.com/v2/recipe/nutritionalInfo'

@app.route('/analyze-nutrition', methods=['POST'])
def analyze_nutrition():
    """
    이미지를 받아서 LogMeal API로 직접 분석
    1. 음식 인식 (dish detection)
    2. 영양소 정보 획득 (nutritional info)
    """
    
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'}), 400
    
    try:
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            file.save(tmp_file.name)
            tmp_file_path = tmp_file.name
        
        # Step 1: LogMeal로 음식 인식
        print(f"Detecting dishes with LogMeal API...")
        with open(tmp_file_path, 'rb') as f:
            dish_response = requests.post(
                LOGMEAL_DISH_DETECTION_URL,
                files={'image': f},
                headers=LOGMEAL_HEADERS
            )
        
        if dish_response.status_code != 200:
            return jsonify({
                'status': 'error',
                'message': f'LogMeal dish detection failed: {dish_response.status_code}'
            }), 500
        
        dish_result = dish_response.json()
        
        # imageId 확인
        image_id = dish_result.get('imageId')
        if not image_id:
            return jsonify({
                'status': 'error',
                'message': 'No imageId returned from LogMeal'
            }), 500
        
        print(f"Got imageId: {image_id}")
        
        # Step 2: LogMeal로 영양 정보 획득
        print(f"Getting nutritional info from LogMeal...")
        nutrition_response = requests.post(
            LOGMEAL_NUTRITION_URL,
            json={'imageId': image_id},
            headers=LOGMEAL_HEADERS
        )
        
        if nutrition_response.status_code != 200:
            return jsonify({
                'status': 'error',
                'message': f'LogMeal nutrition API failed: {nutrition_response.status_code}'
            }), 500
        
        nutrition_result = nutrition_response.json()
        
        # 음식명 추출
        food_names = dish_result.get('foodType', [])
        if not food_names and 'foodFamily' in dish_result:
            food_names = dish_result.get('foodFamily', [])
        
        # 응답 포맷팅
        response = {
            'status': 'success',
            'imageId': image_id,
            'foodNames': food_names,
            'hasNutritionalInfo': nutrition_result.get('hasNutritionalInfo', False),
            'nutritional_info': nutrition_result.get('nutritional_info', {}),
            'nutritional_info_per_item': nutrition_result.get('nutritional_info_per_item', []),
            'serving_size': nutrition_result.get('serving_size', 0)
        }
        
        # 영양 점수가 있으면 추가
        if 'image_nutri_score' in nutrition_result:
            response['nutri_score'] = {
                'category': nutrition_result['image_nutri_score'].get('nutri_score_category', 'Unknown'),
                'score': nutrition_result['image_nutri_score'].get('nutri_score_standardized', 0)
            }
        
        # 음식별 상세 정보
        if response['nutritional_info_per_item']:
            items = []
            for item in response['nutritional_info_per_item']:
                item_info = {
                    'food_item_position': item.get('food_item_position', 0),
                    'id': item.get('id', 0),
                    'serving_size': item.get('serving_size', 0),
                    'hasNutritionalInfo': item.get('hasNutritionalInfo', False)
                }
                
                # 영양 정보가 있으면 추가
                if item.get('nutritional_info'):
                    item_info['nutritional_info'] = item['nutritional_info']
                
                # 영양 점수가 있으면 추가
                if item.get('nutri_score'):
                    item_info['nutri_score'] = item['nutri_score']
                    
                items.append(item_info)
            
            response['items'] = items
        
        # 임시 파일 삭제
        os.unlink(tmp_file_path)
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        # 임시 파일 삭제 시도
        if 'tmp_file_path' in locals():
            try:
                os.unlink(tmp_file_path)
            except:
                pass
        
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/nutrition/<food_name>')
def get_nutrition_by_name(food_name):
    """
    음식명으로 영양 정보 조회 (호환성을 위한 엔드포인트)
    실제로는 이미지 기반 분석을 권장
    """
    return jsonify({
        'status': 'info',
        'message': 'Please use /analyze-nutrition with image for accurate results',
        'foodName': food_name,
        'note': 'This endpoint requires image-based analysis for accurate nutrition data'
    })

@app.route('/health')
def health_check():
    """헬스 체크 엔드포인트"""
    # LogMeal API 상태 확인
    try:
        test_response = requests.get(
            'https://api.logmeal.com/v2/status',
            headers=LOGMEAL_HEADERS,
            timeout=5
        )
        logmeal_status = 'healthy' if test_response.status_code == 200 else 'unhealthy'
    except:
        logmeal_status = 'unknown'
    
    return jsonify({
        'status': 'healthy',
        'service': 'logmeal-nutrition-api',
        'logmeal_api_status': logmeal_status
    })

@app.route('/')
def index():
    """서비스 정보"""
    return jsonify({
        'service': 'LogMeal Nutrition Analysis API',
        'version': '2.0',
        'endpoints': {
            '/analyze-nutrition': 'POST - Analyze nutrition from image',
            '/nutrition/<food_name>': 'GET - Legacy endpoint (image required for accuracy)',
            '/health': 'GET - Health check'
        },
        'description': 'Real-time nutrition analysis using LogMeal API',
        'note': 'Provides accurate nutritional information based on actual food images'
    })

if __name__ == '__main__':
    print("Starting LogMeal Nutrition Server on port 5003...")
    print("This server provides real-time nutrition analysis using LogMeal API")
    app.run(host='0.0.0.0', port=5003, debug=True)