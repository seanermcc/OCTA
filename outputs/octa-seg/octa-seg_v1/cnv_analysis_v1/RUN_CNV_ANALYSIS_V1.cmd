@echo off
call D:\Anaconda\condabin\conda.bat activate octa
if errorlevel 1 exit /b %errorlevel%
cd /d G:\OCT_TreeShrew\octa
set PYTHONPATH=G:\OCT_TreeShrew\octa\code
python -m cnv_analysis_v1 run --config outputs/octa-seg/octa-seg_v1/cnv_analysis_v1/config.json
if errorlevel 1 pause
