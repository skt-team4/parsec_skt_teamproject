@echo off
REM 가상환경 활성화 후 chatbot 실행

if not exist venv (
    echo [ERROR] Virtual environment not found!
    echo Please run setup_venv.bat first.
    pause
    exit /b 1
)

REM 가상환경 활성화
call venv\Scripts\activate.bat

REM PYTHONPATH 설정
set PYTHONPATH=%cd%

echo ========================================
echo NabiYam Chatbot v0
echo ========================================
echo.
echo Select mode:
echo 1. Chat Mode (Interactive)
echo 2. API Server
echo 3. Test Basic Functions
echo 4. Exit
echo.

set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" (
    echo Starting Chat Mode...
    python main.py --mode chat
) else if "%choice%"=="2" (
    echo Starting API Server...
    python src/api/server.py
) else if "%choice%"=="3" (
    echo Running Basic Tests...
    python test_basic.py
) else if "%choice%"=="4" (
    echo Exiting...
    exit /b 0
) else (
    echo Invalid choice!
)

pause
deactivate