@echo off
cd C:\activity_tracker

:: Starta Ollama om den inte redan körs
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if errorlevel 1 (
    start "" /min ollama serve
)

:: Hitta pythonw.exe dynamiskt
for /f "delims=" %%i in ('where pythonw 2^>NUL') do set PYTHONW=%%i
if not defined PYTHONW (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" set PYTHONW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe
    if exist "C:\Python312\pythonw.exe" set PYTHONW=C:\Python312\pythonw.exe
)

if not defined PYTHONW (
    echo Kunde inte hitta pythonw.exe. Kontrollera att Python ar installerat.
    pause
    exit /b 1
)

set MAX_ATTEMPTS=3
set ATTEMPT=0

:TRY
set /a ATTEMPT+=1
if %ATTEMPT% gtr %MAX_ATTEMPTS% goto FAIL

:: Rensa eventuella stale-processer och lock-fil
taskkill /F /IM pythonw.exe /T >NUL 2>&1
timeout /t 2 /nobreak >NUL
if exist "%USERPROFILE%\activity_tracker\tray.lock" del /F "%USERPROFILE%\activity_tracker\tray.lock" >NUL 2>&1

:: Starta appen
start "" "%PYTHONW%" "C:\activity_tracker\tray_app.py"

:: Polla port 5757 tills appen svarar (max 30s)
set WAITED=0
:POLL
timeout /t 3 /nobreak >NUL
set /a WAITED+=3
curl -s --connect-timeout 1 -o NUL http://localhost:5757
if not errorlevel 1 goto SUCCESS
if %WAITED% lss 30 goto POLL

echo Forsok %ATTEMPT% av %MAX_ATTEMPTS% misslyckades, provar igen...
goto TRY

:SUCCESS
echo Activity Tracker koer pa localhost:5757
exit /b 0

:FAIL
echo Appen startade inte efter %MAX_ATTEMPTS% forsok. Kontrollera loggarna.
pause
exit /b 1
