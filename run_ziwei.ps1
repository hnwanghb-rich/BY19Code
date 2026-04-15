Write-Host "Starting ZiWei GUI Application..." -ForegroundColor Green
Write-Host ""

# 检查Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Cyan
} catch {
    Write-Host "Python not found or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python or add it to your PATH" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host ""
Write-Host "Running ZiWei GUI..." -ForegroundColor Cyan

# 运行程序
python ziwei_gui_simple.py

Write-Host ""
Write-Host "Program finished." -ForegroundColor Green
pause