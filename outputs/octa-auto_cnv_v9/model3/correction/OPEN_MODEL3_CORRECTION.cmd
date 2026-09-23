@echo off
setlocal
set PYTHONDONTWRITEBYTECODE=1
cd /d "%~dp0"
if /I "%CONDA_DEFAULT_ENV%"=="octa" goto run
if defined OCTA_CONDA_ACTIVATE (
  call "%OCTA_CONDA_ACTIVATE%" octa
) else (
  call "D:\Anaconda\Scripts\activate.bat" octa
)
if errorlevel 1 goto fail
:run
python -B viewer.py %*
if errorlevel 1 goto fail
exit /b 0
:fail
echo CNV Model 3 correction could not start. Activate the octa environment and retry.
pause
exit /b 1


