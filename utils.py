import os
import math
import gc
import psutil
import numpy as np
import geopandas as gpd
import rasterio
import rasterio.windows
from rasterio.features import geometry_mask

def remove_if_exists(path):
    """
    Funcao que remove um arquivo se ele existir.
    Entrada:
        path: Caminho do arquivo a ser removido.
    Saida:
        Nenhum retorno (None).
    """
    if os.path.exists(path):
        try: os.remove(path)
        except OSError: pass

def calcular_tile_size_dinamico(max_ram, workers, bytes_px, blocksize, tile_min):
    """
    Funcao que calcula o tamanho do tile dinamicamente baseado na memoria RAM livre.
    Entrada:
        max_ram: Fracao da RAM livre que pode ser utilizada (e.g., 0.5 para 50%).
        workers: Numero de processos/threads que serao executados em paralelo.
        bytes_px: Numero de bytes ocupados por pixel no raster.
        blocksize: Tamanho do bloco (blockxsize/blockysize) do raster.
        tile_min: Tamanho maximo de tile permitido (limite superior).
    Saida:
        Retorna o tamanho do tile (int) ajustado conforme a RAM disponivel.
    """
    ram_livre = psutil.virtual_memory().available
    pixels_max = ((ram_livre * max_ram) / workers) / bytes_px
    
    tile_size = max(blocksize, (int(math.sqrt(pixels_max)) // blocksize) * blocksize)
    tile_final = min(tile_min, tile_size)
    
    print(f"\n[INFO] RAM Livre: {ram_livre / (1024**3):.1f} GB | Tile ajustado: {tile_final}x{tile_final}")
    return tile_final

def clipar_por_shapefile(in_raster, shp_path, out_clip, tile_size, cfg_global):
    """
    Funcao que recorta o raster, por tiles, usando a geometria do shapefile.
    Entrada:
        in_raster: Caminho do raster de entrada a ser recortado.
        shp_path: Caminho do shapefile usado como mascara de recorte.
        out_clip: Caminho onde o raster recortado sera salvo.
        tile_size: Tamanho do tile usado para processar o recorte em blocos.
        cfg_global: Dicionario com as configuracoes globais (nodata, compressao, etc.).
    Saida:
        Nenhum retorno (None); o raster recortado e salvo em out_clip.
    """
    print(f"\nRecortando pelo shapefile: {shp_path}...")
    gdf = gpd.read_file(shp_path)
    
    with rasterio.open(in_raster) as src:
        gdf = gdf.to_crs(src.crs)
        geoms = list(gdf.geometry)
        minx, miny, maxx, maxy = gdf.total_bounds
        del gdf; gc.collect()

        rmin, cmin = rasterio.transform.rowcol(src.transform, minx, maxy)
        rmax, cmax = rasterio.transform.rowcol(src.transform, maxx, miny)
        rmin, cmin = max(0, rmin), max(0, cmin)
        rmax, cmax = min(src.height, rmax + 1), min(src.width, cmax + 1)
        
        clip_h, clip_w = rmax - rmin, cmax - cmin
        clip_win = rasterio.windows.Window(cmin, rmin, clip_w, clip_h)
        
        meta = src.meta.copy()
        meta.update({
            "height": clip_h, "width": clip_w,
            "transform": rasterio.windows.transform(clip_win, src.transform),
            "nodata": cfg_global['nodata'], "compress": cfg_global['compresssion'],
            "tiled": cfg_global['tiled'], "blockxsize": cfg_global['blocksize'],
            "blockysize": cfg_global['blocksize']
        })

        remove_if_exists(out_clip)
        n_rows, n_cols = math.ceil(clip_h / tile_size), math.ceil(clip_w / tile_size)

        with rasterio.open(out_clip, "w", **meta) as dst:
            for row in range(n_rows):
                for col in range(n_cols):
                    t_col, t_row = col * tile_size, row * tile_size
                    t_w, t_h = min(clip_w, t_col + tile_size) - t_col, min(clip_h, t_row + tile_size) - t_row
                    
                    src_win = rasterio.windows.Window(cmin + t_col, rmin + t_row, t_w, t_h)
                    dst_win = rasterio.windows.Window(t_col, t_row, t_w, t_h)
                    
                    tile_data = src.read(1, window=src_win)
                    t_transform = rasterio.windows.transform(src_win, src.transform)
                    mask = geometry_mask(geoms, transform=t_transform, invert=True, out_shape=(t_h, t_w))
                    
                    tile_data[~mask] = cfg_global['nodata']
                    dst.write(tile_data.astype(np.int16), 1, window=dst_win)
    print("  [OK] Raster recortado e salvo.")