@echo off
setlocal
cd /d "%~dp0"
if not exist "logs" mkdir "logs"

:restart
echo [%date% %time%] Starting CV Career Agent...>>"logs\bot.log"
"%~dp0.venv\Scripts\python.exe" -u "%~dp0bot.py" >>"logs\bot.log" 2>>"logs\bot-error.log"
echo [%date% %time%] Bot stopped. Restarting in 15 seconds.>>"logs\bot.log"
timeout /t 15 /nobreak >nul
goto restart
