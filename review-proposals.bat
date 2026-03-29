@echo off
cd /d "%~dp0"
python _automation\review-proposals.py %*
pause
