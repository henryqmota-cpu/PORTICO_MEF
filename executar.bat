@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   Executando MEF - Analise de Porticos Planos
echo ===================================================
echo.
echo Arquivos de entrada disponiveis (.txt):
echo.

set count=0
for %%f in (*.txt) do (
    set /a count+=1
    set "file[!count!]=%%f"
    echo [!count!] %%f
)

echo.
set /p escolha="Digite o numero do arquivo desejado e aperte ENTER: "

set arquivo_entrada=!file[%escolha%]!

if "%arquivo_entrada%"=="" (
    echo.
    echo Opcao invalida!
    pause
    exit /b
)

echo.
echo ===================================================
echo [1] Rodando o calculo (portico_mef.py) para o arquivo: %arquivo_entrada%...
python portico_mef.py "%arquivo_entrada%"

echo.
echo [2] Abrindo a visualizacao grafica (visualizacao.py)...
python visualizacao.py resultados.json

echo.
pause
