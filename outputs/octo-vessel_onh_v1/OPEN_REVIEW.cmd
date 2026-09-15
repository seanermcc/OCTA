@echo off
call D:\Anaconda\condabin\conda.bat activate octa
if errorlevel 1 exit /b 1
cd /d "%~dp0"
python app.py %*
if errorlevel 1 pause
