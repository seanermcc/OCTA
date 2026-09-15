@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
set "QT_QPA_PLATFORM=offscreen"
cd /d "%~dp0"
python test_workflow.py
if errorlevel 1 exit /b 1
python verify_gui.py
if errorlevel 1 exit /b 1
python viewer.py --scan TS267_OD_2025-03-05_D14_s01_104048 --manual --capture
if errorlevel 1 exit /b 1
python seal.py
exit /b %errorlevel%
