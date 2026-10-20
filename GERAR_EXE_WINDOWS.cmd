@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ===========================================================
echo   GERADOR WINDOWS - FLEURY TI CONTROL CENTER v1.2
echo ===========================================================
echo.
echo Requer Windows 10/11 x64, Python 3.10+ para COMPILAR.
echo O EXE final nao exige Python na maquina do tecnico.
echo Inno Setup 6 e necessario apenas para gerar o instalador.
echo.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 build_windows.py
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python build_windows.py
    ) else (
        echo ERRO: Python nao encontrado para compilacao.
        echo Instale o Python oficial e execute novamente.
        pause
        exit /b 1
    )
)
if errorlevel 1 (
    echo.
    echo FALHA na compilacao. Consulte a mensagem acima.
    pause
    exit /b 1
)
echo.
echo SUCESSO: veja a pasta entrega_windows.
pause
