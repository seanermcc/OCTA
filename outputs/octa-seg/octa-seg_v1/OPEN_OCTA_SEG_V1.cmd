@echo off
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 (pause & exit /b 1)
cd /d G:\OCT_TreeShrew\octa
python code\cnv_review_v1\main.py --config "G:\OCT_TreeShrew\octa\outputs\octa-seg\octa-seg_v1\launch_config.json"
if errorlevel 1 pause
