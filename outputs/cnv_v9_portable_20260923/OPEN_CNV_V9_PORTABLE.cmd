@echo off
setlocal
call D:\Programs\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set PYTHONDONTWRITEBYTECODE=1
cd /d "%~dp0"
python -B open_portable.py %*
