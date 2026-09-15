@echo off
setlocal
call D:\Anaconda\Scripts\activate.bat octa
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
cd /d "%~dp0"
python -B -u audit_contract.py > verification\implementation_contract.log 2>&1
exit /b %errorlevel%
