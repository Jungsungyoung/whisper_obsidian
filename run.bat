@echo off
echo MeetScribe 시작 중...
cd /d "%~dp0"
set PATH=D:\cuda_libs\dlls;%PATH%
uvicorn main:app --host 0.0.0.0 --port 8765
pause
