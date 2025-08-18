@echo off
echo ========================================
echo NabiYam Chatbot v0 - Virtual Environment Setup
echo ========================================
echo.

REM Python 버전 확인
python --version
echo.

REM 가상환경 생성
echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)

REM 가상환경 활성화
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM pip 업그레이드
echo Upgrading pip...
python -m pip install --upgrade pip

REM 필수 패키지 설치
echo Installing required packages...
echo.

REM PyTorch (CPU 버전으로 설치 - GPU 필요시 수정)
echo Installing PyTorch (CPU version)...
pip install torch torchvision torchaudio

REM 기본 패키지들
echo Installing core packages...
pip install transformers accelerate sentence-transformers
pip install fastapi uvicorn pydantic
pip install python-dotenv loguru tqdm

REM FAISS (CPU 버전)
echo Installing FAISS...
pip install faiss-cpu

REM 데이터 처리
echo Installing data processing packages...
pip install numpy pandas openpyxl xlsxwriter scikit-learn

REM NLP 관련
echo Installing NLP packages...
pip install sentencepiece tokenizers

REM 추가 패키지
echo Installing additional packages...
pip install datasets peft requests httpx

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo To activate the virtual environment, run:
echo   venv\Scripts\activate
echo.
echo To deactivate, run:
echo   deactivate
echo.
pause