@echo off
cd /d "%~dp0"
if exist v1_manual_v2.html (
 start "" "%~dp0v1_manual_v2.html"
 exit /b 0
)
if not exist index.html (
 echo Gallery has not finished. Run RUN_OR_RESUME.cmd first.
 pause
 exit /b 1
)
start "" "%~dp0index.html"
