@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1

echo.
echo ╔═══════════════════════════════════════════╗
echo ║             Graffito 启动脚本           ║
echo ╚═══════════════════════════════════════════╝
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.9+
    pause
    exit /b 1
)

REM Create venv and install dependencies (first time only)
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [INFO] Activating virtual environment...
    call venv\Scripts\activate.bat
    echo [INFO] Installing dependencies...
    python -m pip install --upgrade pip >nul 2>&1
    pip install -r requirements.txt --extra-index-url https://aioqzone.github.io/aioqzone-index/simple >nul 2>&1
    playwright install chromium >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
) else (
    echo [INFO] Activating virtual environment...
    call venv\Scripts\activate.bat
    echo [INFO] Virtual environment exists, skipping dependency installation
)

REM Check config file
if not exist "config\config.yaml" (
    echo [ERROR] Config file not found
    echo [INFO] Please create and edit config\config.yaml then restart
    pause
    exit /b 1
)

REM Create necessary directories
if not exist "data" mkdir data
if not exist "data\cache" mkdir data\cache
if not exist "data\logs" mkdir data\logs
if not exist "data\cookies" mkdir data\cookies

REM Initialize database (only if not exists or forced)
set "FORCE_DB_INIT="
if /I "%1"=="--init-db" set "FORCE_DB_INIT=1"
if /I "%1"=="-i" set "FORCE_DB_INIT=1"

if defined FORCE_DB_INIT (
    echo [INFO] Force initializing database...
    python cli.py db-init
) else (
    if not exist "data\graffito.db" (
        echo [INFO] Initializing database...
        python cli.py db-init
    ) else (
        echo [INFO] Database exists, skipping initialization
    )
)

REM Start main program
echo [INFO] Starting Graffito...
set DRIVER=~fastapi
python main.py

pause