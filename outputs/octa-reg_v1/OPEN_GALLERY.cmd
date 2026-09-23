@echo off
if not exist "%~dp0index.html" (
 echo Run RUN_OR_RESUME.cmd first.
 pause
 exit /b 1
)
start "" "%~dp0index.html"
