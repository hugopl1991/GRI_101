# Pipeline GRI — processamento de condições

Pipeline geoespacial para gerar indicadores de vegetação secundária, frequência de queimadas e condição de borda, combinar essas condições em mapas e produzir tabelas relacionadas ao GRI.

## Índice

- [Visão geral](#visão-geral)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Pré-requisitos](#pré-requisitos)
- [Preparação dos dados](#preparação-dos-dados)
- [Execução](#execução)
- [Configuração](#configuração)
- [Etapas do pipeline](#etapas-do-pipeline)
- [Saídas e solução de problemas](#saídas-e-solução-de-problemas)

## Visão geral

Os scripts de processamento são executados em containers Docker, usando a imagem geoespacial `osgeo/gdal`. Os arquivos locais de entrada, configuração e saída são montados no container; portanto, os dados necessários precisam estar acessíveis nos caminhos definidos em `config.yaml`.

Execute os comandos a partir da raiz do repositório. Os orquestradores atualizam `config.yaml` durante o processamento e criam uma cópia de segurança antes de iniciar.

## Estrutura do repositório

```text
.
├── config.yaml
├── config_backup.yaml
├── Dockerfile
├── docker-compose_raster.yml
├── docker-compose_table.yml
├── requirements.txt
├── Run_pipeline.py
├── Run_pipeline_area.py
├── scripts/
│   ├── burn/          # Frequência e condição de queimadas
│   ├── comparison/    # Comparação dos mapas entre anos
│   ├── edge/          # Condição de borda
│   ├── gri/           # Tabelas e indicadores GRI
│   ├── vegetation/    # Vegetação secundária
│   └── weights/       # Mapa combinado de condições
├── shared/            # Funções e utilitários compartilhados
├── docs/fluxograma/   # Diagramas do fluxo
├── tests/fixtures/    # Arquivos históricos de teste
├── inputs/            # Dados locais de entrada
├── output/            # Resultados do processamento
└── tmp/               # Arquivos temporários
```

Os módulos de `shared/` não são etapas executáveis isoladamente: são utilizados pelos scripts em `scripts/`. Os arquivos em `tests/fixtures/` são exemplos legados e não representam, por si só, uma suíte automatizada de testes.

## Pré-requisitos

- Docker instalado e em execução.
- Docker Compose v2, disponível como `docker compose`.
- Python 3 para executar o orquestrador no computador host.
- Pacote Python `ruamel.yaml` no host:

```bash
python -m pip install ruamel.yaml
```

As dependências dos scripts de processamento estão listadas em `requirements.txt` e instaladas durante a construção da imagem Docker.

## Preparação dos dados

1. Clone ou copie o repositório e abra um terminal na pasta raiz.
2. Disponibilize os dados de entrada localmente, respeitando os caminhos definidos em `config.yaml`.
3. Revise a área, os anos e os parâmetros em `config.yaml` antes de iniciar.
4. Confira se os arquivos esperados para a área e os anos selecionados existem.

Os caminhos de entrada usam marcadores como `{AREA}` e `{YEAR}`. Por exemplo, para a área `PA` e o ano `2024`, o caminho configurado em `Paths.lulc_path` deve corresponder ao arquivo `inputs/mapbiomas_col10/mapbiomas_col10_PA_2024.tif`.

Os dados geoespaciais grandes não são distribuídos pelo repositório. A maior parte de `inputs/`, assim como `output/` e `tmp/`, é ignorada pelo Git; algumas planilhas de referência em `inputs/Planilhas/` são versionadas.

## Execução

### Pipeline usando a área definida em `config.yaml`

```bash
python Run_pipeline.py
```

Este orquestrador processa os anos base e final definidos pelos argumentos padrão no script e usa a área configurada em `config.yaml`.

### Pipeline com área e período informados na linha de comando

```bash
python Run_pipeline_area.py --base-year 2020 --end-year 2024 --area PA
```

Argumentos disponíveis:

| Argumento | Descrição | Padrão |
|---|---|---|
| `--base-year` | Ano-base da comparação | `2020` |
| `--end-year` | Ano final do processamento | `2024` |
| `--area` | Área ou estado a processar (somente `Run_pipeline_area.py`) | `PA` |
| `--rebuild` | Força a reconstrução da imagem Docker | Desativado |

Para forçar a reconstrução:

```bash
python Run_pipeline_area.py --area PA --rebuild
```

O orquestrador também reconstrói a imagem quando não encontra o registro local de build ou quando o conteúdo de `Dockerfile` ou `requirements.txt` mudou.

## Configuração

Edite `config.yaml` para ajustar os caminhos e parâmetros. Os campos mais usados são:

| Campo | Finalidade |
|---|---|
| `Paths.out_dir` | Diretório dos resultados |
| `Paths.tmp_path` | Diretório de arquivos temporários |
| `Paths.lulc_path` | Raster de uso e cobertura da terra; aceita `{AREA}` e `{YEAR}` |
| `Paths.shp_path` | Shapefile do estado ou área de análise |
| `Paths.shp_file` | Shapefile da área operacional (AOI) |
| `Data.area` | Área configurada |
| `Data.start_year` / `Data.end_year` | Período usado pelas etapas de processamento |
| `Data.base_year_compare` | Ano-base usado na comparação |

Os caminhos são interpretados a partir da raiz do repositório, que também é o diretório de trabalho dos containers.

## Etapas do pipeline

O fluxo automatizado é executado nesta ordem:

1. **Vegetação secundária** — `scripts/vegetation/veg_sec_weight.py`.
2. **Frequência de queimadas** — `scripts/burn/NPI_Burn_Freq_v3.py`.
3. **Condição de queimadas** — `scripts/burn/NPI_queimadas_Organizado_v3.py`.
4. **Condição de borda** — `scripts/edge/NPI_borda_Organizado_v5_clip.py`.
5. **Combinação das condições** — `scripts/weights/make_map_weights.py`.
6. **Comparação dos mapas** — `scripts/comparison/compare_maps_condicao_edt.py`.
7. **Tabelas GRI** — `scripts/gri/GRI_UPDATE.py`.

As etapas raster são orquestradas por `docker-compose_raster.yml`; a comparação e as tabelas, por `docker-compose_table.yml`. Cada etapa depende da conclusão bem-sucedida da anterior. Os diagramas estão em [docs/fluxograma/](docs/fluxograma/).

## Saídas e solução de problemas

- Resultados são gravados nos caminhos configurados em `config.yaml`, geralmente sob `output/`.
- Arquivos intermediários são gravados em `tmp/` e podem ser recriados pelo processamento.
- Se o Docker não estiver iniciado, inicie o serviço e tente novamente.
- Se uma etapa informar que não encontrou um arquivo, confirme o caminho correspondente em `config.yaml`, a área/ano usados e a disponibilidade dos dados.
- Em caso de falha durante o processamento, o orquestrador tenta restaurar o arquivo de configuração a partir do backup criado no início.
- Para ver a saída detalhada, acompanhe o terminal onde o orquestrador foi iniciado.
