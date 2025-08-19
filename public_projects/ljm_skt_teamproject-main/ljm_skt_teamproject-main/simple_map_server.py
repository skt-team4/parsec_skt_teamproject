#!/usr/bin/env python3
"""
Simple T-Map Store Map Server
Serves the tmap_folium_map.html file on port 5005
"""

import os
import sys
from pathlib import Path

def run_server(port=5005):
    """Start a simple HTTP server to serve the map HTML file"""
    import http.server
    import socketserver
    
    # Define the map file path
    current_dir = Path(__file__).parent
    map_file = current_dir / "assets" / "maps" / "tmap_folium_map.html"
    
    # Check if map file exists
    if not map_file.exists():
        print(f"Error: Map file not found at {map_file}")
        sys.exit(1)
    
    print(f"Map file found at: {map_file}")
    
    class MapHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/' or self.path == '':
                # Serve the map HTML file directly
                try:
                    with open(map_file, 'rb') as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return
                except Exception as e:
                    print(f"Error serving map file: {e}")
                    self.send_error(404, "Map file not found")
                    return
            else:
                # For other requests, use default handler
                super().do_GET()
    
    # Change to the project directory
    os.chdir(current_dir)
    
    # Start the server
    with socketserver.TCPServer(("", port), MapHandler) as httpd:
        print(f"T-Map Store Map Server running at http://localhost:{port}")
        print(f"Serving map from: {map_file}")
        print("Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped")

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5005
    run_server(port)