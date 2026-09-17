@echo off
chcp 65001 >nul
title Vonne Boutique - Monitor Loyverse Telegram
cd /d "C:\Users\PC3\Documents\Antigravity\Vonne boutique\sitio_web_github"

:MENU
cls
echo ===================================================================
echo             VONNE BOUTIQUE - NOTIFICADOR LOYVERSE TELEGRAM
echo ===================================================================
echo  1. Enviar mensaje de prueba a Telegram (Verificar conexion)
echo  2. Iniciar monitor en segundo plano (Silencioso e invisible)
echo  3. Iniciar monitor en esta ventana (Ver registro de eventos en vivo)
echo  4. Instalar en el Inicio automatico de Windows (Al prender la PC)
echo  5. Detener monitor en segundo plano
echo  6. Salir
echo ===================================================================
echo.
set /p opcion="Selecciona una opcion (1-6): "

if "%opcion%"=="1" goto PROBAR
if "%opcion%"=="2" goto SEGUNDO_PLANO
if "%opcion%"=="3" goto EN_VIVO
if "%opcion%"=="4" goto INSTALAR
if "%opcion%"=="5" goto DETENER
if "%opcion%"=="6" goto SALIR
goto MENU

:PROBAR
cls
echo Probando conexion con Telegram...
echo.
python telegram_notifier.py --test
echo.
pause
goto MENU

:SEGUNDO_PLANO
cls
echo Iniciando notificador en segundo plano...
wscript.exe ejecutar_telegram_silencioso.vbs
echo.
echo [OK] El notificador esta ejecutandose de forma invisible.
echo Puedes cerrar esta ventana. Recibiras alertas directamente en Telegram.
echo.
pause
goto MENU

:EN_VIVO
cls
python telegram_notifier.py --daemon
pause
goto MENU

:INSTALAR
cls
call instalar_telegram_inicio_windows.bat
goto MENU

:DETENER
cls
echo Deteniendo procesos de notificador en segundo plano...
taskkill /F /IM pythonw.exe /T >nul 2>&1
echo [OK] Monitor detenido.
echo.
pause
goto MENU

:SALIR
exit
