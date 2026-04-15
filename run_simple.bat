@echo off
echo Starting simplified ZiWei GUI...
echo.

REM 检查Python
python --version
if %errorlevel% neq 0 (
    echo Python not found or not in PATH
    pause
    exit /b 1
)

echo.
echo Running simplified ZiWei GUI...
python ziwei_gui_simple.py

echo.
pause