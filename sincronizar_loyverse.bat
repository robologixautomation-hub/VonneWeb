@echo off
chcp 65001 > nul
title Sincronizador de Inventario - Vonne Boutique
echo ========================================================
echo       VONNE BOUTIQUE - SINCRONIZADOR DE INVENTARIO
echo       Plaza La Fragua, Saltillo, Coahuila
echo ========================================================
echo.
echo Sincronizando catalogo con Loyverse POS...
python sync_loyverse.py
echo.
echo ========================================================
echo Sincronizacion finalizada.
echo Abre o recarga tu pagina web index.html para ver los cambios.
echo ========================================================
pause
