@echo off
echo Starting Nutrition Analysis Services...
echo ======================================

REM Start Korean Food Recognition API (port 5001)
echo Starting Korean Food Recognition API on port 5001...
start cmd /k "cd /d %~dp0 && python app_korean.py"

REM Start LogMeal Nutrition Integration Server (port 5003)
echo Starting LogMeal Nutrition Server on port 5003...
start cmd /k "cd /d %~dp0 && python logmeal_nutrition_server.py"

REM Start Nutrition History Server (port 5004)
echo Starting Nutrition History Server on port 5004...
start cmd /k "cd /d %~dp0 && python nutrition_history_server.py"

echo.
echo All services are starting...
echo ======================================
echo Services:
echo - Korean Food Recognition API: http://localhost:5001
echo - LogMeal Nutrition Analysis: http://localhost:5003
echo - Nutrition History Dashboard: http://localhost:5004
echo ======================================
echo.
echo Press any key to open the dashboard in your browser...
pause >nul

REM Open dashboard in browser
start http://localhost:5004

echo Dashboard opened in browser!
echo Keep this window open to maintain the services.
pause