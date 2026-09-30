# Pipeline GRI: indicadores de extensão e condição de ecossistemas

Este repositório implementa uma pipeline automatizada em Python e Docker para cálculo dos indicadores de extensão e condição de ecossistemas exigidos pelo piloto da Nature Positive Initiative (NPI) e pelo padrão GRI 101: Biodiversidade.

A solução substitui um fluxo previamente distribuído entre Google Earth Engine, MATLAB, Python e intervenções manuais em QGIS, consolidando o processamento em uma rotina reprodutível, auditável e contêinerizada.

## Visão geral

O projeto calcula:

- frequência e condição de queimadas a partir do produto MODIS MCD64A1;
- condição da vegetação secundária por meio de uma equação assintótica de recuperação;
- condição de borda a partir da transformada euclidiana de distância;
- índice integrado de condição como produto dos três fatores;
- tabelas finais para as divulgações GRI 101-6 e 101-7.

A execução é orquestrada por scripts Python e controlada por `config.yaml`, com integração via Docker e Docker Compose para processamento geoespacial em raster.

## Contexto do projeto

O desenvolvimento do pipeline foi motivado pela necessidade de automatizar a rotina de cálculo de indicadores ecológicos usados no piloto da Nature Positive Initiative e na padronização GRI 101. O relatório técnico documenta a refatoração do fluxo e a validação do método em comparação com a rotina legada.

Principais ganhos da automação:

- reprodução dos resultados da rotina legada até a quinta casa decimal;
- eliminação de deslocamentos espaciais causados por ajustes manuais em SIG;
- execução reprodutível e auditável para a mesma entrada.

## Objetivo da pipeline

A pipeline gera mapas de condição e compara estados de cobertura e condição em anos distintos, com foco em:

- extensão da vegetação natural;
- condição ecológica dos ecossistemas;
- presença de bordas;
- impacto de incêndios;
- indicadores disponibilizados para relatórios ambientais e disclosures de biodiversidade.

## Estrutura do repositório

```text
.
├── README.md
├── config.yaml
├── config_backup.yaml
├── Dockerfile
├── docker-compose_raster.yml
├── docker-compose_table.yml
├── requirements.txt
├── Run_pipeline_area.py
├── docs/
│   └── fluxograma/
│       ├── diagrama_Npi_GRI_flow.mmd
│       └── pipeline_gri.mmd
├── scripts/
│   ├── burn/
│   ├── comparison/
│   ├── edge/
│   ├── gri/
│   ├── vegetation/
│   └── weights/
├── shared/
│   ├── __init__.py
│   ├── functions.py
│   ├── opunit_functions.py
│   ├── utils_gri.py
│   └── utils.py
├── inputs/
├── output/
├── tmp/
└── .gitignore
```

Os módulos em `shared/` armazenam utilitários reutilizados pelos scripts em `scripts/` e não devem ser executados isoladamente como etapa principal do pipeline.

## Dados e fontes de entrada

A pipeline depende de vários conjuntos de dados geoespaciais e tabelas auxiliares. Entre os principais:

- MapBiomas: uso e cobertura da terra, classes naturais e cobertura da área de estudo;
- MODIS MCD64A1: dados de frequência e condição de queimadas;
- shapefiles de estado, área operacional e camada de recorte;
- fitofisionomias e classes de vegetação natural;
- planilhas de reclassificação, legenda e metadados de unidades operacionais.

A estrutura de caminhos é definida em `config.yaml`, com placeholders como `{AREA}`, `{YEAR}`, `{BASE_YEAR}` e `{END_YEAR}`. Isso permite parametrizar a execução para diferentes áreas e anos sem alterar o código-fonte.

## Tabelas de referência

A seguir, os parâmetros e classes adotados para a modelagem da condição dos ecossistemas no Pará, conforme as Tabelas 1 e 2.

### Tabela 1 - Índices usados para classificar a condição de queimadas

| Nº de queimadas no período | Condição atribuída |
|---|---:|
| 1 queimada | 80% |
| 2 queimadas | 60% |
| 3 queimadas | 40% |
| ≥ 4 queimadas | 20% |

Esses valores são usados como penalização da condição ecológica em áreas queimadas e foram consolidados a partir de revisão de literatura pela equipe de Biodiversidade do ITV.

### Tabela 2 - Classes naturais do MapBiomas consideradas no cálculo da condição de borda para o estado do Pará

| Classe do MapBiomas (Coleção 10) | ID |
|---|---:|
| Formação Florestal | 3 |
| Formação Savânica | 4 |
| Mangue | 5 |
| Floresta Alagável | 6 |
| Campo Alagado e Área Pantanosa | 11 |
| Formação Campestre | 12 |
| Praia, Duna e Areal | 23 |
| Afloramento Rochoso | 29 |
| Apicum | 32 |
| Rio, Lago e Oceano | 33 |
| Sem dados | 0 |

A lista foi adaptada a partir do MapBiomas (2025) e aplicada no cálculo da distância de borda para o estado do Pará, com ressalva de revisão necessária para outras regiões.

## Fluxo de processamento

A pipeline é executada em sequência e cada etapa depende da conclusão bem-sucedida da anterior:

1. Vegetação secundária
   - cálculo da condição da vegetação secundária;
   - saída em raster de condição por pixel.

2. Frequência de queimadas
   - agregação dos dados MODIS para mapear a frequência de queimadas;
   - geração do raster de frequência.

3. Condição de queimadas
   - conversão da frequência em índice de condição de fogo;
   - uso de tabela de classes para reclassificação.

4. Condição de borda
   - cálculo do efeito de borda usando distância euclidiana;
   - processamento em blocos sobrepostos para reduzir artefatos.

5. Combinação das condições
   - composição do mapa final de condição dos ecossistemas;
   - integração de queimadas, borda e vegetação secundária.

6. Comparação entre anos
   - comparação do mapa base e do mapa final;
   - geração de indicadores de mudança e classe de condição.

7. Tabelas GRI
   - produção das tabelas de divulgação para GRI 101-6 e GRI 101-7;
   - exportação em CSV/XLSX conforme a estrutura exigida.

Os diagramas do fluxo estão em `docs/fluxograma/`.

## Requisitos

### Pré-requisitos locais

- Docker instalado e em execução;
- Docker Compose v2 (`docker compose`);
- Python 3 no host para executar os orquestradores;
- pacote `ruamel.yaml`:

```bash
python -m pip install ruamel.yaml
```

As dependências do processamento geoespacial estão listadas em `requirements.txt` e são instaladas na imagem Docker utilizada pela pipeline.

## Configuração

A configuração principal fica em `config.yaml`. Esse arquivo define:

- diretórios de entrada, saída e temporários;
- caminhos dos rasters e shapefiles;
- parâmetros de área, período e ano-base;
- parâmetros da condição de borda, queimadas e vegetação secundária;
- nomes dos arquivos de saída e da tabela GRI.

### Principais campos de configuração

```yaml
Paths:
  out_dir: "output"
  tmp_path: "tmp"
  lulc_path: "inputs/mapbiomas_col10/mapbiomas_col10_{AREA}_{YEAR}.tif"
  state_shp_path: "inputs/Shape_estados/{AREA}_Mapbiomas.shp"
  aio_shp_path: "inputs/Shapes_ADAIMO_2025/ADAIMO_2025_{AREA}.shp"

Data:
  area: "PA"
  start_year: 2000
  end_year: 2024
  base_year_compare: 2020
```

Antes de rodar a pipeline, confirme:

1. que os arquivos de entrada existem nos caminhos configurados;
2. que a área e o ano selecionados são coerentes com os dados disponíveis;
3. que os diretórios de saída e temporários possuem permissão de escrita.

## Execução

### 1) Executar a pipeline com a configuração padrão do projeto

```bash
python Run_pipeline_area.py
```

Esse orquestrador usa os parâmetros padrão configurados no script e executa o fluxo completo para a área e o período definidos.

### 2) Executar para uma área e um período específicos

```bash
python Run_pipeline_area.py --base-year 2020 --end-year 2024 --area PA
```

### Argumentos disponíveis

| Argumento | Descrição | Padrão |
|---|---|---|
| `--base-year` | Ano-base usado na comparação | `2020` |
| `--end-year` | Ano final do processamento | `2024` |
| `--area` | Área ou unidade de análise | `PA` |
| `--rebuild` | Força a reconstrução da imagem Docker | desativado |

### Forçar reconstrução da imagem Docker

```bash
python Run_pipeline_area.py --area PA --rebuild
```

O orquestrador também reconstrói a imagem quando o build local não existe ou quando o conteúdo de `Dockerfile` ou `requirements.txt` mudou.

## Saídas esperadas

A pipeline gera arquivos em `output/` e intermediários em `tmp/`, incluindo:

- rasters de condição de vegetação secundária;
- rasters de condicionamento de borda e queimadas;
- mapa integrado de condição dos ecossistemas;
- tabelas de comparação entre anos;
- arquivos finais de GRI, como `Saida1016_PA.csv` e `Saida1017b_PA.csv`;
- arquivos de suporte como `lulc_condicao_legenda_PA.csv` e `lulc_condicao_reclass_PA.csv`.

## Validação e estado atual

No relatório técnico, a validação foi realizada na Unidade Operacional N4N5 (Floresta Nacional de Carajás, PA), com 2020 como ano-base e 2024 como ano de análise. Os resultados mostraram:

- equivalência numérica com a rotina legada até a quinta casa decimal;
- eliminação de deslocamentos espaciais introduzidos por ajustes manuais em SIG;
- melhora na reprodutibilidade e auditabilidade do processamento;
- viabilidade operacional para o estado do Pará.

O projeto está estruturado para expansão futura para outras áreas e biomas, além de migração para a nuvem Microsoft Azure.

## Solução de problemas

- Se o Docker não estiver em execução, inicie o serviço e repita o processamento.
- Se uma etapa falhar por arquivo não encontrado, revise os caminhos em `config.yaml`.
- Verifique a área e os anos configurados para garantir consistência com os dados disponíveis.
- Em caso de erro, acompanhe a saída do terminal para diagnosticar a etapa que falhou.
- O orquestrador vai restaurar o arquivo de configuração a partir do backup antes do início do processamento.

## Observações finais

Este projeto integra processamento geoespacial, automação por container e geração de relatórios ambientais. Ele foi concebido para apoiar a análise de biodiversidade e a comunicação de indicadores conforme as exigências da Nature Positive Initiative e do padrão GRI 101.

Para uso prático, o fluxo recomendado é:

```bash
python Run_pipeline_area.py --base-year 2020 --end-year 2024 --area PA
```

Em seguida, consulte os arquivos de saída em `output/` e valide o resultado em relação ao contexto de uso da área e do período analisado.
