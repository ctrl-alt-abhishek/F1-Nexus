@echo off
title F1 Degradation App Launcher
echo ========================================================
echo Starting F1 Degradation App (Backend + Frontend)
echo ========================================================

cd /d "%~dp0"

echo [1/2] Starting Backend Server (Uvicorn on port 8000)...
start "F1 Nexus Backend" cmd /k "cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"

echo [2/2] Starting Frontend Dev Server...
start "F1 Nexus Frontend" cmd /k "cd frontend && npm run dev"

echo ========================================================
echo Launch complete! Separate terminal windows have been spawned.
echo ========================================================
