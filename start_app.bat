@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo Starting Agentic Multilingual Tutor Application...
echo ===================================================

cd /d "%~dp0"

:: 1. Detect Python Executable
set "PY_CMD=python"
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
    echo Using virtual environment at .venv
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0venv\Scripts\python.exe"
    echo Using virtual environment at venv
) else (
    where python >nul 2>nul
    if !errorlevel! neq 0 (
        where py >nul 2>nul
        if !errorlevel! equ 0 (
            set "PY_CMD=py"
        ) else (
            echo [ERROR] Python was not found in PATH!
            pause
            exit /b 1
        )
    )
)

:: 2. Set PYTHONPATH to include backend
set "PYTHONPATH=%~dp0backend"

:: 3. Clear existing zombie processes on ports 8000 and 5173 if any
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 "') do (
    taskkill /F /PID %%a >nul 2>nul
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173 "') do (
    taskkill /F /PID %%a >nul 2>nul
)

:: 4. Start FastAPI Backend in new window
echo [1/3] Starting FastAPI backend on http://127.0.0.1:8000...
start "Agentic Tutor Backend (FastAPI)" cmd /k "cd /d "%~dp0" && set PYTHONPATH=%~dp0backend && "%PY_CMD%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
timeout /t 2 /nobreak >nul

:: 5. Start Vite Frontend in new window
echo [2/3] Starting Vite frontend on http://localhost:5173...
start "Agentic Tutor Frontend (Vite)" cmd /k "cd /d "%~dp0frontend" && npm run dev -- --host 0.0.0.0 --port 5173"
timeout /t 3 /nobreak >nul

:: 6. Open Default Web Browser
echo [3/3] Opening browser at http://localhost:5173...
start http://localhost:5173

echo.
echo ===================================================
echo Application successfully launched!
echo Frontend: http://localhost:5173
echo Backend:  http://127.0.0.1:8000
echo ===================================================
