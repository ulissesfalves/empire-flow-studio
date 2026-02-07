@echo off
echo Configurando ambiente portatil...

:: Caminhos das ferramentas
SET "FFMPEG_PATH=C:\Users\CS260490\tools\ffmpeg\bin"
SET "IMAGEMAGICK_PATH=C:\Users\CS260490\tools\imagemagick"

:: Adiciona ao PATH
SET "PATH=%FFMPEG_PATH%;%IMAGEMAGICK_PATH%;%PATH%"

:: Ativa o Python venv
call venv\Scripts\activate.bat

:: Roda o servidor
echo Iniciando Backend...
uvicorn backend.main:app --reload