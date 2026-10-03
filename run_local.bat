@echo off
rem Run SafeOrder locally: double-click this file (needs Python 3.11+; see README)
cd /d "%~dp0"
where py >nul 2>nul && (py -3 run_local.py %* & goto :end)
where python >nul 2>nul && (python run_local.py %* & goto :end)
echo Python 3.11 or newer is needed: https://www.python.org/downloads/
:end
pause
