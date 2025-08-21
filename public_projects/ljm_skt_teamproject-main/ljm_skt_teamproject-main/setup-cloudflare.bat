@echo off
echo ===============================================
echo YUM:AI Cloudflare Tunnel Setup
echo ===============================================
echo.

echo Step 1: Cloudflare Tunnel 설치 확인...
where cloudflared >nul 2>&1
if %errorlevel% neq 0 (
    echo Cloudflare Tunnel이 설치되어 있지 않습니다.
    echo.
    echo 다운로드 중...
    echo https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
    echo.
    echo 다운로드 후 C:\Program Files\Cloudflare 폴더에 저장하고 PATH에 추가하세요.
    echo.
    pause
    exit /b 1
) else (
    echo ✓ Cloudflare Tunnel이 설치되어 있습니다.
)

echo.
echo Step 2: Cloudflare 로그인...
echo 브라우저가 열리면 Cloudflare 계정으로 로그인하세요.
cloudflared tunnel login

echo.
echo Step 3: 터널 생성...
cloudflared tunnel create yumai-tunnel

echo.
echo Step 4: DNS 레코드 생성...
echo 다음 도메인을 설정합니다:
echo - yumai.example.com (메인 앱)
echo - api.yumai.example.com (API 프록시)
echo.
echo 실제 도메인으로 변경하려면 cloudflare-tunnel-config.yml을 수정하세요.
echo.

cloudflared tunnel route dns yumai-tunnel yumai.example.com
cloudflared tunnel route dns yumai-tunnel api.yumai.example.com

echo.
echo Step 5: 터널 실행...
echo.
cloudflared tunnel run --config cloudflare-tunnel-config.yml yumai-tunnel

pause