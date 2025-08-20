@echo off
echo ===================================
echo YUM:AI Google OAuth 터널 시작
echo ===================================
echo.
echo 도메인: maximum-shiner-implicitly.ngrok-free.app
echo Google OAuth: 활성화됨
echo.

echo [실행 중...]
ngrok.exe http 19001 --domain=maximum-shiner-implicitly.ngrok-free.app

pause