@echo off
chcp 65001 >nul
echo ============================================
echo   DocHistory Windows 打包脚本
echo ============================================
echo.

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.10+
    pause
    exit /b 1
)

REM 安装依赖
echo [1/4] 安装项目依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

REM 安装PyInstaller
echo [2/4] 安装PyInstaller打包工具...
pip install pyinstaller
if errorlevel 1 (
    echo [错误] PyInstaller安装失败
    pause
    exit /b 1
)

REM 清理旧的构建文件
echo [3/4] 清理旧的构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 执行打包
echo [4/4] 开始打包生成exe文件...
pyinstaller DocHistory.spec --clean --noconfirm
if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

echo.
echo ============================================
echo   打包成功！
echo ============================================
echo.
echo 可执行文件位于: dist\DocHistory.exe
echo.
echo 使用方法: 双击 dist\DocHistory.exe 即可运行
echo.
pause
