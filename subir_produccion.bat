@echo off
setlocal
cd /d "%~dp0"
title Federacion - Subir a produccion

echo ============================================
echo   SUBIR CAMBIOS A PRODUCCION
echo ============================================

REM --- Activar entorno virtual ---
set "VENV="
for /d %%d in (venv*) do if exist "%%d\Scripts\activate.bat" set "VENV=%%d"
if not defined VENV (
    echo [ERROR] No encontre ningun entorno virtual venv* en esta carpeta.
    pause
    exit /b 1
)
call "%VENV%\Scripts\activate.bat"

REM --- Chequeos previos ---
echo.
echo Verificando el proyecto...
python manage.py check
if errorlevel 1 (
    echo [ERROR] Django encontro errores. No se sube nada.
    pause
    exit /b 1
)

python manage.py makemigrations --check --dry-run >nul 2>&1
if errorlevel 1 (
    echo [ATENCION] Hay cambios en los modelos sin migracion.
    echo Corre "python manage.py makemigrations" y volve a ejecutar este script.
    pause
    exit /b 1
)

REM --- Rama actual ---
for /f %%b in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%b"
echo Rama: %BRANCH%

REM --- Commit (solo si hay cambios) ---
echo.
git status --short
git status --porcelain | findstr . >nul
if errorlevel 1 (
    echo No hay cambios locales para commitear.
) else (
    git add -A

    REM Seguridad: que no se cuele ningun venv
    git diff --cached --name-only | findstr /i /r "^venv" >nul
    if not errorlevel 1 (
        echo [ERROR] Se estaba por subir una carpeta venv. Revisa el .gitignore.
        git reset >nul
        pause
        exit /b 1
    )

    set /p "MSG=Mensaje del commit: "
    call :commit
)

REM --- Traer cambios de la otra PC antes de subir ---
echo.
echo Trayendo cambios del repositorio...
git pull --rebase origin %BRANCH%
if errorlevel 1 (
    echo.
    echo [CONFLICTO] Hay conflictos con cambios de la otra PC.
    echo Resolvelos, despues corre "git rebase --continue" y volve a ejecutar este script.
    echo Si queres cancelar todo: "git rebase --abort"
    pause
    exit /b 1
)

REM --- Subir ---
echo.
echo Subiendo a GitHub...
git push origin %BRANCH%
if errorlevel 1 (
    echo [ERROR] No se pudo hacer el push.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   LISTO. Render va a deployar automaticamente.
echo ============================================
pause
exit /b 0

:commit
if "%MSG%"=="" set "MSG=Actualizacion %date% %time:~0,5%"
git commit -m "%MSG%"
exit /b 0
