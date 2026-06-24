Componentes principais do programa:
  1. portico_mef.py: Resolvedor principal (MEF com condensação de rótulas).
  2. visualizacao.py: Interface gráfica interativa (wxPython + Matplotlib).
  3. gerar_memorial.py: Gerador automático de relatório Word (.docx).

---------------------------------------------------------------------------
1. PRÉ-REQUISITOS (Configuração do Ambiente)
---------------------------------------------------------------------------
Certifique-se de que o Python 3.x está instalado na máquina.

Para instalar as dependências necessárias no Windows:
1. Abra a pasta do projeto no Windows Explorer.
2. Clique na barra de endereços no topo da janela, apague o caminho atual, 
   digite "cmd" e aperte Enter. (O Prompt de Comando abrirá direto na pasta).
3. No prompt, digite o seguinte comando e aperte Enter:

   pip install -r requirements.txt

Isso instalará automaticamente as bibliotecas:
- numpy (cálculos matemáticos)
- matplotlib (gráficos e diagramas)
- wxPython (interface da janela gráfica)
- python-docx (geração de documentos de texto)

---------------------------------------------------------------------------
2. COMO EXECUTAR
---------------------------------------------------------------------------

Método A (Automático via Script Batch):
  - Dê dois cliques em "executar.bat".
  - O terminal listará todos os arquivos ".txt" de entrada disponíveis.
  - Digite o número correspondente ao arquivo que quer analisar (ex: exemplo_viga_gerber.txt) e aperte Enter.
  - O programa rodará a análise estrutural, atualizará o memorial e abrirá a visualização gráfica automaticamente.

Método B (Manual via Terminal):
  - Para rodar apenas o resolvedor MEF e gerar os dados de um arquivo:
    python portico_mef.py exemplo_viga_gerber.txt

  - Para abrir o visualizador de resultados a qualquer momento:
    Dê dois cliques no arquivo "visualizar.bat" (ou digite no terminal "python visualizacao.py resultados.json").

---------------------------------------------------------------------------
3. RECURSOS DO VISUALIZADOR INTERATIVO
---------------------------------------------------------------------------
Ao abrir a janela gráfica, você pode interagir com os resultados:

  - Painel de Controle (Esquerda):
    * Camadas / Esforços: Marque ou desmarque para ver a geometria original, a Deformada, Diagramas (N, V, M), Cargas aplicadas e Reações de apoio.
    * Equações: Ative para exibir as fórmulas matemáticas analíticas ao longo de cada trecho de barra direto no gráfico.
    * Controle de Escala: Use os controles deslizantes (Sliders) para amplificar ou reduzir a escala visual da Deformada e dos Diagramas sem alterar os limites do gráfico.
    * Enquadrar Vista: Redefine o enquadramento ideal da estrutura na tela.

  - Seleção Interativa por Clique do Mouse:
    * Clique com o mouse em qualquer parte da estrutura no gráfico (desde que os botões de Zoom/Pan do Matplotlib não estejam ativos).
    * O programa detectará o ponto mais próximo e destacará com um marcador de alvo (círculo amarelo/vermelho) e um balão (callout box) com os dados.
    * Snapping Inteligente: Clicar perto de uma extremidade ou nó atrai a seleção diretamente para o nó (facilitando a consulta).
    * Painel "Informações de Seleção" (Esquerda): Mostra o nome do elemento, a posição exata (ex: x = 1.25m), coordenadas e os valores de deslocamento horizontal (ux), vertical (uy) em milímetros e rotação (θz) em radianos e graus.

---------------------------------------------------------------------------
4. ARQUIVOS DE SAÍDA GERADOS
---------------------------------------------------------------------------
Toda vez que a análise estrutural é executada, o resolvedor cria na pasta:
  - resultados.json: Contém todas as matrizes, vetores e pontos de esforços.
  - Memorial_Calculo_Resultados.docx: relatório gerado de 
    forma automática contendo o passo a passo matemático, tabelas de dados, 
    vetores, matrizes locais (normais e condensadas de rótulas), diagramas e 
    uma seção didática explicando a formulação da condensação estática.
