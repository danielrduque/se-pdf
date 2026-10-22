@echo off
rem Descarga los modelos de Ollama (hacer una sola vez, despues de instalar Ollama).
rem Si se corta la descarga, vuelve a ejecutarlo: ollama reanuda donde se quedo.
:retry
ollama pull embeddinggemma-2:740m || (echo Reintentando... & timeout /t 5 >nul & goto retry)
:retry2
ollama pull gemma3:4b || (echo Reintentando... & timeout /t 5 >nul & goto retry2)
echo.
echo Listo. Ahora ejecuta run.bat
pause
