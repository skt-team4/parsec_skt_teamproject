@echo off
echo Starting NabiYam Web App on port 19000...
echo.

REM 포트 19000이 사용중인지 확인
netstat -ano | findstr :19000 >nul
if %errorlevel%==0 (
    echo Warning: Port 19000 is already in use!
    echo Trying to kill the process using port 19000...
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :19000') do (
        taskkill /F /PID %%a >nul 2>&1
    )
    timeout /t 2 >nul
)

echo Starting Expo on port 19000...
npx expo start --web --port 19000 --clear