@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
cd /d "%~dp0"
python -B -u check_new_acquisition.py %* >> verification\new_acquisition.log 2>&1
exit /b %errorlevel%
