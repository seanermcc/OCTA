@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
cd /d "%~dp0"
python -B -u refine_inventory.py > verification\metadata_refinement.log 2>&1
if errorlevel 1 exit /b %errorlevel%
python -B -u environment_provenance.py > verification\environment.log 2>&1
if errorlevel 1 exit /b %errorlevel%
python -B -u summarize_review.py > verification\human_summary.log 2>&1
if errorlevel 1 exit /b %errorlevel%
python -B -u asset_storage.py >> verification\storage_compaction.log 2>&1
exit /b %errorlevel%
