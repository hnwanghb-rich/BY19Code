@echo off
echo Testing Python environment...
echo.

REM 检查Python
where python >nul 2>&1
if %errorlevel% equ 0 (
    echo Python found
    python --version
) else (
    echo Python not found
)

echo.
echo Checking py launcher...
where py >nul 2>&1
if %errorlevel% equ 0 (
    echo py launcher found
    py --version
) else (
    echo py launcher not found
)

echo.
echo Current directory:
cd

echo.
pause