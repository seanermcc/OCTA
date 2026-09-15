@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
cd /d "%~dp0"
if not exist logs mkdir logs
python -B -u viewer.py %* >> logs\viewer.log 2>&1
if errorlevel 1 pause
