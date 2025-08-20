@echo off
echo YUM:AI 외부 접속 터널 시작...
echo.

echo [1] 웹 앱 터널 시작 (포트 19001)...
start cmd /k "lt --port 19001 --print-requests"

timeout /t 2

echo [2] 챗봇 API 터널 시작 (포트 8000)...
start cmd /k "lt --port 8000 --print-requests"

timeout /t 2

echo [3] 음식 인식 API 터널 시작 (포트 5001)...
start cmd /k "lt --port 5001 --print-requests"

timeout /t 2

echo [4] 영양 분석 API 터널 시작 (포트 5003)...
start cmd /k "lt --port 5003 --print-requests"

echo.
echo ===================================
echo 터널이 시작되었습니다!
echo 각 창에서 표시되는 URL을 확인하세요.
echo ===================================
echo.
echo 팁: 각 URL을 메모해두고 다음과 같이 사용하세요:
echo - 웹 앱: https://xxxxx.loca.lt (19001)
echo - 챗봇: https://yyyyy.loca.lt (8000) 
echo - 음식: https://zzzzz.loca.lt (5001)
echo - 영양: https://wwwww.loca.lt (5003)
echo.
pause