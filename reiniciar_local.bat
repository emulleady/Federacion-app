@echo off
setlocal
cd /d "%~dp0"
title Federacion - Servidor local

echo ============================================
echo   REINICIANDO SERVIDOR LOCAL
echo ============================================

REM --- Cortar cualquier servidor que este usando el puerto 8000 ---
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo Cerrando proceso anterior en puerto 8000 - PID %%a
    taskkill /PID %%a /F >nul 2>&1
)

REM --- Buscar el entorno virtual (venv, venv2, etc.) ---
set "VENV="
for /d %%d in (venv*) do if exist "%%d\Scripts\activate.bat" set "VENV=%%d"
if not defined VENV (
    echo [ERROR] No encontre ningun entorno virtual venv* en esta carpeta.
    pause
    exit /b 1
)
echo Usando entorno virtual: %VENV%
call "%VENV%\Scripts\activate.bat"

REM --- Dependencias y migraciones ---
echo.
echo Instalando dependencias nuevas (si hay)...
pip install -r requirements.txt -q

echo.
echo Aplicando migraciones...
python manage.py migrate
if errorlevel 1 (
    echo [ERROR] Fallaron las migraciones. Revisa el mensaje de arriba.
    pause
    exit /b 1
)

REM --- Levantar servidor ---
echo.
echo Servidor en http://127.0.0.1:8000  (Ctrl+C para cortar)
echo.
python manage.py runserver
pause
