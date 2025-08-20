@echo off
echo ===================================
echo ngrok 터널 테스트
echo ===================================
echo.

echo [1] 버전 확인...
ngrok.exe --version
echo.

echo [2] 임시 터널 테스트 (도메인 없이)...
echo 포트 19001로 임시 터널을 시작합니다.
echo Ctrl+C로 중지할 수 있습니다.
echo.
ngrok.exe http 19001

pause