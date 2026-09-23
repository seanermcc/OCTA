@echo off
call D:\Anaconda\condabin\conda.bat activate octa
if errorlevel 1 exit /b 1
cd /d "%~dp0..\..\code"
python -m octa_reg_v1 run --output "%~dp0." %*
if errorlevel 1 pause
