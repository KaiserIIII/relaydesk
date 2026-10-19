@echo off
setlocal
cd /d "%~dp0"
python -X utf8 -m relaydesk demo
if errorlevel 1 goto failed
python -X utf8 -m relaydesk serve
if errorlevel 1 goto failed
exit /b 0
:failed
pause
exit /b 1
