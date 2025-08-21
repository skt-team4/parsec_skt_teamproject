@echo off
echo ========================================
echo Cloudflare Tunnel 시작 스크립트
echo ========================================
echo.

REM cloudflared 경로 설정
set CLOUDFLARED_PATH=cloudflared.exe

REM cloudflared 실행 확인
if not exist "%CLOUDFLARED_PATH%" (
    echo cloudflared.exe를 찾을 수 없습니다!
    echo cloudflared를 다운로드하여 프로젝트 루트에 놓아주세요.
    echo https://github.com/cloudflare/cloudflared/releases
    pause
    exit /b 1
)

echo Cloudflare Tunnel을 시작합니다...
echo.
echo 접속 URL:
echo - 메인 앱: https://yumai.lsjproject.com
echo - API: https://yumai-api.lsjproject.com
echo.

REM Cloudflare Tunnel 시작
%CLOUDFLARED_PATH% tunnel --config cloudflare-config.yml run

pause