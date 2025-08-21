@echo off
echo Starting Cloudflare tunnel for proxy server...
echo.

cd C:\lsj\skt_team\lsj_skt_teamproject_2
cloudflared.exe tunnel --url http://localhost:19001

pause