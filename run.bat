@echo off
cd /d "%~dp0"

where python3 >nul 2>nul
if %errorlevel%==0 (
    python3 railway_auto.py
) else (
    python railway_auto.py
)

pause
