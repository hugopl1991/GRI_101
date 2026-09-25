import os, yaml
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.mask import mask as rio_mask
from rasterio.features import geometry_mask
from pathlib import Path

with open('config.yaml', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
PATHS, DATA = cfg['Paths'], cfg['Data']

OUT_BURN = (PATHS['out_burn'].format(SYERAR=DATA['start_year'],EYERAR=DATA['end_year'])) # Caminho para o arquivo de queimadas.
SHP_PATH = (PATHS['shp_path'].format(AREA=DATA['area']))  # Caminho para o shapefile para recortar dado do estado em interesse.

def processar_frequencia():
    """
    Funcao que calcula a frequencia de queimadas (numero de meses/anos com
    ocorrencia) a partir da serie temporal de rasters MODIS, recortada pela
    geometria do shapefile de area.
    Entrada:
        Nenhum parametro; utiliza as variaveis (config.yaml).
    Saida:
        Nenhum retorno (None); o raster de frequencia e salvo em out_file.
    """
    out_file = os.path.join(PATHS['out_dir'], (OUT_BURN))
    os.makedirs(PATHS['out_dir'], exist_ok=True)
    
    # Listagem concisa via Path.glob iterando os anos
    tifs = [p for y in range(DATA['start_year'], DATA['end_year'] + 1) 
            if (Path(PATHS['in_dir']) / str(y)).exists() 
            for p in sorted((Path(PATHS['in_dir']) / str(y)).glob(PATHS['raster_modis']))]
    
    if not tifs: raise FileNotFoundError("Nenhum raster MODIS encontrado.")

    print("\nCarregando Geometrias...")
    gdf = gpd.read_file(SHP_PATH).to_crs(DATA['crs_corr'])
    geoms = [g.__geo_interface__ for g in gdf.geometry.simplify(DATA['tolerance'])]
    
    freq, profile, g_mask = None, None, None
    
    print("\nAnalisando Frequencia (Anos)...")
    for tif in tifs:
        with rasterio.open(tif) as src:
            src_nd = src.nodata if src.nodata is not None else -1
            try: 
                data, trans = rio_mask(src, geoms, crop=True, nodata=src_nd, all_touched=DATA['all_touched'])
            except ValueError: 
                continue
            
            # Inicializacao e extracao de metadados na primeira passagem valida
            if freq is None:
                freq = np.zeros((data.shape[1], data.shape[2]), dtype=np.int16)
                profile = src.profile.copy()
                profile.update(driver="GTiff", dtype="int16", height=data.shape[1], width=data.shape[2], 
                               transform=trans, nodata=DATA['nodata'], compress=DATA['compresssion'])
                
                g_mask = geometry_mask(geoms, out_shape=freq.shape, transform=trans, invert=True, all_touched=DATA['all_touched'])

            # Atualiza apenas onde for queima valida (maior que 0 e ignorando valores fora do shape)
            freq += np.where(g_mask & (data[0] != src_nd) & (data[0] > 0), 1, 0).astype(np.int16)

    if freq is None: raise RuntimeError("Erro processual: nenhuma area valida interceptada.")
    
    # Aplica a marcacao de NODATA no final para regioes externas a geometria
    freq[~g_mask] = DATA['nodata']
    profile.update({"count": 1})
    
    with rasterio.open(out_file, "w", **profile) as dst:
        dst.write(freq, 1)
    
    validos = freq[freq != DATA['nodata']]
    print(f"\n[OK] Salvo: {out_file} | Range de Queima (meses): {validos.min()} a {validos.max()}")

if __name__ == "__main__":
    processar_frequencia()