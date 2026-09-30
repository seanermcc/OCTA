@echo off
call D:\Programs\Anaconda\Scripts\activate.bat octa
set PYTHONDONTWRITEBYTECODE=1
cd /d G:\OCT_TreeShrew\octa
python -B outputs\octa-seg\octa-seg_v3\review\launch.py --reviewer demo --read-only
