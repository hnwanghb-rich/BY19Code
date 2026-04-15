@echo off

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Python环境，请先安装Python
    pause
    exit /b 1
)

REM 安装依赖包
echo 正在安装所需依赖包...
pip install -r requirements.txt >nul 2>&1
if %errorlevel% neq 0 (
    echo 依赖包安装失败，请手动运行: pip install -r requirements.txt
    pause
    exit /b 1
)

REM 启动紫微斗数排盘系统
echo 正在启动紫微斗数排盘系统...
python ziwei_gui.py

REM 程序退出后暂停，显示信息
pause