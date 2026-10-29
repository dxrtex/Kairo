@echo off
cd /d "%~dp0"
echo Kairo Research - Datenabruf SEC + Dukascopy. Fenster bitte offen lassen.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0kairo_daten_laden.ps1" %*
pause
