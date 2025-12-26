@echo off
cd /d %~dp0
echo Starting WebApp/API only (no Telegram bot)...
python keep_alive.py
pause
