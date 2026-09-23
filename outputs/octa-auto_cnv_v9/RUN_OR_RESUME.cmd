@echo off
setlocal
set PYTHONDONTWRITEBYTECODE=1
cd /d "%~dp0"
call "D:\Anaconda\Scripts\activate.bat" octa
if errorlevel 1 exit /b 1
python -B run_compute.py
if errorlevel 1 exit /b 1
python -B freeze_scoring.py
if errorlevel 1 exit /b 1
python -B deliver.py
if errorlevel 1 exit /b 1
python -B verify_release.py --final
if errorlevel 1 exit /b 1
python -B verify_controlled_comparison.py
if errorlevel 1 exit /b 1
python -B polish_delivery.py
if errorlevel 1 exit /b 1
echo Both models and the comparison gallery are ready. Open OPEN_GALLERY.cmd.
pause
