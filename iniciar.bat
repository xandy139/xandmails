@echo off
chcp 65001 > nul
title XandMails - Monitor de Código em Tempo Real

echo ========================================================
echo       XandMails - Monitor de Codigo de E-mail
echo ========================================================
echo.

if not exist ".venv" (
    echo [INFO] Criando ambiente virtual Python...
    python -m venv .venv
    echo [INFO] Instalando dependencias...
    .\.venv\Scripts\pip.exe install -r requirements.txt
)

echo [INFO] Abrindo navegador em http://localhost:5000 ...
start http://localhost:5000

echo [INFO] Iniciando servidor web...
.\.venv\Scripts\python.exe app.py

pause
