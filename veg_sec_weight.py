import sys
import yaml
import pandas as pd
import numpy as np
import warnings
import os

# Suprimir todos os warnings
warnings.filterwarnings("ignore")

from fuca.functions import *

def make_raster_from_matrix(band: np.ndarray, raster_std: str,
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
        nodata = 0)

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
base_year = DATA['base_year_veg']
end_year = DATA['end_year']
id_class = DATA['id_class_veg']
all_touched = DATA['all_touched_veg']

out_path = PATHS['out_dir']
out_path = create_dir(out_path)

tmp_path = PATHS['tmp_path']
tmp_path = create_dir(tmp_path)

sec_veg_file = PATHS['sec_veg_map_file']
shp_file = PATHS['shp_file'].format(AREA=area)

sec_veg_end = sec_veg_file.format(AREA=area,YEAR=end_year)

if shp_file is not None:
   sec_veg_end = clip_raster(raster_path=sec_veg_end,
                          shp_path=shp_file,
                          tmp_path=tmp_path,
                          all_touched=all_touched)


band_sec_veg_end, _ = get_raster_band(sec_veg_end)

# valores, contagens = np.unique(band_sec_veg_end, return_counts=True)

# for valor, contagem in zip(valores, contagens):
#     print(f"Elemento {valor} aparece {contagem} vezes")

matrix = band_sec_veg_end.copy()

# Aplica a fórmula apenas nos elementos diferentes de zero
matrix[band_sec_veg_end != 0] = (1 - np.exp(-0.038 * band_sec_veg_end[band_sec_veg_end != 0]))*100


# Seleciona 100 elementos aleatórios
elementos_aleatorios = np.random.choice(matrix.flatten(), size=1000, replace=False)

#print("100 elementos aleatorios:")
#print(elementos_aleatorios)

make_raster_from_matrix(band=matrix,
                        raster_std=sec_veg_end,
                        tmp_path= out_path,
                        final_name = f"veg_sec_weight_{area}_{end_year}.tif",
                        descriptions = 'Raster de pesos de Veg Sec',
                        dtype = 'uint8')

print("\n[OK] Vegetacao segundaria concluida!")
