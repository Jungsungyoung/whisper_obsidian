@echo off
echo MeetScribe 시작 중...
cd /d "%~dp0"
uvicorn main:app --host 0.0.0.0 --port 8765
pause
