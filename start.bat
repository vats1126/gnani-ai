@echo off
echo ===================================================
echo Starting Gnani AI Fullstack Application...
echo ===================================================
cd /d "%~dp0"

start "Gnani AI Backend (FastAPI)" cmd /k "cd /d "%~dp0backend" && "C:\Users\vivek\AppData\Local\Programs\Python\Python313\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
timeout /t 2 /nobreak >nul

start "Gnani AI Frontend (Vite)" cmd /k "cd /d "%~dp0frontend" && npm run dev -- --host 0.0.0.0 --port 5173"
timeout /t 3 /nobreak >nul

start http://localhost:5173
echo.
echo Application launched!
echo Frontend: http://localhost:5173
echo Backend:  http://127.0.0.1:8000
echo ===================================================
