@echo off
chcp 65001 > nul
title Programar Sincronizacion Diaria 4:00 PM y 8:00 PM - Vonne Boutique

echo =======================================================================
echo     VONNE BOUTIQUE - PROGRAMADOR DE SINCRONIZACION AUTOMATICA
echo     Plaza La Fragua, Saltillo, Coahuila
echo     Horario programado: Todos los dias a las 4:00 PM y 8:00 PM
echo =======================================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "VBS_SCRIPT=%SCRIPT_DIR%ejecutar_sync_silencioso.vbs"

echo Registrando tarea de las 4:00 PM en el Programador de Tareas...
schtasks /create /tn "VonneBoutique_Sync_4PM" /tr ""C:\Windows\System32\wscript.exe" "%VBS_SCRIPT%"" /sc daily /st 16:00 /f

echo Registrando tarea de las 8:00 PM en el Programador de Tareas...
schtasks /create /tn "VonneBoutique_Sync_8PM" /tr ""C:\Windows\System32\wscript.exe" "%VBS_SCRIPT%"" /sc daily /st 20:00 /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo =======================================================================
    echo  CONFIGURACION EXITOSA!
    echo  - Tu catalogo se sincronizara con Loyverse a las 4:00 PM y a las 8:00 PM.
    echo  - Se ejecuta en segundo plano de forma 100%% silenciosa.
    echo  - Puedes consultar el archivo 'historial_sincronizacion.log' para
    echo    ver el registro de cada actualizacion.
    echo =======================================================================
) else (
    echo.
    echo Hubo un detalle al registrar la tarea.
    echo Si te pide permisos, dale clic derecho a este archivo y selecciona
    echo 'Ejecutar como Administrador'.
)

echo.
pause
