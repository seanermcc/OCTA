@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
cd /d "%~dp0"
python -B summarize_review.py
