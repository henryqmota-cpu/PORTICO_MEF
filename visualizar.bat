@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo =======================================================================
echo   Visualizador Gráfico de Pórticos Planos - MEF
echo =======================================================================
echo.

:: Contar arquivos .json de resultados disponíveis
set count=0
for %%f in (*.json) do (
    set /a count+=1
    set "file[!count!]=%%f"
)

if %count%==0 (
    echo [AVISO] Nenhum arquivo .json de resultados foi encontrado na raiz do projeto.
    echo.
    echo Para gerar os resultados, execute o resolvedor principal primeiro:
    echo Exemplo:
    echo   python portico_mef.py exemplo_viga_gerber.txt
    echo.
    echo Pressione qualquer tecla para sair...
    pause > nul
    exit /b
)

if %count%==1 (
    echo [INFO] Abrindo o arquivo de resultados: !file[1]!
    python visualizacao.py !file[1]!
    exit /b
)

echo Foram encontrados %count% arquivos de resultados .json.
echo Por favor, selecione qual deseja visualizar:
echo.
for /l %%i in (1,1,%count%) do (
    echo   [%%i] !file[%%i]!
)
echo.

:prompt
set /p escolha="Digite o número da sua escolha (ou 'S' para sair): "

if /i "%escolha%"=="S" (
    echo Saindo...
    exit /b
)

:: Validar escolha do usuário
if not defined file[%escolha%] (
    echo Opção inválida. Por favor, digite um número entre 1 e %count%.
    goto prompt
)

echo.
echo [INFO] Abrindo o arquivo de resultados: !file[%escolha%]!
python visualizacao.py !file[%escolha%]!

endlocal
