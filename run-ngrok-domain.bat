@echo off
echo ===================================
echo YUM:AI ngrok 터널 실행
echo ===================================
echo.
echo 도메인: maximum-shiner-implicitly.ngrok-free.app
echo 포트: 19001
echo.

echo [실행 중...]
ngrok.exe http 19001 --domain=maximum-shiner-implicitly.ngrok-free.app

pause