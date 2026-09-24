# Pipeline GRI - Processamento de Condições

Este repositório contém scripts para executar o pipeline geoespacial de:
- análise de vegetação secundária,
- frequência de queimadas,
- condição de borda,
- e comparação de condições entre anos.

## Arquivos principais

- `Run_pipeline.py` : executa o pipeline para um ano base e um ano final, atualiza `config.yaml` e chama os serviços Docker necessários.
- `Run_pipeline_area.py` : mesma lógica de `Run_pipeline.py`, mas permite também definir a área/estado via `--area`.
- `config.yaml` : arquivo principal de configuração com caminhos de entrada/saída e parâmetros de processamento.
- `make_map_biotic_value.py` : gera os mapas de BV e BVfinal a partir da tabela externa de coeficientes.
- `docker-compose_raster.yml` : orquestra o processamento dos dados raster para cada ano.
- `docker-compose_table.yml` : executa a etapa de comparação entre o ano base e o ano final (Futuramente add Script do Matlab)

## Pré-requisitos

- Docker instalado e em execução.
- Docker Compose disponível como `docker compose`.
- Python 3.x para rodar o script de orquestração.
- Opcional: `ruamel.yaml` caso execute os scripts Python diretamente fora de Docker.

```bash
pip install ruamel.yaml
```

## Como usar

1. Abra o terminal na pasta do projeto.
2. Edite `config.yaml` se precisar adaptar caminhos de entrada/saída ou parâmetros.
3. Execute o pipeline padrão:

```bash
python Run_pipeline.py
```

4. Execute o pipeline com período e área personalizada:

```bash
python Run_pipeline_area.py --base-year 2020 --end-year 2024 --area PA
```

5. Para forçar a reconstrução da imagem Docker, adicione `--rebuild`:

```bash
python Run_pipeline_area.py --area PA --rebuild
```

## Parâmetros importantes em `config.yaml`

- `Paths.out_dir` : diretório de saída.
- `Paths.tmp_path` : diretório temporário.
- `Paths.lulc_path` : caminho do raster MapBiomas usando placeholders `{AREA}` e `{YEAR}`.
- `Paths.shp_path` / `Paths.shp_file` : shapefiles de estado e AOI.
- `Data.area` : estado de interesse (por exemplo, `PA`).
- `Data.start_year`, `Data.end_year` : período de análise.
- `Data.base_year_compare` : ano base para comparação.
- `Paths.biotic_value_table` : tabela `mapbiomas_id_bv.txt` com as colunas
  `id_class` e `bv` (tabulação ou outro separador detectável); as classes 60,
  61, 62 e 80 são ignoradas.
- `Paths.rad_shape_file` : único shape RAD (polígonos ou multipolígonos),
  reprojetado e rasterizado automaticamente no grid do MapBiomas. Seus pixels
  recebem BV `0.2083`.
- `Data.lulc_nodata_classes` : classes MapBiomas tratadas como sem dados
  (por padrão, `[0]`) e excluídas dos mapas de BV.
- `Data.biotic_value_scale` : fator aplicado aos valores da tabela antes da
  geração dos mapas. O padrão `100` converte a tabela `0–1` para a escala
  metodológica `0–100`; portanto, `BVfinal` permanece nessa mesma escala.
- `Data.secondary_vegetation_mask` : usa valores positivos do raster de
  vegetação secundária como máscara do BV. Esses pixels recebem o BV da classe
  configurada em `Data.secondary_vegetation_bv_class` (por padrão, classe `3`);
  a redução pela equação de Potter permanece aplicada no mapa de condição.

## Mapas de valor biótico

O estágio `npi_biotic_value` é executado depois do mapa de condição. Ele gera
`output/map_biotic_value_{AREA}_{YEAR}.tif` (BV sem condição) e
`output/map_biotic_value_final_{AREA}_{YEAR}.tif` (BV com condição). A condição
é convertida de 0–100 para 0–1. O estágio
falha explicitamente se faltar a tabela de BV, se houver classe MapBiomas sem
coeficiente ou se o raster RAD estiver desalinhado.

## Fluxo básico

1. O script faz backup de `config.yaml`.
2. Atualiza o ano em `config.yaml`.
3. Executa `docker-compose_raster.yml` para gerar mapas raster do ano base e do ano final.
4. Atualiza `config.yaml` com `base_year_compare` e executa `docker-compose_table.yml` para a comparação final.

## Observações

- O script `Run_pipeline_area.py` controla a reconstrução da imagem Docker automaticamente.
- Se o `Dockerfile` ou `requirements.txt` não mudarem, a imagem é reaproveitada.
- Se ocorrer erro em qualquer etapa, o backup de `config.yaml` é restaurado.

## Estrutura esperada de pastas

- `inputs/` : dados de entrada (MapBiomas, shapefiles, MODIS, etc.)
- `output/` : resultados gerados.
- `tmp/` : arquivos temporários.

---

Este README é uma síntese do funcionamento principal dos scripts e da configuração necessária para rodar o pipeline.
