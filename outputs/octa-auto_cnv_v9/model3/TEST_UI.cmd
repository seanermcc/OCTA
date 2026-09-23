@echo off
setlocal
cd /d "%~dp0"
call "D:\Anaconda\Scripts\activate.bat" octa
python -B ui_fixture.py
if errorlevel 1 exit /b 1
python -B server.py --fixture --port 8804
