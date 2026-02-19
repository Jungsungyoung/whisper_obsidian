@echo off
echo Starting MeetScribe...
cd /d "%~dp0"
set PATH=D:\cuda_libs\dlls;C:\Users\Admin\miniconda3\Lib\site-packages\torch\lib;%PATH%

where cloudflared >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    start "Cloudflare Tunnel" python tunnel.py
) else (
    echo [INFO] cloudflared not found - local mode only
    echo [INFO] Install: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
    echo.
)

uvicorn main:app --host 0.0.0.0 --port 8765
pause
