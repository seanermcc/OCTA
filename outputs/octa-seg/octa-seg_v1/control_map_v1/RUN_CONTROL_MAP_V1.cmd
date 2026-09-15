@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
cd /d "%~dp0..\..\..\..\code"
python -u -m control_map_v1 %*
exit /b %errorlevel%
