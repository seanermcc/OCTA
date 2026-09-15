@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0code;%~dp0..\..\code"
cd /d "%~dp0"
python code\longitudinal_assessment.py %*
exit /b %errorlevel%
