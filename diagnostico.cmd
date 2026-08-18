@echo off
setlocal
set "TRADUCTOR_DEBUG=%TEMP%\traductor_debug.log"
set "TRADUCTOR_DEBUG_CAPTURE=%TEMP%\traductor_capture.png"
echo Reiniciando TraductorLens con diagnostico...
echo Log: %TRADUCTOR_DEBUG%
echo Imagen capturada: %TRADUCTOR_DEBUG_CAPTURE%
echo.
echo 1) Coloca la ventana sobre un texto (pagina web, documento, etc.)
echo 2) Espera 5 segundos
echo 3) Cierra la app y ejecuta:   type "%TRADUCTOR_DEBUG%"
echo.
taskkill /IM TraductorLens.exe /F >nul 2>&1
start "" "%~dp0dist\TraductorLens.exe"
