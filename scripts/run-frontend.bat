@echo off
rem 前端服务：由 start.bat 调用，端口读 FRONTEND_PORT，并把 API 代理指向 BACKEND_PORT
cd /d "%~dp0..\frontend"
if "%FRONTEND_PORT%"=="" set FRONTEND_PORT=5173
if "%BACKEND_PORT%"=="" set BACKEND_PORT=8010
set VITE_API_TARGET=http://127.0.0.1:%BACKEND_PORT%
echo [frontend] vite --port %FRONTEND_PORT% --target %VITE_API_TARGET%
call npx vite --host 127.0.0.1 --port %FRONTEND_PORT% --strictPort
