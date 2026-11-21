@echo off
cd /d "%~dp0"
for /f "tokens=5" %%P in ('netstat -ano -p TCP ^| findstr ":18765" ^| findstr "LISTENING"') do taskkill /F /PID %%P >nul 2>&1
set "PY="
if exist "%~dp0python\python.exe" set "PY=%~dp0python\python.exe"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY where py >nul 2>&1 && set "PY=py -3"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY (
  echo Install Python 3, then run this file again.
  start "" "https://www.python.org/downloads/"
  pause
  exit /b 1
)
if not exist "%~dp0bridge.py" (
  echo bridge.py missing in this folder
  pause
  exit /b 1
)
netsh advfirewall firewall add rule name="DuiJuTuiJian" dir=in action=allow protocol=TCP localport=18765 >nul 2>&1
"%PY%" "%~dp0bridge.py" --setup
