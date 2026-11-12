@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
python -m radar.trova_chat_id
pause
