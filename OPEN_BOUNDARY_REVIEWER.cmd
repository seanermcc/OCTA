@echo off
setlocal
rem CNV-Core / Full-CNV release; save to the Passport reviewer store.
if not exist "F:\octa\OPEN_BOUNDARY_REVIEWER.cmd" (
  echo Connect My Passport as F: to open the cached boundary reviewer.
  pause
  exit /b 1
)
call "F:\octa\OPEN_BOUNDARY_REVIEWER.cmd" %*
