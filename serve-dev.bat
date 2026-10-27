@echo off
cd /d "C:\Users\anton\OneDrive\Desktop\radar-de-concursos"
"C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe" -m radar serve --db data\radar.sqlite3 --port 8000 >> "%TEMP%\radar-serve.log" 2>&1
