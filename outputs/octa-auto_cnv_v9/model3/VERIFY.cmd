@echo off
setlocal
cd /d "%~dp0"
call "D:\Anaconda\Scripts\activate.bat" octa
python -B verify_delivery.py
