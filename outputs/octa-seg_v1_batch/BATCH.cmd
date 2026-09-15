@echo off
setlocal
call D:\Programs\Anaconda\condabin\conda.bat activate octa
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
cd /d "%~dp0"
python -u code\batch.py %*
exit /b %errorlevel%
