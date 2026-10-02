@echo off
setlocal
cd /d "%~dp0"
title Federacion - Verificar estado

REM ====== CONFIGURAR: URL de produccion en Render, sin barra al final ======
set "PROD_URL=https://TU-APP.onrender.com"
REM ==========================================================================

set "TODO_OK=1"

echo ============================================
echo   VERIFICANDO ESTADO DEL PROYECTO
echo ============================================

REM --- Entorno virtual ---
set "VENV="
for /d %%d in (venv*) do if exist "%%d\Scripts\activate.bat" set "VENV=%%d"
if not defined VENV goto :sin_venv
call "%VENV%\Scripts\activate.bat"

REM --- Rama y fetch ---
for /f %%b in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%b"
echo Rama: %BRANCH%
git fetch origin -q

echo.
echo [1] Cambios sin commitear
git status --porcelain | findstr . >nul
if errorlevel 1 goto :sin_cambios
echo     [X] Hay archivos modificados sin commitear:
git status --short
set "TODO_OK=0"
goto :paso2
:sin_cambios
echo     [OK] Nada pendiente
:paso2

echo.
echo [2] Local vs GitHub
for /f "tokens=1,2" %%a in ('git rev-list --left-right --count HEAD...origin/%BRANCH%') do (
    set "AHEAD=%%a"
    set "BEHIND=%%b"
)
if not "%AHEAD%"=="0" echo     [X] Tenes %AHEAD% commits locales sin subir a GitHub
if not "%AHEAD%"=="0" set "TODO_OK=0"
if not "%BEHIND%"=="0" echo     [X] GitHub tiene %BEHIND% commits que no bajaste - posiblemente de la otra PC
if not "%BEHIND%"=="0" set "TODO_OK=0"
if "%AHEAD%%BEHIND%"=="00" echo     [OK] Local y GitHub iguales

echo.
echo [3] Migraciones
python manage.py makemigrations --check --dry-run >nul 2>&1
if errorlevel 1 echo     [X] Hay cambios en modelos sin makemigrations
if errorlevel 1 set "TODO_OK=0"
python manage.py migrate --check >nul 2>&1
if errorlevel 1 echo     [X] Hay migraciones sin aplicar en tu base local
if errorlevel 1 set "TODO_OK=0"
echo     Revision de migraciones terminada

echo.
echo [4] GitHub vs Produccion - Render
for /f %%c in ('git rev-parse origin/%BRANCH%') do set "GITHUB_COMMIT=%%c"
set "PROD_COMMIT="
for /f %%c in ('powershell -NoProfile -Command "try { (Invoke-RestMethod '%PROD_URL%/version/' -TimeoutSec 20).commit } catch { 'ERROR' }"') do set "PROD_COMMIT=%%c"

if "%PROD_COMMIT%"=="ERROR" goto :prod_error
if "%PROD_COMMIT%"=="%GITHUB_COMMIT%" goto :prod_ok
echo     [X] Produccion NO tiene la ultima version
echo         GitHub:     %GITHUB_COMMIT:~0,7%
echo         Produccion: %PROD_COMMIT:~0,7%
echo         Revisa en Render si el deploy esta en curso o fallo.
set "TODO_OK=0"
goto :resumen
:prod_ok
echo     [OK] Produccion esta en el ultimo commit %PROD_COMMIT:~0,7%
goto :resumen
:prod_error
echo     [X] No pude consultar %PROD_URL%/version/
echo         Puede estar dormido, caido, o falta agregar la vista /version/
set "TODO_OK=0"

:resumen
echo.
echo ============================================
if "%TODO_OK%"=="1" echo   TODO ACTUALIZADO
if "%TODO_OK%"=="0" echo   HAY COSAS PENDIENTES - mira los [X] de arriba
echo ============================================
pause
exit /b 0

:sin_venv
echo [ERROR] No encontre ningun entorno virtual venv* en esta carpeta.
pause
exit /b 1
