#!/bin/bash

echo "Starting NabiYam Web App on port 19000..."
echo ""

# 포트 19000이 사용중인지 확인 (macOS/Linux)
if lsof -Pi :19000 -sTCP:LISTEN -t >/dev/null ; then
    echo "Warning: Port 19000 is already in use!"
    echo "Trying to kill the process using port 19000..."
    
    # macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        lsof -ti:19000 | xargs kill -9 2>/dev/null
    # Linux
    else
        fuser -k 19000/tcp 2>/dev/null
    fi
    
    sleep 2
fi

echo "Starting Expo on port 19000..."
npx expo start --web --port 19000 --clear