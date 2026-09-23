@echo off
setlocal
cd /d "%~dp0"
if /I "%CONDA_DEFAULT_ENV%"=="octa" goto run
if defined OCTA_CONDA_ACTIVATE (
  call "%OCTA_CONDA_ACTIVATE%" octa
) else (
  call "D:\Anaconda\Scripts\activate.bat" octa
)
if errorlevel 1 goto fail
:run
python -B measure.py
if errorlevel 1 goto fail
echo Confirmed size reports are in reports\quantification.
pause
exit /b 0
:fail
echo Export failed. Existing human annotations have not been changed.
pause
exit /b 1
