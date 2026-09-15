@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
python "%~dp0launch.py" %*
if errorlevel 1 pause
