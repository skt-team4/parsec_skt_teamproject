@echo off
echo YUM:AI ngrok 터널 시작
echo.

REM ngrok.exe 확인
if not exist ngrok.exe (
    echo [ERROR] ngrok.exe를 찾을 수 없습니다!
    echo.
    echo 1. https://ngrok.com/download 에서 다운로드
    echo 2. 이 폴더에 ngrok.exe 복사
    echo.
    pause
    exit /b 1
)

echo ===================================
echo ngrok 터널 옵션
echo ===================================
echo.
echo 1. 임시 URL (테스트용, Google OAuth 불가)
echo 2. 고정 도메인 (Google OAuth 가능)
echo.
choice /C 12 /N /M "선택하세요 (1 또는 2): "

if %errorlevel%==1 (
    echo.
    echo 임시 터널 시작 중...
    ngrok http 19001
) else (
    echo.
    set /p DOMAIN="고정 도메인 입력 (예: yumai-app.ngrok-free.app): "
    echo.
    echo 고정 도메인으로 터널 시작 중...
    ngrok http 19001 --domain=%DOMAIN%
)

pause