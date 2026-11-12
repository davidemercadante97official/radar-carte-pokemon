@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
python -m tests.test_matching
python -m radar.prova_telegram
pause
