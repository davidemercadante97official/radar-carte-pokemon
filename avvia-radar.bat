@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
echo Radar carte Pokemon: un giro ogni 15 minuti. Chiudi questa finestra per fermarlo.
python -m radar.main --ogni 15
pause
