@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
set "QT_QPA_PLATFORM=offscreen"
cd /d "%~dp0"
python -B -u test_real_gui.py --first-new > verification\new_gui.log 2>&1
exit /b %errorlevel%
