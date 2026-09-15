@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
cd /d "%~dp0"
python viewer.py %*
set "task_exit=%errorlevel%"
if not "%task_exit%"=="0" pause
exit /b %task_exit%

