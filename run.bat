@echo off
echo Starting MeetScribe...
cd /d "%~dp0"
set PATH=D:\cuda_libs\dlls;C:\Users\Admin\miniconda3\Lib\site-packages\torch\lib;%PATH%

:: Cloudflare Tunnel (external access URL) - requires cloudflared installed
where cloudflared >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Starting Cloudflare Tunnel...
    start "" /B cloudflared tunnel --url http://localhost:8765
    echo Tunnel URL will appear above in a moment.
    echo.
) else (
    echo [INFO] cloudflared not found - running in local mode only
    echo [INFO] Install: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
    echo.
)

uvicorn main:app --host 0.0.0.0 --port 8765
pause
