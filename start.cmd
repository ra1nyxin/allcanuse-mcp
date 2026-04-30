@echo off
setlocal
cd /d "%~dp0"
python run_server.py %*
