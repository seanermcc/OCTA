@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
cd /d "%~dp0"
python pilot.py %*
if errorlevel 1 exit /b 1
python report_v3.py
exit /b %errorlevel%
