@echo off
chcp 65001 >nul
title Vonne Boutique - Auto-Respondedor de Comentarios Facebook
cd /d "C:\Users\PC3\Documents\Antigravity\Vonne boutique\sitio_web_github"

:MENU
cls
echo ===================================================================
echo          VONNE BOUTIQUE - AUTO-RESPONDEDOR CON IA (FACEBOOK)
echo ===================================================================
echo  1. Ejecutar simulacion con comentarios de prueba (Ver respuestas)
echo  2. Probar una pregunta personalizada
echo  3. Iniciar en esta ventana (Ver escaneo en vivo cada 5 min)
echo  4. Iniciar en segundo plano (Silencioso e invisible)
echo  5. Detener servicio en segundo plano
echo  6. Salir
echo ===================================================================
echo.
set /p opcion="Selecciona una opcion (1-6): "

if "%opcion%"=="1" goto SIMULAR
if "%opcion%"=="2" goto PREGUNTA
if "%opcion%"=="3" goto EN_VIVO
if "%opcion%"=="4" goto SEGUNDO_PLANO
if "%opcion%"=="5" goto DETENER
if "%opcion%"=="6" goto SALIR
goto MENU

:SIMULAR
cls
echo ===================================================================
echo          SIMULANDO RESPUESTAS DE IA PARA VONNE BOUTIQUE
echo ===================================================================
echo.
python facebook_ai_comment_responder.py --simulate
echo.
pause
goto MENU

:PREGUNTA
cls
echo Escribe la pregunta que haria una clienta (ej: "Precio de la capa"):
set /p pregunta="Pregunta: "
echo.
python facebook_ai_comment_responder.py --test-comment "%pregunta%"
echo.
pause
goto MENU

:EN_VIVO
cls
echo Iniciando escaneo en vivo de Facebook (Presiona Ctrl+C para salir)...
echo.
python facebook_ai_comment_responder.py --daemon
pause
goto MENU

:SEGUNDO_PLANO
cls
echo Iniciando Auto-Respondedor en segundo plano...
wscript.exe ejecutar_facebook_ai_silencioso.vbs
echo.
echo [OK] El asistente de IA esta activo de forma invisible.
echo Monitoreara y respondera comentarios automaticamente.
echo.
pause
goto MENU

:DETENER
cls
echo Deteniendo procesos en segundo plano...
taskkill /F /FI "WINDOWTITLE eq *facebook_ai*" >nul 2>&1
echo [OK] Servicio detenido.
echo.
pause
goto MENU

:SALIR
exit
