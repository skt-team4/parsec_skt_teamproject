from flask import Flask, send_file
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)  # CORS 활성화

@app.route('/')
def serve_map():
    """T-Map 가맹점 지도 HTML 파일 제공"""
    map_path = os.path.join('assets', 'tmap_folium_map.html')
    if os.path.exists(map_path):
        return send_file(map_path)
    else:
        return "Map file not found", 404

@app.route('/health')
def health():
    return "Map server is running", 200

if __name__ == '__main__':
    print("T-Map store map server starting...")
    print("Map available at http://localhost:5005/")
    app.run(host='0.0.0.0', port=5005, debug=False)