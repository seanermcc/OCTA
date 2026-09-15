@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set "PYTHONPATH=%~dp0code;%~dp0..\..\..\code"
set "PYTHONDONTWRITEBYTECODE=1"
pushd "%~dp0"
python -m octa_seg_v2.gui %*
if errorlevel 1 pause
popd
