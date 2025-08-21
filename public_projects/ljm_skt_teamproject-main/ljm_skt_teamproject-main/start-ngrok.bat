@echo off
echo Starting YUM:AI with ngrok...
echo.

REM 프록시 서버 시작
echo Starting proxy server...
start cmd /k "cd /d %~dp0 && python proxy_server.py"
timeout /t 3

REM 지도 서버는 이미 실행 중

REM ngrok 시작
echo.
echo Starting ngrok tunnels...
echo.
echo IMPORTANT: 
echo 1. ngrok.yml 파일에서 YOUR_NGROK_AUTH_TOKEN을 실제 토큰으로 교체하세요
echo 2. .env 파일에서 다음 설정을 추가하세요:
echo    EXPO_PUBLIC_USE_REMOTE_API=true
echo    EXPO_PUBLIC_PROXY_URL=https://yumai-api.ngrok-free.app
echo.
echo ngrok를 시작하려면:
echo ngrok start --all --config ngrok.yml
echo.
pause