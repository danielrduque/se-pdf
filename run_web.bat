@echo off
rem App web: backend FastAPI + frontend React compilado. Abre http://127.0.0.1:8000
cd /d "%~dp0"
if not exist web\dist (
  echo Compilando el frontend por primera vez...
  pushd web
  call npm install --no-audit --no-fund
  call npm run build
  popd
)
docker compose up -d --wait db
powershell -NoProfile -ExecutionPolicy Bypass -File tools\llamacpp_start.ps1 -IfDown
.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000
