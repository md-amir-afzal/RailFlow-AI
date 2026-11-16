@echo off
setlocal
set "ROOT=%~dp0"
if not exist "%ROOT%backend\.venv\Scripts\python.exe" (
  echo First run setup_windows.bat to install backend dependencies.
  pause
  exit /b 1
)
if not exist "%ROOT%frontend\node_modules\vite\bin\vite.js" (
  echo Frontend dependencies are missing. Run setup_windows.bat first.
  pause
  exit /b 1
)
echo Starting RailFlow AI backend and frontend...
start "RailFlow AI - Backend API" cmd /k "cd /d ""%ROOT%backend"" && ""%ROOT%backend\.venv\Scripts\python.exe"" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
start "RailFlow AI - Frontend" cmd /k "cd /d ""%ROOT%frontend"" && npm run dev"
timeout /t 5 /nobreak >nul
start "" "http://127.0.0.1:5173"
echo.
echo Dashboard: http://127.0.0.1:5173
echo API docs:  http://127.0.0.1:8000/docs
echo Keep both terminal windows open while using RailFlow AI.
