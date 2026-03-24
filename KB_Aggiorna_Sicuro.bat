@echo off
:: KB Update - Modalita' Sicura
:: Esegue una singola operazione e si ferma.
:: Lascia margine di token per uso personale di Claude.

title KB Update - Sicuro
cd /d "%~dp0"

powershell -ExecutionPolicy Bypass -NoLogo -File "_automation\kb-safe.ps1"
