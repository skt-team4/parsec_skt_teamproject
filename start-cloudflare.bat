@echo off
echo YUM:AI Cloudflare Tunnel 시작...
echo.

REM Cloudflare 설치 확인
where cloudflared >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] cloudflared가 설치되지 않았습니다!
    echo.
    echo 설치 방법:
    echo 1. https://github.com/cloudflare/cloudflared/releases 에서 다운로드
    echo 2. PATH에 추가하거나 현재 폴더에 복사
    echo.
    pause
    exit /b 1
)

echo [1] 임시 터널 시작 (테스트용 - Google OAuth 불가)...
echo cloudflared tunnel --url http://localhost:19001
echo.
echo [2] 고정 터널 시작 (Google OAuth 가능 - 설정 필요)...
echo cloudflared tunnel run yumai-app
echo.

choice /C 12 /N /M "선택하세요 (1: 임시, 2: 고정): "

if %errorlevel%==1 (
    echo.
    echo 임시 터널 시작 중...
    echo 주의: Google OAuth는 작동하지 않습니다!
    echo.
    cloudflared tunnel --url http://localhost:19001
) else (
    echo.
    echo 고정 터널 시작 중...
    echo 설정 파일: cloudflare-config.yml
    echo.
    cloudflared tunnel run --config cloudflare-config.yml yumai-app
)

pause