@echo off
setlocal
cd /d "%~dp0.."
set PYTHONPATH=src;%CD%
py tests\run_tests.py
exit /b %ERRORLEVEL%
