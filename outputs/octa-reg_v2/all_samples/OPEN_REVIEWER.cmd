@echo off
call D:\Anaconda\Scripts\activate.bat octa
cd /d "%~dp0..\..\.."
set PYTHONPATH=%CD%\code
python -c "import urllib.request,json; assert json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/health', timeout=2))['service']=='octa-reg-v2-review'" >nul 2>&1
if errorlevel 1 start "" /min powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0START_SERVER.ps1"
if "%~1"=="" (start "" "http://127.0.0.1:8771/index.html") else (start "" "http://127.0.0.1:8771/%~1/index.html")
