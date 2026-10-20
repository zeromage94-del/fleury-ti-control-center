@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "FleuryTIControlCenter.exe" (
  start "" "FleuryTIControlCenter.exe"
  exit /b 0
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 app.py
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    python app.py
  ) else (
    echo Esta distribuicao de codigo-fonte precisa de Python.
    echo Para criar EXE sem dependencia de Python, execute GERAR_EXE_WINDOWS.cmd no Windows.
  )
)
pause
