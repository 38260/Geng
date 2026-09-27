@echo off
rem ============================================================
rem  赶梗潮 · 一键启动
rem  用法：双击本文件（启动后按任意键即停止全部服务）
rem        start.bat --detach   启动后保持后台运行，用 stop.bat 停止
rem  注意：本文件必须用 GBK(ANSI) 保存，UTF-8 会让 cmd 解析中文出错
rem ============================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title GengChao Launcher

set "LOG_DIR=%~dp0logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "BE_DEF=8010"
set "FE_DEF=5173"

echo.
echo   ==========================================
echo    赶梗潮  一键启动    今天，赶什么梗？
echo   ==========================================
echo.

rem ---------- 1. 环境检查 ----------
where python >nul 2>nul
if errorlevel 1 (
  echo   [X] 没找到 Python。请安装 Python 3.10+ 并勾选 Add to PATH。
  goto :fail
)
where node >nul 2>nul
if errorlevel 1 (
  echo   [X] 没找到 Node.js。请安装 Node 18+ 后重试。
  goto :fail
)

rem ---------- 2. 依赖（缺了才装） ----------
python -c "import fastapi,uvicorn,sqlalchemy,pandas,numpy,httpx,pydantic_settings" >nul 2>nul
if errorlevel 1 (
  echo   [1/4] 安装后端依赖，首次运行可能要几分钟...
  python -m pip install -r backend\requirements.txt
  if errorlevel 1 (
    echo   [X] 后端依赖安装失败，请检查网络或代理。
    goto :fail
  )
) else (
  echo   [1/4] 后端依赖已就绪
)

if exist "frontend\node_modules\vite" (
  echo   [2/4] 前端依赖已就绪
) else (
  echo   [2/4] 安装前端依赖，首次运行可能要几分钟...
  pushd frontend
  call npm install --no-audit --no-fund
  set "NPM_RC=!errorlevel!"
  popd
  if not "!NPM_RC!"=="0" (
    echo   [X] 前端依赖安装失败，请检查网络或 npm registry。
    goto :fail
  )
)

rem ---------- 3. 一次问清两个空闲端口（默认端口被占时自动让路） ----------
echo   [3/4] 检测可用端口...
set "PORTS="
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$b=%BE_DEF%; while(Get-NetTCPConnection -LocalPort $b -State Listen -ErrorAction SilentlyContinue){$b++}; $f=%FE_DEF%; while(Get-NetTCPConnection -LocalPort $f -State Listen -ErrorAction SilentlyContinue){$f++}; Write-Output ($b.ToString()+' '+$f.ToString())"`) do set "PORTS=%%i"
for /f "tokens=1,2" %%a in ("%PORTS%") do (
  set "BACKEND_PORT=%%a"
  set "FRONTEND_PORT=%%b"
)
if not defined BACKEND_PORT set "BACKEND_PORT=%BE_DEF%"
if not defined FRONTEND_PORT set "FRONTEND_PORT=%FE_DEF%"

if not "!BACKEND_PORT!"=="%BE_DEF%" echo        默认后端端口被占用，改用 !BACKEND_PORT!
if not "!FRONTEND_PORT!"=="%FE_DEF%" echo        默认前端端口被占用，改用 !FRONTEND_PORT!

>> "%LOG_DIR%\ports.txt" echo !BACKEND_PORT! !FRONTEND_PORT!

rem ---------- 4. 起服务 ----------
echo   [4/4] 启动后端与前端...
rem 用独立最小化窗口启动：子进程不继承本窗口的输出管道，
rem 否则本脚本会一直等不到管道关闭，看起来像卡死。
start "GengChao-Backend-!BACKEND_PORT!" /MIN "%~dp0scripts\run-backend.bat"
call :wait_http "http://127.0.0.1:!BACKEND_PORT!/api/health" 60
if errorlevel 1 (
  echo   [X] 后端 60 秒内没起来。点开任务栏 GengChao-Backend 窗口看报错；
  echo       常见原因是数据库文件损坏，删掉 backend\data\gengv1.db* 后重试。
  goto :fail
)

start "GengChao-Frontend-!FRONTEND_PORT!" /MIN "%~dp0scripts\run-frontend.bat"
call :wait_http "http://127.0.0.1:!FRONTEND_PORT!/" 45
if errorlevel 1 (
  echo   [X] 前端 45 秒内没起来。点开任务栏 GengChao-Frontend 窗口看报错。
  goto :fail
)

rem ---------- 就绪 ----------
echo.
echo   ==========================================
echo    启动完成
echo.
echo      前端页面   http://localhost:!FRONTEND_PORT!
echo      后端接口   http://127.0.0.1:!BACKEND_PORT!/docs
echo      实时日志   任务栏 GengChao-Backend / GengChao-Frontend 两个窗口
echo.
powershell -NoProfile -Command "$m=Invoke-RestMethod 'http://127.0.0.1:!BACKEND_PORT!/api/meta'; '      数据源：' + $m.data_source + '   正式梗库：' + $m.certified_count + ' 个   更新时间：' + $m.data_updated_at"
echo   ==========================================
echo.

if /I "%~1"=="--detach" (
  echo   后台运行模式：服务保持运行，用 stop.bat 停止。
  exit /b 0
)

echo   关闭服务：在本窗口按任意键
pause >nul
call :stop_all
rem 统一走 stop.bat，避免两处逻辑各写一份、改一处漏一处
call "%~dp0stop.bat"
exit /b 0

:fail
)
where node >nul 2>nul
if errorlevel 1 (
  echo   [X] 没找到 Node.js。请安装 Node 18+ 后重试。
  goto :fail
)

rem ---------- 2. 依赖（缺了才装） ----------
python -c "import fastapi,uvicorn,sqlalchemy,pandas,numpy,httpx,pydantic_settings" >nul 2>nul
if errorlevel 1 (
  echo   [1/4] 安装后端依赖，首次运行可能要几分钟...
  python -m pip install -r backend\requirements.txt
  if errorlevel 1 (
    echo   [X] 后端依赖安装失败，请检查网络或代理。
    goto :fail
  )
) else (
  echo   [1/4] 后端依赖已就绪
)

if exist "frontend\node_modules\vite" (
  echo   [2/4] 前端依赖已就绪
) else (
  echo   [2/4] 安装前端依赖，首次运行可能要几分钟...
  pushd frontend
  call npm install --no-audit --no-fund
  set "NPM_RC=!errorlevel!"
  popd
  if not "!NPM_RC!"=="0" (
    echo   [X] 前端依赖安装失败，请检查网络或 npm registry。
    goto :fail
  )
)

rem ---------- 3. 一次问清两个空闲端口（默认端口被占时自动让路） ----------
echo   [3/4] 检测可用端口...
set "PORTS="
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$b=%BE_DEF%; while(Get-NetTCPConnection -LocalPort $b -State Listen -ErrorAction SilentlyContinue){$b++}; $f=%FE_DEF%; while(Get-NetTCPConnection -LocalPort $f -State Listen -ErrorAction SilentlyContinue){$f++}; Write-Output ($b.ToString()+' '+$f.ToString())"`) do set "PORTS=%%i"
for /f "tokens=1,2" %%a in ("%PORTS%") do (
  set "BACKEND_PORT=%%a"
  set "FRONTEND_PORT=%%b"
)
if not defined BACKEND_PORT set "BACKEND_PORT=%BE_DEF%"
if not defined FRONTEND_PORT set "FRONTEND_PORT=%FE_DEF%"

if not "!BACKEND_PORT!"=="%BE_DEF%" echo        默认后端端口被占用，改用 !BACKEND_PORT!
if not "!FRONTEND_PORT!"=="%FE_DEF%" echo        默认前端端口被占用，改用 !FRONTEND_PORT!

>> "%LOG_DIR%\ports.txt" echo !BACKEND_PORT! !FRONTEND_PORT!

rem ---------- 4. 起服务 ----------
echo   [4/4] 启动后端与前端...
rem 用独立最小化窗口启动：子进程不继承本窗口的输出管道，
rem 否则本脚本会一直等不到管道关闭，看起来像卡死。
start "GengChao-Backend-!BACKEND_PORT!" /MIN "%~dp0scripts\run-backend.bat"
call :wait_http "http://127.0.0.1:!BACKEND_PORT!/api/health" 60
if errorlevel 1 (
  echo   [X] 后端 60 秒内没起来。点开任务栏 GengChao-Backend 窗口看报错；
  echo       常见原因是数据库文件损坏，删掉 backend\data\gengv1.db* 后重试。
  goto :fail
)

start "GengChao-Frontend-!FRONTEND_PORT!" /MIN "%~dp0scripts\run-frontend.bat"
call :wait_http "http://127.0.0.1:!FRONTEND_PORT!/" 45
if errorlevel 1 (
  echo   [X] 前端 45 秒内没起来。点开任务栏 GengChao-Frontend 窗口看报错。
  goto :fail
)

rem ---------- 就绪 ----------
echo.
echo   ==========================================
echo    启动完成
echo.
echo      前端页面   http://localhost:!FRONTEND_PORT!
echo      后端接口   http://127.0.0.1:!BACKEND_PORT!/docs
echo      实时日志   任务栏 GengChao-Backend / GengChao-Frontend 两个窗口
echo.
powershell -NoProfile -Command "$m=Invoke-RestMethod 'http://127.0.0.1:!BACKEND_PORT!/api/meta'; '      数据源：' + $m.data_source + '   正式梗库：' + $m.certified_count + ' 个   更新时间：' + $m.data_updated_at"
echo   ==========================================
echo.

if /I "%~1"=="--detach" (
  echo   后台运行模式：服务保持运行，用 stop.bat 停止。
  exit /b 0
)

echo   关闭服务：在本窗口按任意键
pause >nul
call :stop_all
exit /b 0

rem ============================================================
:wait_http
rem %~1 = URL   %~2 = 最多等多少秒
setlocal
set "TARGET=%~1"
set /a "LEFT=%~2"
:wait_http_loop
curl -s -o nul -m 2 "%TARGET%" && (endlocal & exit /b 0)
set /a LEFT-=1
if %LEFT% leq 0 (endlocal & exit /b 1)
ping -n 2 127.0.0.1 >nul
goto wait_http_loop

:stop_all
for /f "usebackq tokens=1,2" %%a in ("%LOG_DIR%\ports.txt") do (
  powershell -NoProfile -Command "foreach($p in @(%%a,%%b)){ Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
)
echo   已停止后端与前端服务。
exit /b 0

:fail
echo.
echo   启动未完成，请根据上面的提示处理后重试。
endlocal
exit /b 1
