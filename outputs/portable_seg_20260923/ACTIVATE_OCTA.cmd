@echo off
if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" for %%I in ("%CONDA_PREFIX%") do if /I "%%~nxI"=="octa" exit /b 0
if defined OCTA_CONDA_ACTIVATE if exist "%OCTA_CONDA_ACTIVATE%" (call "%OCTA_CONDA_ACTIVATE%" octa & exit /b)
for %%P in ("%USERPROFILE%\miniconda3\Scripts\activate.bat" "%USERPROFILE%\anaconda3\Scripts\activate.bat" "%LOCALAPPDATA%\miniconda3\Scripts\activate.bat" "%ProgramData%\miniconda3\Scripts\activate.bat" "%ProgramData%\anaconda3\Scripts\activate.bat" "D:\Anaconda\Scripts\activate.bat") do if exist "%%~P" (call "%%~P" octa & exit /b)
echo Activate your octa conda environment, then run OPEN_REVIEWER.cmd again.
echo For a new computer, read START_HERE.md for setup.
exit /b 1
