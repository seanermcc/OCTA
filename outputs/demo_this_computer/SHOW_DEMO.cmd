@echo off
setlocal
if exist G:\OCT_TreeShrew\octa\DEMO_GUIDE.md goto ready
if exist G:\ (
 echo G: is occupied. Check the drive before launching.
 pause
 exit /b 1
)
subst G: F:\
:ready
set "OCTA_CONDA_ACTIVATE=D:\Programs\Anaconda\Scripts\activate.bat"
call "%OCTA_CONDA_ACTIVATE%" octa
python -B "%~dp0demo_models.py" %*
