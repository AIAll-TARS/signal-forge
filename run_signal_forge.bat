@echo off
REM Signal Forge Windows launcher. It is safe to launch from Explorer or any folder.
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Creating local Python environment...
  py -3 -m venv .venv || goto :error
)
echo Installing Signal Forge locally...
"%PY%" -m pip install --disable-pip-version-check -e . || goto :error
REM init-db is idempotent. Seed sources are imported only when this is a fresh database.
if not exist "signal-forge.db" (
  "%PY%" -m signal_forge --db signal-forge.db init-db || goto :error
  "%PY%" -m signal_forge --db signal-forge.db import-sources config\sources.seed.yaml || goto :error
)
echo Starting Signal Forge. Close this window or use stop_signal_forge.bat to stop it.
start "" http://127.0.0.1:8765/
"%PY%" -m signal_forge --db signal-forge.db serve --host 127.0.0.1 --port 8765
goto :end
:error
echo.
echo Signal Forge could not start. Review the message above.
pause
:end
endlocal
