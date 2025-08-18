#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
나비얌 챗봇 API 서버 시작 스크립트
"""

import sys
import os
import io

# UTF-8 인코딩 설정
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 서버 시작
if __name__ == "__main__":
    from src.api.server import app
    import uvicorn
    
    print("🚀 나비얌 챗봇 API 서버 시작...")
    print("📍 주소: http://localhost:8000")
    print("📚 API 문서: http://localhost:8000/docs")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )