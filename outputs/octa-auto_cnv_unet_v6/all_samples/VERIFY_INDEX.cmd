@echo off
setlocal
cd /d "%~dp0"
"D:\Program Files\node.exe" test_index.js > verification\index_tests.log 2>&1
exit /b %errorlevel%
