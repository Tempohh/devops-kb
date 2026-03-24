@echo off
:: KB Update - Modalita' Infinita
:: Gira in loop, attende il ripristino token se necessario.
:: Chiudi la finestra o premi Ctrl+C per interrompere.
:: Il contesto e' sempre salvato su disco tra una run e l'altra.

title KB Update - Infinito
cd /d "%~dp0"

powershell -ExecutionPolicy Bypass -NoLogo -File "_automation\kb-infinite.ps1"
