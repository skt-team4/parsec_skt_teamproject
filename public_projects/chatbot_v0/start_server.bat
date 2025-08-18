@echo off
cd /d "%~dp0"
set PYTHONPATH=%cd%
echo Starting NabiYam API Server...
python src/api/server.py
pause