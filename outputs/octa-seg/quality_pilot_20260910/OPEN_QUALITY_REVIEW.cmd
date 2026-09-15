@echo off
call D:\Anaconda\Scripts\activate.bat octa
cd /d "G:\OCT_TreeShrew\octa"
set "PYTHONPATH=G:\OCT_TreeShrew\octa\code"
python -m cnv_review_v1.main --config "G:\OCT_TreeShrew\octa\outputs\octa-seg\quality_pilot_20260910\launch_config.json"
if errorlevel 1 pause
