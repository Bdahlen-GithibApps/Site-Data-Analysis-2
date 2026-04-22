@echo off
REM share_public.bat — starts the app if needed and opens a public Cloudflare tunnel

set "APP_URL=http://127.0.0.1:8081"

where cloudflared >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: cloudflared is not installed or not on PATH.
    echo Install it from:
    echo   https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
    echo Then run this file again.
    pause
    exit /b 1
)

echo.
echo Checking whether the app is already running on %APP_URL% ...
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing %APP_URL% ^| Out-Null; exit 0 } catch { exit 1 }"
IF %ERRORLEVEL% NEQ 0 (
    echo App not detected. Starting run.bat in a new window...
    start "Site Data App" cmd /k run.bat

    echo Waiting for the local app to come online...
    powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(90); do { try { Invoke-WebRequest -UseBasicParsing '%APP_URL%' ^| Out-Null; exit 0 } catch { Start-Sleep -Milliseconds 500 } } while ((Get-Date) -lt $deadline); exit 1"
    IF %ERRORLEVEL% NEQ 0 (
        echo.
        echo ERROR: The app did not start within 90 seconds.
        echo Check the Site Data App window for errors, then run this file again.
        pause
        exit /b 1
    )
)

echo.
echo Local app is reachable.
echo Starting Cloudflare Quick Tunnel...
echo Share the https://*.trycloudflare.com URL shown below with your users.
echo Keep this window open while they use the app.
echo.

cloudflared tunnel --url %APP_URL%