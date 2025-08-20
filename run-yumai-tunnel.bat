@echo off
echo YUM:AI Cloudflare Tunnel 실행
echo.

REM cloudflared.exe 확인
if not exist cloudflared.exe (
    echo [ERROR] cloudflared.exe를 찾을 수 없습니다!
    echo.
    echo 1. https://github.com/cloudflare/cloudflared/releases 에서 다운로드
    echo 2. cloudflared-windows-amd64.exe를 cloudflared.exe로 이름 변경
    echo 3. 이 폴더에 복사
    echo.
    pause
    exit /b 1
)

echo [1] Cloudflare 로그인...
cloudflared.exe tunnel login

echo.
echo [2] 터널 실행 중...
echo Tunnel ID: e37bf6f7-ca0f-4477-a323-f645cd092436
echo.

REM config.yml 생성
echo tunnel: e37bf6f7-ca0f-4477-a323-f645cd092436 > config.yml
echo credentials-file: %USERPROFILE%\.cloudflared\e37bf6f7-ca0f-4477-a323-f645cd092436.json >> config.yml
echo. >> config.yml
echo ingress: >> config.yml
echo   - hostname: yumai.sktfly0704.workers.dev >> config.yml
echo     service: http://localhost:19001 >> config.yml
echo   - hostname: yumai-api.sktfly0704.workers.dev >> config.yml
echo     service: http://localhost:8000 >> config.yml
echo   - service: http_status:404 >> config.yml

echo.
echo [3] 터널 시작...
cloudflared.exe tunnel run --config config.yml yumai

pause