import os, yaml, multiprocessing, concurrent.futures
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import Resampling, reproject
from rasterio.windows import Window
from utils import calcular_tile_size_dinamico, remove_if_exists, clipar_por_shapefile

CONFIG_FILE = os.environ.get('CONFIG_FILE', 'config.yaml')
with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
PATHS, DATA = cfg['Paths'], cfg['Data']

WORKERS = max(1, multiprocessing.cpu_count() - 1)
LULC = PATHS['lulc_path'].format(AREA=DATA['area'],YEAR=DATA['end_year']) # Caminho para o raster mapbiomas
BURN_FREQ = f"{PATHS['out_dir']}/{PATHS['out_burn'].format(SYERAR=DATA['start_year'],EYERAR=DATA['end_year'])}" # Caminho para o raster de frenquancia de queimdas  
OUT_REPROJ = f"{PATHS['out_reproj']}" # Caminho para o arquivo raster reprojetado (temporário)
OUT_COND = f"{PATHS['out_dir']}/{PATHS['out_cond_burn'].format(AREA=DATA['area'],YEAR=DATA['end_year'])}" # Caminho para o arquivo raster de condição de queimadas
SHP_FILE = PATHS['shp_file'].format(AREA=DATA['area']) # Caminho para o arquivo shapefile da AREA OPERACIONAL
OUT_CLIP = f"{PATHS['out_dir']}/{PATHS['out_clip_burn'].format(AREA=DATA['area'],YEAR=DATA['end_year'])}" #  Caminho para o arquivo raster de condição de queimadas recortado pelo shapefile

df_regras = pd.read_csv(PATHS['tabela_csv']) # Caminho para o arquivo CSV contendo a tabela de classes de condição de queimadas
CLASS_MIN, CLASS_MAX = df_regras['Class'].min(), df_regras['Class'].max()
MAPA_COND = df_regras['Cond'].to_numpy(dtype=np.int16)

def reprojetar_modis():
    """
    Funcao que reprojeta o raster MODIS de queimadas para a mesma grade
    (transform/CRS) do raster de referencia (LULC).
    Entrada:
        Nenhum parametro; utiliza as variaveis globais CG e CQ (config.yaml).
    Saida:
        Nenhum retorno (None); o raster reprojetado e salvo em OUT_REPROJ.
    """
    print("\n[1/3] Reprojetando MODIS...")
    os.makedirs(PATHS['out_dir'], exist_ok=True) # Garante que a pasta 'output' exista
    os.makedirs(os.path.dirname(OUT_REPROJ), exist_ok=True) # Garante que a pasta 'tmp' exista
    with rasterio.open(LULC) as ref, rasterio.open(BURN_FREQ) as src:
        prof = ref.profile.copy()
        prof.update(dtype="int16", nodata=DATA['nodata'], compress=DATA['compresssion'], tiled=DATA['tiled'], blockxsize=DATA['blocksize'], blockysize=DATA['blocksize'])
        remove_if_exists(OUT_REPROJ)
        
        with rasterio.open(OUT_REPROJ, "w", **prof) as dst:
            reproject(source=rasterio.band(src, 1), destination=rasterio.band(dst, 1), 
                      src_transform=src.transform, src_crs=src.crs, dst_transform=ref.transform, dst_crs=ref.crs, resampling=Resampling.nearest)

def _process_win(args_extracao):
    """
    Funcao que processa uma janela (window) do raster, aplicando a tabela
    de regras (Class -> Cond) sobre os dados de queimadas reprojetados.
    Entrada:
        args_extracao: Dicionario contendo a Window (rasterio) delimitando a regiao.
    Saida:
        Retorna uma tupla (win, cond) onde win e a mesma Window de entrada e
        cond e a matriz numpy com a condicao calculada para essa janela.
    """
    win = args_extracao["win"]
    with rasterio.open(OUT_REPROJ) as brn, rasterio.open(LULC) as lulc:
        b_tile, l_tile = brn.read(1, window=win), lulc.read(1, window=win)
        cond = MAPA_COND[np.clip(b_tile, CLASS_MIN, CLASS_MAX)]
        cond[(l_tile == lulc.nodata) | (b_tile == DATA['nodata'])] = DATA['nodata']
        return win, cond

def gerar_mapa_condicao(t_size):
    """
    Funcao que gera o mapa de condicao de queimadas em paralelo, por janelas,
    aplicando a tabela de regras sobre o raster MODIS reprojetado.
    Entrada:
        t_size: Tamanho do tile/janela utilizado para dividir o processamento.
    Saida:
        Nenhum retorno (None); o raster de condicao e salvo em OUT_COND.
    """
    print(f"\n[2/3] Gerando mapa (Workers: {WORKERS})...")
    with rasterio.open(LULC) as ref:
        prof, h, w = ref.profile.copy(), ref.height, ref.width
    
    prof.update(dtype="int16", nodata=DATA['nodata'], compress=DATA['compresssion'], tiled=DATA['tiled'], blockxsize=DATA['blocksize'], blockysize=DATA['blocksize'])
    
    # Empacotando os argumentos
    args_extracao = [{"win": Window(c, r, min(w, c + t_size) - c, min(h, r + t_size) - r)} 
                     for r in range(0, h, t_size) for c in range(0, w, t_size)]
    
    remove_if_exists(OUT_COND)
    with rasterio.open(OUT_COND, "w", **prof) as dst, concurrent.futures.ThreadPoolExecutor(WORKERS) as exc:
        for fut in concurrent.futures.as_completed({exc.submit(_process_win, arg): arg for arg in args_extracao}):
            win, cond = fut.result()
            dst.write(cond, 1, window=win)

if __name__ == "__main__":
    t_size = calcular_tile_size_dinamico(DATA['max_ram_usage'], WORKERS, DATA['byte_pixel'], DATA['blocksize'], DATA['tile_size_min'])
    reprojetar_modis()
    gerar_mapa_condicao(t_size)
    remove_if_exists(OUT_REPROJ)
    #clipar_por_shapefile(OUT_COND, SHP_FILE, OUT_CLIP, t_size, DATA)
    print("\n[OK] Queimadas concluida!")