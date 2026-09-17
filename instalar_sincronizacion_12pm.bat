@echo off
chcp 65001 > nul
title Programar Sincronización Diaria 12:00 PM - Vonne Boutique

echo =======================================================================
echo     VONNE BOUTIQUE - PROGRAMADOR DE SINCRONIZACIÓN AUTOMÁTICA
echo     Plaza La Fragua, Saltillo, Coahuila
echo     Horario programado: Todos los días a las 12:00 PM (Mediodía)
echo =======================================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "VBS_SCRIPT=%SCRIPT_DIR%ejecutar_sync_silencioso.vbs"

echo Registrando tarea en el Programador de Tareas de Windows...
schtasks /create /tn "VonneBoutique_Sync_12PM" /tr "\"C:\Windows\System32\wscript.exe\" \"%VBS_SCRIPT%\"" /sc daily /st 12:00 /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo =======================================================================
    echo  ¡CONFIGURACIÓN EXITOSA!
    echo  - Tu catálogo se actualizará automáticamente todos los días a las 12:00 PM.
    echo  - Se ejecuta en segundo plano de forma 100%% silenciosa.
    echo  - Puedes consultar el archivo 'historial_sincronizacion.log' para
    echo    ver el registro con fecha y hora de cada actualización.
    echo =======================================================================
) else (
    echo.
    echo ⚠️ Hubo un detalle al registrar la tarea.
    echo Si te pide permisos, dale clic derecho a este archivo y selecciona
    echo 'Ejecutar como Administrador'.
)

echo.
pause
