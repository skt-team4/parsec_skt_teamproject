@echo off
echo ========================================
echo ngrok 터널 시작 스크립트
echo ========================================
echo.

REM ngrok 경로 설정
set NGROK_PATH=ngrok.exe

REM ngrok 실행 확인
if not exist "%NGROK_PATH%" (
    echo ngrok.exe를 찾을 수 없습니다!
    echo ngrok을 다운로드하여 프로젝트 루트에 놓아주세요.
    echo https://ngrok.com/download
    pause
    exit /b 1
)

echo 다음 포트들에 대한 ngrok 터널을 시작합니다:
echo - 19000: Expo 웹 앱
echo - 8000: 챗봇 API
echo - 5001: 음식 인식 API
echo - 5003: 영양 분석 API
echo - 5004: 영양 기록 API
echo.

REM ngrok 설정 파일 생성
echo authtoken: 31XWHxsthkuEo8IGG3ivsmx38ZC_7usVJz6N4ECQVPL153XBJ > ngrok.yml
echo version: "2" >> ngrok.yml
echo tunnels: >> ngrok.yml
echo   expo: >> ngrok.yml
echo     addr: 19000 >> ngrok.yml
echo     proto: http >> ngrok.yml
echo     hostname: maximum-shiner-implicitly.ngrok-free.app >> ngrok.yml
echo   chatbot: >> ngrok.yml
echo     addr: 8000 >> ngrok.yml
echo     proto: http >> ngrok.yml
echo   food-recognition: >> ngrok.yml
echo     addr: 5001 >> ngrok.yml
echo     proto: http >> ngrok.yml
echo   nutrition: >> ngrok.yml
echo     addr: 5003 >> ngrok.yml
echo     proto: http >> ngrok.yml
echo   nutrition-history: >> ngrok.yml
echo     addr: 5004 >> ngrok.yml
echo     proto: http >> ngrok.yml

echo.
echo ngrok 터널 시작중...
echo.

REM ngrok 시작 (모든 터널)
start "ngrok" %NGROK_PATH% start --all --config ngrok.yml

echo.
echo ngrok이 시작되었습니다!
echo.
echo 접속 URL:
echo - Expo 앱: https://maximum-shiner-implicitly.ngrok-free.app
echo - ngrok 대시보드: http://localhost:4040
echo.
echo 모든 API 서비스는 프록시를 통해 접근 가능합니다:
echo - /api/8000/* : 챗봇 API
echo - /api/5001/* : 음식 인식 API
echo - /api/5003/* : 영양 분석 API
echo - /api/5004/* : 영양 기록 API
echo.
pause