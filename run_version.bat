@echo off
:: Kör en specifik version av Activity Tracker från källkoden
:: Användning: run_version.bat v0.13b   (kör specifik version)
::             run_version.bat latest    (återgå till main/senaste)
::             run_version.bat           (visar tillgängliga versioner)

cd C:\dev\verktyg\activity_tracker

if "%1"=="" (
    echo.
    echo Tillgängliga versioner:
    git tag --sort=-version:refname
    echo.
    echo Nuvarande:
    git describe --tags --exact-match 2>NUL || git rev-parse --abbrev-ref HEAD
    echo.
    echo Användning: run_version.bat v0.13b
    echo             run_version.bat latest    ^(återgå till main^)
    pause
    exit /b 0
)

:: Stäng eventuell körande instans
taskkill /f /im ActivityTracker.exe 2>NUL
taskkill /f /im pythonw.exe 2>NUL
timeout /t 2 /nobreak >NUL

:: "latest" = återgå till main och popa eventuell stash
if /i "%1"=="latest" (
    git checkout main --quiet 2>NUL
    if errorlevel 1 git checkout master --quiet 2>NUL
    git stash pop --quiet 2>NUL
    echo Återgår till senaste versionen ^(main^)...
    goto :start_app
)

:: Spara pågående ändringar om det finns några
git stash --quiet 2>NUL

:: Checka ut önskad version
git checkout %1 --quiet 2>NUL
if errorlevel 1 (
    echo Versionen "%1" hittades inte.
    git stash pop --quiet 2>NUL
    pause
    exit /b 1
)

echo Kör version %1...

:start_app
echo (Stäng fönstret eller kör run_version.bat utan argument för att lista versioner)
echo (Kör "run_version.bat latest" för att återgå till senaste versionen)
echo.

:: Hitta pythonw
for /f "delims=" %%i in ('where pythonw 2^>NUL') do set PYTHONW=%%i
if not defined PYTHONW (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" set PYTHONW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe
)

if not defined PYTHONW (
    echo Kunde inte hitta pythonw.exe
    pause
    exit /b 1
)

start "" "%PYTHONW%" "C:\dev\verktyg\activity_tracker\tray_app.py"
