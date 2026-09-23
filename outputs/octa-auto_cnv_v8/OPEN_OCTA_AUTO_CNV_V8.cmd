@echo off
setlocal
set PYTHONDONTWRITEBYTECODE=1
cd /d "%~dp0"
if /I "%CONDA_DEFAULT_ENV%"=="octa" goto run
call "D:\Anaconda\Scripts\activate.bat" octa
if errorlevel 1 goto fail
:run
python -B viewer.py %*
if errorlevel 1 goto fail
exit /b 0
:fail
echo CNV v8 viewer could not start. Read the error above.
pause
exit /b 1
