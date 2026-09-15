@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
cd /d "%~dp0"
python -B -u batch.py --scan TS336_OD_2026-07-28_D56_s01_143412 > verification\first_new_predictions.log 2>&1
exit /b %errorlevel%
