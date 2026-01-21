@echo off
setlocal

set ROOT=%~dp0

if exist "%ROOT%.venv\Scripts\python.exe" (
  set PY=%ROOT%.venv\Scripts\python.exe
) else (
  set PY=python
)

cd /d "%ROOT%"

set DEFAULT_GAMERTAG=JGtm
set DEFAULT_XUID=2533274823110022

if "%SPNKR_PLAYER%"=="" (
  set "SPNKR_PLAYER=%DEFAULT_GAMERTAG%"
)

:menu
cls
echo ==============================================
echo OpenSpartan Graphs - Lancement
echo ==============================================
echo Repo: %ROOT%
echo Python: %PY%
echo.
echo Joueur SPNKr (SPNKR_PLAYER): %SPNKR_PLAYER%
echo (Default gamertag=%DEFAULT_GAMERTAG% / xuid=%DEFAULT_XUID%)
echo.
echo Choisis une option:
echo   1) SPNKr: backfill (match + events) pour le joueur
echo   2) SPNKr: rafraichir TOUTES les DB (data\spnkr*.db)
echo   3) Lancer le dashboard (sans refresh)
echo   4) Lancer le dashboard + refresh SPNKr (avant)
echo   5) Changer le joueur SPNKr
echo   Q) Quitter
echo.

choice /c 12345Q /n /m "Tape 1/2/3/4/5 ou Q puis Entrée: "

if errorlevel 6 goto :eof
if errorlevel 5 goto :set_player
if errorlevel 4 goto :launch_with_refresh
if errorlevel 3 goto :launch
if errorlevel 2 goto :refresh_all
if errorlevel 1 goto :backfill_one

:set_player
echo.
set /p "SPNKR_PLAYER=Nouveau SPNKR_PLAYER (gamertag ou XUID): "
if "%SPNKR_PLAYER%"=="" set "SPNKR_PLAYER=%DEFAULT_GAMERTAG%"
goto :menu

:backfill_one
echo.
echo [SPNKr] Backfill pour: %SPNKR_PLAYER%
echo.
set "OUT_DB=%ROOT%data\spnkr_gt_%SPNKR_PLAYER%.db"
if "%SPNKR_PLAYER%"=="" goto :menu
if "%SPNKR_PLAYER%"=="%DEFAULT_XUID%" (
  set "OUT_DB=%ROOT%data\spnkr_xuid_%SPNKR_PLAYER%.db"
)
if "%SPNKR_PLAYER%"=="%DEFAULT_GAMERTAG%" (
  set "OUT_DB=%ROOT%data\spnkr_gt_%SPNKR_PLAYER%.db"
)

set /p "MAX_MATCHES=Max matchs (defaut 500): "
if "%MAX_MATCHES%"=="" set "MAX_MATCHES=500"
set /p "MATCH_TYPE=Type de matchs [all/matchmaking/custom/local] (defaut matchmaking): "
if "%MATCH_TYPE%"=="" set "MATCH_TYPE=matchmaking"
set /p "RPS=Requetes/seconde (defaut 2): "
if "%RPS%"=="" set "RPS=2"

echo.
echo [SPNKr] Import safe (temp + replace si OK)
echo out_db: %OUT_DB%
"%PY%" "%ROOT%run_dashboard.py" --refresh-spnkr --refresh-player "%SPNKR_PLAYER%" --refresh-out-db "%OUT_DB%" --refresh-match-type %MATCH_TYPE% --refresh-max-matches %MAX_MATCHES% --refresh-rps %RPS% --refresh-with-highlight-events
echo.
pause
goto :menu

:refresh_all
echo.
echo [SPNKr] Refresh toutes les DB data\spnkr*.db
echo.
call "%ROOT%refresh_all_dbs.bat"
echo.
pause
goto :menu

:launch
echo.
echo Lancement OpenSpartan Graphs...
"%PY%" "%ROOT%run_dashboard.py"
echo.
echo (Ferme cette fenetre pour arreter le serveur)
pause
goto :menu

:launch_with_refresh
echo.
echo Lancement dashboard + refresh SPNKr pour: %SPNKR_PLAYER%
"%PY%" "%ROOT%run_dashboard.py" --refresh-spnkr --refresh-player "%SPNKR_PLAYER%"
echo.
echo (Ferme cette fenetre pour arreter le serveur)
pause
goto :menu
