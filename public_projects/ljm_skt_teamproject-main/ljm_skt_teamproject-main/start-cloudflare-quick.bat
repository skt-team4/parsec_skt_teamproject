@echo off
echo Starting YUM:AI with Cloudflare Tunnel (Quick Setup)...
echo.
echo This will create temporary tunnels without authentication.
echo.

REM Expo 앱 터널
echo Starting tunnel for Expo app (port 19000)...
start cmd /k "C:\lsj\skt_team\lsj_skt_teamproject_2\cloudflared.exe tunnel --url http://localhost:19000"

timeout /t 3

REM 프록시 서버 터널  
echo Starting tunnel for API proxy (port 19001)...
start cmd /k "C:\lsj\skt_team\lsj_skt_teamproject_2\cloudflared.exe tunnel --url http://localhost:19001"

echo.
echo ================================================
echo Tunnels are starting...
echo.
echo Check the terminal windows for your public URLs:
echo - App URL: Look for the URL in the first window
echo - API URL: Look for the URL in the second window
echo.
echo Update .env file with these URLs
echo ================================================
echo.
pause