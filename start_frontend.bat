@echo off
echo Configurando Frontend...

:: --- CAMINHO CORRIGIDO BASEADO NO SEU COMANDO ANTERIOR ---
SET "NODE_PATH=C:\Users\CS260490\nodejs"

:: Adiciona o Node ao PATH desta janela
SET "PATH=%NODE_PATH%;%PATH%"

:: Entra na pasta do frontend
cd frontend

:: Verifica se o node existe
node -v >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Nao encontrei o Node.js em: %NODE_PATH%
    echo Verifique se a pasta existe.
    pause
    exit
)

:: Instala as dependencias se a pasta node_modules nao existir
if not exist node_modules (
    echo [AVISO] Instalando bibliotecas pela primeira vez...
    echo Isso pode demorar alguns minutos.
    call npm install
)

:: Roda o site
echo Iniciando o Site...
call npm run dev

:: Se der erro e o site fechar, isso mantem a janela aberta para voce ler
echo.
echo O servidor parou. Leia o erro acima.
pause