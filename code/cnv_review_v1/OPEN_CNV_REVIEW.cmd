@echo off
call D:\Anaconda\condabin\conda.bat activate octa
if errorlevel 1 goto failed
cd /d "%~dp0..\.."
python code\cnv_review_v1\main.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo The CNV reviewer could not start. See the error above.
pause
