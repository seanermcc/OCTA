@echo off
setlocal
cd /d "%~dp0..\.."
if exist "D:\Programs\Anaconda\Scripts\activate.bat" (
  call "D:\Programs\Anaconda\Scripts\activate.bat" octa
) else if exist "D:\Anaconda\Scripts\activate.bat" (
  call "D:\Anaconda\Scripts\activate.bat" octa
) else (
  call conda activate octa
)
if errorlevel 1 (
  echo Could not activate the octa environment.
  pause
  exit /b 1
)
set "PYTHONDONTWRITEBYTECODE=1"
python -u code\reviewer_compare\build.py --lead "F:\octa\For_Segmentation\Reviews\reviewers\lead"
if errorlevel 1 (
  echo Comparison refresh failed. Read the error above.
  pause
  exit /b 1
)
call "%~dp0OPEN_COMPARISON.cmd"
