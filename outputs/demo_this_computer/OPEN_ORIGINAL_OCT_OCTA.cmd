@echo off
setlocal
if exist G:\OCT_TreeShrew\octa\code\eight_surface\cnv_gui.py goto ready
if exist G:\ (
  echo G: is occupied. The original data paths cannot be restored.
  pause
  exit /b 1
)
subst G: F:\
:ready
call D:\Programs\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set PYTHONDONTWRITEBYTECODE=1
python -B "%~dp0original_oct_octa.py"
if errorlevel 1 pause
