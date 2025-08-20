@echo off
echo YUM:AI Quick Tunnel 시작 (임시 도메인)
echo.
echo [주의] 이 방법은 임시 URL을 생성합니다.
echo Google OAuth는 작동하지 않지만, 다른 모든 기능은 테스트 가능합니다.
echo.

echo 웹 앱 터널 시작 중...
start cmd /k "cloudflared tunnel --url http://localhost:19001"

timeout /t 3

echo.
echo ========================================
echo 터널이 시작되었습니다!
echo 터미널에 표시되는 https://xxx.trycloudflare.com URL로 접속하세요.
echo.
echo Google 로그인이 필요하면:
echo 1. Cloudflare 대시보드에서 Zero Trust 활성화
echo 2. 또는 ngrok 사용 (고정 도메인 제공)
echo ========================================
echo.
pause