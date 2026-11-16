@echo off
setlocal
set "ROOT=%~dp0"
echo ==========================================
echo       RAILFLOW AI - FIRST TIME SETUP
echo ==========================================
where python >nul 2>nul || (echo Python 3.10+ is required. Install from https://www.python.org/downloads/ and enable Add Python to PATH.& pause & exit /b 1)
where node >nul 2>nul || (echo Node.js 20+ is required. Install from https://nodejs.org/ and reopen this window.& pause & exit /b 1)
where npm >nul 2>nul || (echo npm was not found. Reinstall Node.js and ensure npm is added to PATH.& pause & exit /b 1)
cd /d "%ROOT%backend"
if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Creating Python virtual environment...
  python -m venv .venv || goto :failed
)
echo [2/4] Installing backend dependencies...
"%ROOT%backend\.venv\Scripts\python.exe" -m pip install --upgrade pip || goto :failed
"%ROOT%backend\.venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :failed
cd /d "%ROOT%frontend"
echo [3/4] Installing frontend dependencies (internet connection required)...
npm install || goto :failed
echo [4/4] Starting RailFlow AI...
call "%ROOT%run_windows.bat"
exit /b 0
:failed
echo.
echo Setup did not complete. Read the error above, check your internet connection, then run setup_windows.bat again.
pause
exit /b 1
