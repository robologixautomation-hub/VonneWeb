@echo off
chcp 65001 >nul
title Configurar Notificador Telegram en Inicio de Windows

echo ================================================================
echo   Instalar Notificador Loyverse - Telegram en Inicio de Windows
echo   Vonne Boutique Saltillo
echo ================================================================
echo.

set TARGET_DIR=C:\Users\PC3\Documents\Antigravity\Vonne boutique\sitio_web_github
set VBS_SCRIPT=%TARGET_DIR%\ejecutar_telegram_silencioso.vbs
set SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\VonneTelegramNotifier.lnk

if not exist "%VBS_SCRIPT%" (
    echo [ERROR] No se encontro el archivo %VBS_SCRIPT%
    pause
    exit /b 1
)

echo Creando acceso directo en la carpeta de Inicio de Windows...
powershell "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT%');$s.TargetPath='wscript.exe';$s.Arguments='\"%VBS_SCRIPT%\"';$s.WorkingDirectory='%TARGET_DIR%';$s.Save()"

if exist "%SHORTCUT%" (
    echo.
    echo [OK] El monitor ha quedado instalado en el inicio automatico de Windows.
    echo Se ejecutara de forma silenciosa cada vez que enciendas la computadora.
    echo.
) else (
    echo.
    echo [ERROR] No se pudo crear el acceso directo automatico.
    echo.
)

pause
