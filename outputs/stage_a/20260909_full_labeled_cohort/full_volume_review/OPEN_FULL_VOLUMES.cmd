@echo off
call "D:\Anaconda\condabin\conda.bat" activate octa
if errorlevel 1 goto failed
cd /d "G:\OCT_TreeShrew\octa"
python "G:\OCT_TreeShrew\octa\code\stage_a_full_volume_gui.py" "%~dp0packs" --labels "G:\OCT_TreeShrew\octa\outputs\eight_surface\labels"
if errorlevel 1 goto failed
exit /b 0
:failed
echo The labeling window could not start. Please keep this message for troubleshooting.
pause
exit /b 1
