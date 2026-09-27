@echo off
rem 后端服务：由 start.bat 调用，端口读环境变量 BACKEND_PORT
cd /d "%~dp0..\backend"
set PYTHONIOENCODING=utf-8
if "%BACKEND_PORT%"=="" set BACKEND_PORT=8010
echo [backend] uvicorn app.main:app --port %BACKEND_PORT%
python -m uvicorn app.main:app --host 127.0.0.1 --port %BACKEND_PORT% --log-level info
