@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
cd /d "%~dp0"
python pilot.py %*
if errorlevel 1 goto failed
python finalize.py
if errorlevel 1 goto failed
python test_workflow.py
if errorlevel 1 goto failed
exit /b 0
:failed
set "task_exit=%errorlevel%"
pause
exit /b %task_exit%
