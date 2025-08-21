from flask import Flask, send_file
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# HTML 파일 경로
MAP_FILE_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'maps', 'tmap_folium_map.html')

@app.route('/')
def serve_map():
    """지도 HTML 파일 서빙"""
    if os.path.exists(MAP_FILE_PATH):
        return send_file(MAP_FILE_PATH)
    else:
        return f"<h1>지도 파일을 찾을 수 없습니다</h1><p>경로: {MAP_FILE_PATH}</p>", 404

@app.route('/health')
def health_check():
    """헬스 체크"""
    return {"status": "ok", "map_exists": os.path.exists(MAP_FILE_PATH)}

if __name__ == '__main__':
    print("Map server starting...")
    print(f"Map file path: {MAP_FILE_PATH}")
    print(f"File exists: {os.path.exists(MAP_FILE_PATH)}")
    print("Server URL: http://localhost:5007")
    
    app.run(host='0.0.0.0', port=5007, debug=True)