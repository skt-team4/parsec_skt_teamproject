@echo off
echo YUM:AI 전체 서비스 ngrok 터널 시작
echo.

echo [1] 웹 앱 (포트 19001)
start cmd /k "ngrok http 19001 --domain=yumai-app.ngrok-free.app"

timeout /t 3

echo [2] 챗봇 API (포트 8000)
start cmd /k "ngrok http 8000 --domain=yumai-api.ngrok-free.app"

echo.
echo ===================================
echo ngrok 터널이 시작되었습니다!
echo.
echo 웹 앱: https://yumai-app.ngrok-free.app
echo API: https://yumai-api.ngrok-free.app
echo ===================================
echo.
pause