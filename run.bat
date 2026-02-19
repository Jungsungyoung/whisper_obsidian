@echo off
echo MeetScribe 시작 중...
cd /d "%~dp0"
set PATH=D:\cuda_libs\dlls;C:\Users\Admin\miniconda3\Lib\site-packages\torch\lib;%PATH%

:: Cloudflare Tunnel — 외부 접속 URL 생성 (cloudflared 설치 시)
where cloudflared >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Cloudflare Tunnel 시작 중...
    start /B cloudflared tunnel --url http://localhost:8765
    echo 터널 URL이 잠시 후 위에 출력됩니다.
    echo.
) else (
    echo [INFO] cloudflared 미설치 - 외부 접속 없이 로컬 모드로 실행
    echo [INFO] 설치: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
    echo.
)

uvicorn main:app --host 0.0.0.0 --port 8765
pause
