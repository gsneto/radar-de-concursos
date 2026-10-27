@echo off
rem Sobe o servidor local na porta 8000 usando o venv do projeto.
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -m radar serve --db data\radar.sqlite3 --port 8000 >> "%TEMP%\radar-serve.log" 2>&1
