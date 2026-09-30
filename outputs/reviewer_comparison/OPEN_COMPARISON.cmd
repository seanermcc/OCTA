@echo off
setlocal
if exist "D:\Programs\Anaconda\Scripts\activate.bat" (
  set "OCTA_COMPARE_ACTIVATE=D:\Programs\Anaconda\Scripts\activate.bat"
) else if exist "D:\Anaconda\Scripts\activate.bat" (
  set "OCTA_COMPARE_ACTIVATE=D:\Anaconda\Scripts\activate.bat"
) else (
  rem The complete viewer also works offline; exports use browser downloads.
  start "" "%~dp0index.html"
  exit /b 0
)
set "OCTA_COMPARE_ROOT=%~dp0..\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_server.ps1"
