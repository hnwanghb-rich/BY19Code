@echo off
echo 测试紫微斗数程序...
echo.

REM 检查Python是否可用
where python >nul 2>nul
if %errorlevel% equ 0 (
    echo 找到Python，开始测试...
    python test_ziwei.py
    goto :end
)

where python3 >nul 2>nul
if %errorlevel% equ 0 (
    echo 找到Python3，开始测试...
    python3 test_ziwei.py
    goto :end
)

echo 错误：未找到Python或Python3
echo 请确保Python已安装并添加到PATH环境变量

:end
pause