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
    :: Fallback: leta i vanliga installationsplatser
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" set PYTHONW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe
    if exist "C:\Python312\pythonw.exe" set PYTHONW=C:\Python312\pythonw.exe
)

if not defined PYTHONW (
    echo Kunde inte hitta pythonw.exe. Kontrollera att Python är installerat.
    pause
    exit /b 1
)

start "" "%PYTHONW%" "C:\activity_tracker\tray_app.py"
