@echo off
echo YUM:AI Cloudflare Tunnel (yumai) 시작
echo.

REM cloudflared.exe가 현재 폴더에 있는지 확인
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

echo [Step 1] 기존 cloudflared 프로세스 종료...
taskkill /F /IM cloudflared.exe 2>nul

echo.
echo [Step 2] Cloudflare 대시보드에서 토큰 복사
echo.
echo 1. https://one.dash.cloudflare.com 로그인
echo 2. Zero Trust → Networks → Tunnels
echo 3. 'yumai' 터널 클릭 → Configure 탭
echo 4. Install and run a connector 섹션
echo 5. Windows 선택 후 표시되는 명령어에서 토큰 복사
echo.
echo 토큰 예시: eyJhIjoiYTk3ZD...매우긴문자열...
echo.
set /p TOKEN="토큰을 붙여넣고 Enter: "

if "%TOKEN%"=="" (
    echo 토큰이 입력되지 않았습니다!
    pause
    exit /b 1
)

echo.
echo [Step 3] 터널 서비스 설치...
cloudflared.exe service install %TOKEN%

echo.
echo [Step 4] Public Hostname 설정 필요
echo.
echo Cloudflare 대시보드에서:
echo 1. yumai 터널 → Public Hostnames 탭
echo 2. Add a public hostname 클릭
echo 3. Subdomain: yumai
echo 4. Domain: 선택 (또는 생성)
echo 5. Service: HTTP, URL: localhost:19001
echo 6. Save
echo.
echo 설정 완료 후 https://yumai.[domain] 으로 접속
echo.
pause