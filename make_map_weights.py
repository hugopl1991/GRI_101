import sys
import os
import yaml
import pandas as pd
import numpy as np
import warnings

# Suprimir todos os warnings
warnings.filterwarnings("ignore")

from fuca.functions import *

def make_raster_from_matrix(band: np.ndarray, raster_std: str, nodata_value: int,
                            tmp_path: str, final_name: str,
                            descriptions: str, dtype: str = 'uint8') -> str:
  """
    Funcao que cria o raster final.
    
    Entrada:
        band: Matriz numpy de pixels.
        raster_std: Caminho do raster que sera usado como padrao.
        dtype: Tipo de dado do raster (e.g., 'uint8', 'float32').
        tmp_path: Caminho da pasta onde sera salvo o raster gerado.
        final_name: Nome final do arquivo raster a ser gerado.
        descriptions: String com descricao do raster que sera gerado.
        
    Saída:
        Retorna o caminho onde o raster gerado foi salvo.
  """ 
  with rasterio.open(raster_std) as dataset:
      profile = dataset.profile

      profile.update(
        dtype=dtype,
        count=1,
        compress='lzw',
        nodata = nodata_value)

      if final_name == None:
        system.exit("Erro: Necessario informar o nome final do raster.")
      else:
        final_name = tmp_path+final_name
  #Salva o raster que foi criado
      with rasterio.open(final_name, "w", **profile,) as dest:
          dest.set_band_description(1, descriptions)
          dest.write(band, indexes=1)
      dest.close()
  dataset.close()

  dataset = None
  dest = None

  return final_name

CONFIG_FILE = os.environ.get('CONFIG_FILE', 'config.yaml')
with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
PATHS, DATA = cfg['Paths'], cfg['Data']

area = DATA['area']
year = DATA['end_year']
id_class = DATA['id_class_cond']
all_touched = DATA['all_touched_cond']
nodata_cond = DATA['nodata_cond']    # Valor de no data para esse raster (Zero)
nodata_edge = DATA['nodata']         # Valor de nodata dos script Queimadas e Burn, não pode ser zero, Matriz do EDGE tem valores zeros.

out_path = PATHS['out_dir']
out_path = create_dir(out_path)

tmp_path = PATHS['tmp_path']
tmp_path = create_dir(tmp_path)

shp_file = PATHS['shp_file'].format(AREA=area)

sec_veg_weight = PATHS['sec_veg_weight_map_file'].format(AREA=area,YEAR=year) # Caminho para o arquivo raster de condição da vegetação segundaria
edge_weight_map_file = f"{out_path}/{(PATHS['out_cond_edge'].format(AREA=area,YEAR=year))}" # Caminho para o arquivo raster de condição de borda
fire_weight_map_file = f"{out_path}/{(PATHS['out_cond_burn'].format(AREA=area,YEAR=year))}" # Caminho para o arquivo raster de condição de queimadas

lulc_map_file = PATHS['lulc_path'].format(AREA=DATA['area'],YEAR=DATA['end_year']) # Caminho para o arquivo raster de uso e cobertura da terra (LULC)

# print(band_sec_veg_weight,nodata)
# print(type(band_sec_veg_weight[0][0]),type(nodata))

edge_weight = edge_weight_map_file.format(AREA=area,YEAR=year)

fire_weight = fire_weight_map_file.format(AREA=area,YEAR=year)

lulc_map = lulc_map_file.format(AREA=area,YEAR=year)

if shp_file is not None:
   sec_veg_weight = clip_raster(raster_path=sec_veg_weight,
                          shp_path=shp_file,
                          tmp_path=tmp_path,
                          all_touched=all_touched)
   
   edge_weight = clip_raster(raster_path=edge_weight,
                          shp_path=shp_file,
                          tmp_path=tmp_path,
                          all_touched=all_touched)
   
   fire_weight = clip_raster(raster_path=fire_weight,
                          shp_path=shp_file,
                          tmp_path=tmp_path,
                          all_touched=all_touched)
   
   lulc_map = clip_raster(raster_path=lulc_map,
                          shp_path=shp_file,
                          tmp_path=tmp_path,
                          all_touched=all_touched)


# === INÍCIO DO BLOCO SUBSTITUTO ===
band_sec_veg_weight, nd_sec = get_raster_band(sec_veg_weight)
band_edge_weight, nd_edge = get_raster_band(edge_weight)
band_fire_weight, nd_fire = get_raster_band(fire_weight)
band_lulc_map, nd_lulc = get_raster_band(lulc_map)

# Prevenção caso alguma banda venha sem Nodata no metadado (retorne None)
nd_edge = nd_edge if nd_edge is not None else nodata_edge
nd_fire = nd_fire if nd_fire is not None else nodata_edge

band_sec_veg_weight = band_sec_veg_weight.astype('int32')
band_edge_weight = band_edge_weight.astype('int32')
band_fire_weight = band_fire_weight.astype('int32')

mask1 = (band_sec_veg_weight == nd_sec) & np.isin(band_lulc_map, id_class)
mask_zero = (band_sec_veg_weight == nd_sec) & ~np.isin(band_lulc_map, id_class)

sec_veg_weight_masked = band_sec_veg_weight.copy()
sec_veg_weight_masked[mask1] = 100
sec_veg_weight_masked[mask_zero] = 1

# Máscara de Fundo (usa os metadados lidos dinamicamente)
mask_fundo = (band_edge_weight == nd_edge) | (band_fire_weight == nd_fire) | (band_lulc_map == nd_lulc)

# Multiplicação
weights_result = sec_veg_weight_masked * band_edge_weight * band_fire_weight

del mask1, mask_zero, sec_veg_weight_masked, band_edge_weight, band_fire_weight

# =================================================================
# RASTER 1: "Milhão" (Valores válidos de 0 a 1.000.000)
# =================================================================
final_weight_milhao = weights_result.astype('int32')
final_weight_milhao[mask_fundo] = nodata_cond 

make_raster_from_matrix(band=final_weight_milhao,
                        raster_std=sec_veg_weight,
                        nodata_value = nodata_cond,
                        tmp_path= out_path,
                        final_name = f"map_weights_milhao_{year}.tif",
                        descriptions = 'Raster de pesos de Veg Sec, Borda e Queimadas',
                        dtype = 'int32') 

# =================================================================
# RASTER 2: "100" (Valores válidos de 0 a 100)
# =================================================================
final_weight_100 = (weights_result / 10000).astype('uint8')
final_weight_100[mask_fundo] = nodata_cond 

make_raster_from_matrix(band=final_weight_100,
                        raster_std=sec_veg_weight,
                        nodata_value = nodata_cond,
                        tmp_path= out_path,
                        final_name = f"map_weights_100_{year}.tif",
                        descriptions = 'Raster de pesos de Veg Sec, Borda e Queimadas',
                        dtype = 'uint8')

print("\n[OK] Condicao ecossistema concluida!")