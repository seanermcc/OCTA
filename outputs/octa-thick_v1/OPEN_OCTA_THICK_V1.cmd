@echo off
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 (pause & exit /b 1)
cd /d "%~dp0"
python viewer.py %*
if errorlevel 1 pause
