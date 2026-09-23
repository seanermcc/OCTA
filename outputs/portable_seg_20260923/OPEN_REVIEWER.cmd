@echo off
setlocal
call "%~dp0ACTIVATE_OCTA.cmd"
if errorlevel 1 (pause & exit /b 1)
set "PYTHONDONTWRITEBYTECODE=1"
python "%~dp0outputs\octa-seg\octa-seg_v3\review\launch.py" --reviewer lead %*
if errorlevel 1 pause
