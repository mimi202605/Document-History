@echo off
echo ============================================
echo   DocHistory Windows Build Script
echo ============================================
echo.

REM Check Python environment
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Install dependencies
echo [1/4] Installing project dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

REM Install PyInstaller
echo [2/4] Installing PyInstaller...
pip install pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller
    pause
    exit /b 1
)

REM Clean old build files
echo [3/4] Cleaning old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build executable
echo [4/4] Building executable...
python -m PyInstaller DocHistory.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build Successful!
echo ============================================
echo.
echo Executable: dist\DocHistory.exe
echo.
echo Usage: Double-click dist\DocHistory.exe to run
echo.
pause
