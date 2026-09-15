@echo off
setlocal
cd /d "%~dp0"
if /i "%CONDA_DEFAULT_ENV%"=="octa" goto ready
if defined OCTA_CONDA_ACTIVATE (
    call "%OCTA_CONDA_ACTIVATE%" octa
    if not errorlevel 1 goto ready
)
where conda >nul 2>&1
if not errorlevel 1 (
    call conda activate octa
    if not errorlevel 1 goto ready
)
if exist D:\Anaconda\Scripts\activate.bat (
    call D:\Anaconda\Scripts\activate.bat octa
    if not errorlevel 1 goto ready
)
echo Activate the octa environment in Anaconda Prompt, then run SHOW_MODELS.cmd.
echo See DEMO_GUIDE.md for work-computer setup and offline galleries.
pause
exit /b 1
:ready
set "PYTHONDONTWRITEBYTECODE=1"
python -B code\demo_models.py %*
if errorlevel 1 pause
