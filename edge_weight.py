import math, os, yaml, multiprocessing, concurrent.futures
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import Window
from scipy.ndimage import distance_transform_edt
from utils import calcular_tile_size_dinamico, remove_if_exists, clipar_por_shapefile

with open('config.yaml', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
PATHS, DATA = cfg['Paths'], cfg['Data']

WORKERS = max(1, multiprocessing.cpu_count() - 1)
LULC = PATHS['lulc_path'].format(AREA=DATA['area'],YEAR=DATA['end_year']) # Caminho para o raster mapbiomas
SHP_PATH = PATHS['shp_path'].format(AREA=DATA['area'])  # Caminho para o shapefile para recortar dado do estado em interesse.
OUT_COND = f"{PATHS['out_dir']}/{PATHS['out_cond_edge'].format(AREA=DATA['area'],YEAR=DATA['end_year'])}"
MASK_TEMP = f"{PATHS['mask_temp']}" # Caminho para o arquivo raster temporário de máscara do shapefile
SHP_FILE = PATHS['shp_file'].format(AREA=DATA['area']) # Caminho para o arquivo shapefile da AREA OPERACIONAL
OUT_CLIP = f"{PATHS['out_dir']}/{PATHS['out_clip_edge'].format(AREA=DATA['area'],YEAR=DATA['end_year'])}" # Caminho para o arquivo raster de condição de borda recortado pelo shapefile

# Constantes matematicas da condicao de borda
if DATA['funcao'] == "linear":
    CONST_DIST = ((DATA['dist_max_pixel'] - DATA['cond_borda']) / DATA['dist_max_metros']) * DATA['size_pixel']
else:
    amp = DATA['dist_max_pixel'] - DATA['cond_borda']
    k = -np.log(0.5 / amp) / (DATA['dist_max_metros'] / DATA['size_pixel'])

def _worker_processa_tile(args_extracao):
    """
    Funcao que processa um tile individual, calculando a condicao de borda
    a partir da distancia as areas naturais (com sobreposicao entre tiles).
    Entrada:
        args_extracao: Dicionário contendo a linha, coluna, tamanho do tile, etc.
    Saida:
        Retorna uma tupla (cond, write_win) onde cond e a matriz numpy com a
        condicao de borda calculada (ja sem a margem de sobreposicao) e write_win
        e a Window de escrita correspondente no raster de saida.
    """
    row = args_extracao["row"]
    col = args_extracao["col"]
    t_size = args_extracao["t_size"]
    n_rows = args_extracao["n_rows"]
    n_cols = args_extracao["n_cols"]
    
    ovlap = DATA['overlap']
    
    r_start, c_start = max(0, row * t_size - ovlap), max(0, col * t_size - ovlap)
    
    with rasterio.open(LULC) as src, rasterio.open(MASK_TEMP) as m_src:
        r_end, c_end = min(src.height, (row + 1) * t_size + ovlap), min(src.width, (col + 1) * t_size + ovlap)
        read_win = Window(c_start, r_start, c_end - c_start, r_end - r_start)
        
        tile_data = src.read(1, window=read_win)
        valido = m_src.read(1, window=read_win) == 1
    
    natural = valido & np.isin(tile_data, DATA['classes_naturais'])
    natural_edt = np.where(valido, natural, 1).astype(np.uint8)
    
    dist_pixels = np.where(natural, np.floor(distance_transform_edt(natural_edt) + 0.5).astype(np.int16), 0)

    if DATA['funcao'] == "linear":
        cond = np.floor(CONST_DIST * dist_pixels + DATA['cond_borda'] + 0.5).astype(np.int16)
    else:
        cond = np.floor(DATA['dist_max_pixel'] - amp * np.exp(-k * dist_pixels) + 0.5).astype(np.int16)

    cond = np.clip(cond, DATA['cond_borda'], DATA['dist_max_pixel'])
    cond[~natural], cond[~valido] = 0, DATA['nodata']

    # Recorte da margem de sobreposicao (usando n_rows e n_cols diretamente)
    ir_start = ovlap if row > 0 else 0
    ir_end = cond.shape[0] - (ovlap if row < n_rows - 1 else 0)
    ic_start = ovlap if col > 0 else 0
    ic_end = cond.shape[1] - (ovlap if col < n_cols - 1 else 0)
    
    write_win = Window(col * t_size, row * t_size, ic_end - ic_start, ir_end - ir_start)
    return cond[ir_start:ir_end, ic_start:ic_end], write_win

def gerar_mapa_condicao(t_size):
    """
    Funcao que gera o mapa de condicao de borda em paralelo, tile a tile,
    a partir do raster de uso e cobertura do solo (LULC) e do shapefile de area.
    Entrada:
        t_size: Tamanho do tile utilizado para dividir o processamento.
    Saida:
        Nenhum retorno (None); o raster de condicao e salvo em OUT_COND.
    """
    print(f"\n[1/2] Gerando mapa de condicao (Workers: {WORKERS})...")
    os.makedirs(PATHS['out_dir'], exist_ok=True) # Garante que a pasta 'output' exista
    os.makedirs(os.path.dirname(MASK_TEMP), exist_ok=True) # Garante que a pasta 'tmp' exista
    remove_if_exists(MASK_TEMP)
    
    with rasterio.open(LULC) as src:
        prof, shape = src.profile.copy(), (src.height, src.width)
        gdf = gpd.read_file(SHP_PATH).to_crs(src.crs)
        fora = geometry_mask([g.__geo_interface__ for g in gdf.geometry if g], transform=src.transform, out_shape=shape)
        prof.update(dtype="uint8", count=1, nodata=None, compress=DATA['compresssion'], tiled=DATA['tiled'], blockxsize=DATA['blocksize'], blockysize=DATA['blocksize'])
        with rasterio.open(MASK_TEMP, "w", **prof) as dst: dst.write((~fora).astype(np.uint8), 1)
    
    prof.update(dtype="int16", nodata=DATA['nodata'])
    n_rows, n_cols = math.ceil(shape[0] / t_size), math.ceil(shape[1] / t_size)
    
    # Empacotando os argumentos
    args_extracao = [{
        "row": r,
        "col": c,
        "t_size": t_size,
        "n_rows": n_rows,
        "n_cols": n_cols
    } for r in range(n_rows) for c in range(n_cols)]

    with rasterio.open(OUT_COND, "w", **prof) as dst, concurrent.futures.ProcessPoolExecutor(WORKERS) as exc:
        for fut in concurrent.futures.as_completed({exc.submit(_worker_processa_tile, t): t for t in args_extracao}):
            cond, win = fut.result()
            dst.write(cond, 1, window=win)
    
    remove_if_exists(MASK_TEMP)

if __name__ == "__main__":
    t_size = calcular_tile_size_dinamico(DATA['max_ram_usage'], WORKERS, DATA['byte_pixel'], DATA['blocksize'], DATA['tile_size_min'])
    gerar_mapa_condicao(t_size)
    #clipar_por_shapefile(OUT_COND, SHP_FILE, OUT_CLIP, t_size, DATA)
    print("\n[OK] Borda concluida!")