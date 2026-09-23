@echo off
setlocal
cd /d "%~dp0"
call "D:\Anaconda\Scripts\activate.bat" octa
if errorlevel 1 exit /b 1
python -B run_pipeline.py
exit /b %errorlevel%
