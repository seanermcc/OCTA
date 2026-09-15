@echo off
call D:\Anaconda\Scripts\activate.bat octa
cd /d "G:\OCT_TreeShrew\octa"
set "PYTHONPATH=G:\OCT_TreeShrew\octa\code"
python -m quality_pilot.evaluate_reviews
pause
