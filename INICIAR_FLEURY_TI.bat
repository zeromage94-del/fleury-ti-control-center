@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Fleury TI Control Center - Servidor local
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 app.py
  goto :end
)
where python >nul 2>&1
if %errorlevel%==0 (
  python app.py
  goto :end
)
echo.
echo ERRO: Python 3.10 ou superior nao encontrado.
echo Instale Python pelo site https://www.python.org/downloads/windows/
echo Durante a instalacao, ative a opcao "Add python.exe to PATH".
echo.
:end
pause
