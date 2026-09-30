@echo off
rem ============================================================
rem  赶梗潮 · 重启服务（先停后起）
rem  用法：restart.bat            停掉再启动，启动后按任意键停止
rem        restart.bat --detach   停掉再后台启动，用 stop.bat 停止
rem  说明：本文件只做"停 + 起"的编排，停止逻辑在 stop.bat、启动逻辑在
rem        start.bat —— 不在这里再抄一份，否则改了一边漏一边。
rem  注意：本文件必须用 GBK(ANSI) 保存，UTF-8 会让 cmd 解析中文出错
rem ============================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title GengChao Restart

echo.
echo   ==========================================
echo    赶梗潮  重启服务
echo   ==========================================
echo.

rem ---------- 0. 先把当前端口记下来 ----------
rem stop.bat 结束时会删掉 logs\ports.txt，所以端口必须在停之前读出来。
rem 读不到就退回默认端口（与 start.bat 的默认值保持一致）。
set "PORTS=8010,5173"
if exist "logs\ports.txt" (
  for /f "usebackq tokens=1,2" %%a in ("logs\ports.txt") do set "PORTS=%%a,%%b"
)

rem ---------- 1. 停止 ----------
if not exist "%~dp0stop.bat" (
  echo   [X] 没找到 stop.bat，无法重启。
  goto :fail
)
call "%~dp0stop.bat"

rem ---------- 2. 等端口真正释放 ----------
rem stop.bat 是"发出终止信号"就返回，进程退出到端口从 LISTEN 消失有几秒延迟。
rem 不等的话，紧接着的 start.bat 会把这些端口当成被别的程序占用而自动让路，
rem 于是每重启一次端口就往后挪一格，重启几次之后自己都记不清在哪个端口上了。
set /a "TRIES=0"
:wait_release
powershell -NoProfile -Command "$busy=0; foreach($p in @(%PORTS%)){ if(Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue){ $busy++ } }; exit $busy" >nul 2>nul
if errorlevel 1 (
  set /a "TRIES+=1"
  if !TRIES! geq 20 (
    echo   [X] 等了 20 秒，端口 %PORTS% 仍被占用，已放弃重启。
    echo       可能是别的程序占着这些端口：先关掉它，或直接跑 start.bat（它会自动让路）。
    goto :fail
  )
  ping -n 2 127.0.0.1 >nul
  goto :wait_release
)
echo   端口已释放（%PORTS%）。
echo.

rem ---------- 3. 启动（参数原样转给 start.bat，如 --detach） ----------
if not exist "%~dp0start.bat" (
  echo   [X] 没找到 start.bat，无法重启。
  goto :fail
)
call "%~dp0start.bat" %*
set "RC=%errorlevel%"

endlocal & exit /b %RC%

:fail
echo.
echo   重启未完成，请根据上面的提示处理后重试。
endlocal
exit /b 1
