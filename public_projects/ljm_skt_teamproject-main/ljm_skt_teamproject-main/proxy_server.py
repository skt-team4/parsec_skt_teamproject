from flask import Flask, request, jsonify, Response, make_response
from flask_cors import CORS
import requests
import os
from werkzeug.datastructures import Headers

app = Flask(__name__)
# 완전한 CORS 설정 for Cloudflare Tunnel
CORS(app, 
     resources={r"/*": {"origins": "*"}},
     allow_headers=["Content-Type", "Authorization", "ngrok-skip-browser-warning", "Accept", "Origin", "X-Requested-With"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     supports_credentials=True,
     max_age=3600)

# 백엔드 서비스 매핑
BACKEND_SERVICES = {
    '5001': 'http://localhost:5001',  # 한국 음식 인식
    '5002': 'http://localhost:5002',  # 정적 영양 정보
    '5003': 'http://localhost:5003',  # LogMeal 영양 분석
    '5004': 'http://localhost:5004',  # 영양 기록
    '8000': 'http://localhost:8000',  # 메인 챗봇 API
    '8080': 'http://localhost:8080',  # 페르소나 챗봇 API
}

@app.before_request
def handle_preflight():
    """Handle preflight requests before they reach the route"""
    if request.method == "OPTIONS":
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept, Origin, X-Requested-With'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response

@app.after_request
def after_request(response):
    """Ensure CORS headers are always added"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept, Origin, X-Requested-With'
    return response

@app.route('/api/<port>/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def proxy(port, path):
    """모든 백엔드 서비스로의 프록시"""
    # Handle OPTIONS immediately
    if request.method == 'OPTIONS':
        return '', 204
        
    if port not in BACKEND_SERVICES:
        return jsonify({'error': f'Unknown service port: {port}'}), 404
    
    backend_url = f"{BACKEND_SERVICES[port]}/{path}"
    
    # 쿼리 파라미터 전달
    if request.query_string:
        backend_url += f"?{request.query_string.decode('utf-8')}"
    
    try:
        # 요청 헤더 복사 (Host 헤더 제외)
        headers = {key: value for key, value in request.headers if key != 'Host'}
        
        # 프록시 요청
        if request.method == 'GET':
            resp = requests.get(backend_url, headers=headers)
        elif request.method == 'POST':
            # multipart/form-data 처리
            if 'multipart/form-data' in request.content_type:
                files = {}
                for key in request.files:
                    file = request.files[key]
                    files[key] = (file.filename, file.stream, file.content_type)
                resp = requests.post(backend_url, files=files, data=request.form, headers=headers)
            else:
                resp = requests.post(backend_url, json=request.json, headers=headers)
        elif request.method == 'PUT':
            resp = requests.put(backend_url, json=request.json, headers=headers)
        elif request.method == 'DELETE':
            resp = requests.delete(backend_url, headers=headers)
        else:
            return jsonify({'error': f'Method {request.method} not supported'}), 405
        
        # 응답 반환 with complete CORS headers
        response = make_response(resp.content, resp.status_code)
        response.headers['Content-Type'] = resp.headers.get('Content-Type', 'application/json')
        # CORS headers will be added by after_request
        return response
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Service on port {port} is not available")
        return jsonify({'error': f'Service on port {port} is not available'}), 503
    except Exception as e:
        print(f"❌ Proxy error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """헬스 체크 엔드포인트"""
    services_status = {}
    for port, url in BACKEND_SERVICES.items():
        try:
            resp = requests.get(f"{url}/health", timeout=2)
            services_status[port] = 'online' if resp.status_code == 200 else 'error'
        except:
            services_status[port] = 'offline'
    
    return jsonify({
        'status': 'ok',
        'services': services_status
    })

@app.route('/map')
def serve_map():
    """T-Map HTML 파일 직접 제공"""
    map_file_path = os.path.join(os.path.dirname(__file__), 'assets', 'maps', 'tmap_folium_map.html')
    print(f"Looking for map file at: {map_file_path}")
    print(f"File exists: {os.path.exists(map_file_path)}")
    if os.path.exists(map_file_path):
        with open(map_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return Response(html_content, mimetype='text/html')
    else:
        return jsonify({'error': f'Map file not found at {map_file_path}'}), 404

@app.route('/')
def index():
    """프록시 서버 정보"""
    return jsonify({
        'service': 'YUM:AI Proxy Server',
        'purpose': 'Routes requests to backend services',
        'services': list(BACKEND_SERVICES.keys()),
        'health_check': '/health',
        'map': '/map'
    })

if __name__ == '__main__':
    print("Proxy Server Starting...")
    print("This server routes requests to all backend services")
    print("Server URL: http://localhost:3001")
    print("\nAvailable services:")
    for port, url in BACKEND_SERVICES.items():
        print(f"  - Port {port}: {url}")
    
    # 새로운 포트 3001 사용 (Expo 포트 충돌 회피)
    app.run(host='0.0.0.0', port=3001, debug=True)