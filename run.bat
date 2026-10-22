@echo off
cd /d "%~dp0"
docker compose up -d --wait db
powershell -NoProfile -ExecutionPolicy Bypass -File tools\llamacpp_start.ps1 -IfDown
.venv\Scripts\python.exe -m streamlit run app.py
