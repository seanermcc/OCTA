@echo off
call D:\Anaconda\condabin\conda.bat activate octa
if errorlevel 1 exit /b 1
cd /d G:\OCT_TreeShrew\octa
python code\batch_vasculature_v1.py
pause
