#!/usr/bin/env python3
"""
T-Map 가맹점 지도 서버
포트 5005에서 실행되며 tmap_folium_map.html 파일을 제공합니다.
"""

import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

class MapRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '':
            # 루트 경로 요청 시 지도 HTML 파일로 리다이렉트
            self.path = '/assets/maps/tmap_folium_map.html'
        
        # CORS 헤더 추가
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        
        return super().do_GET()

def run_server(port=5005):
    """지도 서버 실행"""
    try:
        # 현재 디렉토리를 프로젝트 루트로 변경
        project_root = Path(__file__).parent
        os.chdir(project_root)
        
        server_address = ('', port)
        httpd = HTTPServer(server_address, MapRequestHandler)
        
        print(f"T-Map Store Map Server Starting...")
        print(f"Available at: http://localhost:{port}")
        print(f"Serving from: {project_root}")
        print("Press Ctrl+C to stop\n")
        
        httpd.serve_forever()
        
    except KeyboardInterrupt:
        print("\nServer shutting down...")
        httpd.shutdown()
    except Exception as e:
        print(f"Server start failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    # 포트 번호를 인자로 받을 수 있음 (기본값: 5005)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5005
    run_server(port)