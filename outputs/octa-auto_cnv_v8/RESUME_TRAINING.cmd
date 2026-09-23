@echo off
setlocal
set PYTHONDONTWRITEBYTECODE=1
cd /d "%~dp0"
if /I "%CONDA_DEFAULT_ENV%"=="octa" goto run
call "D:\Anaconda\Scripts\activate.bat" octa
if errorlevel 1 goto fail
:run
python -B audit.py
if errorlevel 1 goto fail
python -B prepare.py --optics-only
if errorlevel 1 goto fail
python -B prepare.py
if errorlevel 1 goto fail
python -B verify.py --sanity
if errorlevel 1 goto fail
python -B train.py --model 1
if errorlevel 1 goto fail
python -B train_structural.py --model 2
if errorlevel 1 goto fail
python -B predict.py --model 1
if errorlevel 1 goto fail
python -B predict.py --model 2
if errorlevel 1 goto fail
python -B preservation.py --after
if errorlevel 1 goto fail
python -B finalize.py
if errorlevel 1 goto fail
exit /b 0
:fail
echo V8 stopped on an error. Do not interpret an incomplete run as a trained release.
pause
exit /b 1
