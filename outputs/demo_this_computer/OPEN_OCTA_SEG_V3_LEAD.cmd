@echo off
setlocal
if exist G:\OCT_TreeShrew\octa\outputs\octa-seg\octa-seg_v3\review\launch.py goto ready
if exist G:\ (
  echo G: is occupied. Check the external drive mapping.
  exit /b 1
)
subst G: F:\
:ready
call D:\Programs\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set PYTHONDONTWRITEBYTECODE=1
python -B "G:\OCT_TreeShrew\octa\outputs\octa-seg\octa-seg_v3\review\launch.py" --reviewer lead
