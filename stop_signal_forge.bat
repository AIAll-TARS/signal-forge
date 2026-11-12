@echo off
REM Stop the local Signal Forge server listening on its default port.
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8765 ^| findstr LISTENING') do taskkill /PID %%a /F
echo Signal Forge stop request sent.
