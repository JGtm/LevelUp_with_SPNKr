@echo off
setlocal

set ROOT=%~dp0

if exist "%ROOT%.venv\Scripts\python.exe" (
  set PY=%ROOT%.venv\Scripts\python.exe
) else (
  set PY=python
)

cd /d "%ROOT%"

echo Lancement OpenSpartan Graphs...
set DEFAULT_GAMERTAG=JGtm
set DEFAULT_XUID=2533274823110022

if "%SPNKR_PLAYER%"=="" (
  set SPNKR_PLAYER=%DEFAULT_GAMERTAG%
)

echo.
echo [SPNKr] Joueur cible: %SPNKR_PLAYER%
echo [SPNKr] (Default gamertag=%DEFAULT_GAMERTAG% / xuid=%DEFAULT_XUID%)
echo [SPNKr] (Override possible via variable d'env SPNKR_PLAYER)

if not "%SPNKR_PLAYER%"=="" (
  "%PY%" "%ROOT%run_dashboard.py" --refresh-spnkr --refresh-no-skill
  if exist "%ROOT%data\spnkr.db" (
    set OPENSPARTAN_DB_PATH=%ROOT%data\spnkr.db
  )
) else (
  "%PY%" "%ROOT%run_dashboard.py"
)

echo.
echo (Ferme cette fenetre pour arreter le serveur)
pause
