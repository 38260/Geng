@echo off
rem ============================================================
rem  赶梗潮 · 停止服务
rem  停掉 start.bat 记录过的全部端口上运行的后端/前端进程
rem  注意：本文件必须用 GBK(ANSI) 保存，且不要调用 chcp
rem ============================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

if not exist "logs\ports.txt" (
  echo   没找到 logs\ports.txt，按默认端口 8010 / 5173 尝试停止。
  > "logs\ports.txt" echo 8010 5173
)

echo   正在停止 start.bat 启动过的全部服务...
powershell -NoProfile -Command "$ports=@(); Get-Content 'logs\ports.txt' -ErrorAction SilentlyContinue | ForEach-Object { $ports += ($_ -split '\s+') | Where-Object { $_ -match '^\d+$' } }; $found=0; foreach($p in ($ports | Select-Object -Unique)){ $c=Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue; if($c){ $c | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }; Write-Host ('     已停止端口 ' + $p); $found++ } else { Write-Host ('     端口 ' + $p + ' 没有服务在监听') } }; if($found -eq 0){ Write-Host '     没有需要停止的服务' }"
del "logs\ports.txt" >nul 2>nul

echo   完成。
endlocal
