import sys
import yaml
import pandas as pd
import numpy as np
import rasterio.features
from shapely.geometry import shape, box
import warnings

# Suprimir todos os warnings
warnings.filterwarnings("ignore")

from fuca.functions import *
from fuca.opunit_functions import *

def obtem_legendas(nome_arquivo):
    """
    Obtem as legendas do arquivo de legenda
    """
    df = pd.read_excel(nome_arquivo, sheet_name='LULC', index_col = 0)
    dict_lulc = df['Legenda'].transpose().to_dict()

    df = pd.read_excel(nome_arquivo, sheet_name='IBGE', index_col = 0)
    dict_ibge = df['Legenda'].transpose().to_dict()

    df = pd.read_excel(nome_arquivo, sheet_name='Queimada', index_col = 0)
    dict_fire = df['Legenda'].transpose().to_dict()

    df = pd.read_excel(nome_arquivo, sheet_name='Borda', index_col = 0)
    dict_edge = df['Legenda'].transpose().to_dict()

    df = pd.read_excel(nome_arquivo, sheet_name='Condicao', index_col = 0)
    dict_condicao = df['Legenda'].transpose().to_dict()

    return dict_lulc, dict_ibge, dict_fire, dict_edge, dict_condicao

def read_dissolve_shp(shp_path: str):
    """
      Funcao que le o shapefile e dissolve todas as geometrias em uma unica.
      
      Entrada:
          shp_path: Caminho do shapefile.
          
      Saída:
          Retorna a geometria unificada do shapefile.
    """
    gdf = gpd.read_file(shp_path)
    gdf_unificado = gdf.dissolve()
    return gdf_unificado.geometry[0]

def add_pixel_dict(dict_tmp, class_id, pixel):
    if class_id in dict_tmp:
        dict_tmp[class_id].append(pixel)
    else:
        dict_tmp[class_id] = []
        dict_tmp[class_id].append(pixel)

def print_total_pixels(dict_tmp):
    for class_id in dict_tmp:
        print(f"{class_id}: {len(dict_tmp[class_id])}")
    print()

def fractional_pixel_weights_optimized(raster_path: str, geom: Any) -> np.ndarray:
    """
    Funcao otimizada que calcula a fracao de area de um shapefile
    que intersecta com cada pixel de um raster.

    A abordagem é vetorizada, sem loops explícitos.
    
    Entrada:
        raster_path: String contendo o caminho do arquivo raster.
        geom: Objeto do tipo geometry que representa o shapefile.
    
    Saída:
        frac_intersected: Array numpy contendo o percentual de area coberta por pixel.
    """
    
    geom = shape(geom)
    
    with rasterio.open(raster_path) as src:
        # 1. Crie uma máscara (array booleano) com a geometria rasterizada
        # A geometria é 'queimada' no raster, gerando um array de True/False
        # onde True indica a área do shapefile.
        mask = rasterio.features.geometry_mask([geom],
                                               out_shape=(src.height, src.width),
                                               transform=src.transform,
                                               all_touched=True)
        
        # 2. Crie um array de zeros para armazenar os pesos
        weights = np.zeros(src.shape, dtype=np.float32)

        # 3. Use uma abordagem de intersecção mais eficiente
        # Crie a geometria de um polígono para a extensão do raster
        raster_geom = box(src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)

        # Calcule a interseção da geometria do shapefile com a extensão do raster
        # Isso é uma otimização para não processar pixels fora do raster
        geom_intersected_raster = geom.intersection(raster_geom)
        
        # O gerador rasteriza a geometria, calculando a área fracionária de cada pixel
        # que intersecta a geometria.
        frac_generator = rasterio.features.rasterize([geom_intersected_raster],
                                                     out_shape=(src.height, src.width),
                                                     transform=src.transform,
                                                     fill=0,
                                                     all_touched=True,
                                                     dtype=np.float32)

        # 4. Use a máscara e o gerador de frações para obter o resultado final
        # O gerador retorna os pesos para todos os pixels do raster de uma vez
        weights = frac_generator
        
    return weights

with open('config.yaml', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
PATHS, DATA = cfg['Paths'], cfg['Data']

area = DATA['area']
base_year = DATA['base_year_compare']
end_year = DATA['end_year']
id_class = DATA['id_class_compare']
all_touched = DATA['all_touched_compare']
n_condition_classes = DATA['n_condition_classes']

fito_file = PATHS['fito_map_file']
lulc_file = PATHS['lulc_path']
# sec_veg_file = config['Paths']['sec_veg_map_file']
bioma_file = PATHS['bioma_map_file']
area_file = PATHS['area_map_file']
state_shape_file = PATHS['shp_path'].format(AREA=area)

# edge_map_file = config['Paths']['edge_map_file']
# fire_map_file = config['Paths']['fire_map_file']
condition_map_file_base = PATHS['condition_map_file_base']
condition_map_file_end = PATHS['condition_map_file_end'].format(AREA=area,END_YEAR=end_year)

opunit_id_map_file = PATHS['opunit_id_map_file'].format(AREA=area)

#Arquivo csv contendo os IDs de Opunit
opunit_id_csv_file = PATHS['opunit_id_csv_file']
opunit_metadata_file = PATHS['opunit_metadata_file']
legendas_file = PATHS['legendas_file']

shp_file = PATHS['shp_file'].format(AREA=area,YEAR=end_year)

tmp_path = PATHS['tmp_path']
out_path = PATHS['out_dir']

tmp_path = create_dir(tmp_path)
out_path = create_dir(out_path)

uni_op = get_Opunit_id(opunit_file=opunit_id_csv_file)
dict_opunit_metadata = get_Opunit_metadata(opunit_metadata_file)

dict_lulc, dict_ibge, dict_fire, dict_edge, dict_condicao = obtem_legendas(legendas_file)

if n_condition_classes != len(dict_condicao):
    print(f'Numero de classes de condicao ({n_condition_classes}) diferente do numero de classes na legenda (criando legenda artificialmente)')
    dict_condicao = { i+1: f'Condicao {(i)*20}%-{(i+1)*20}%' for i in range(n_condition_classes) }

#Recorta mapa base de LULC
lulc_base = lulc_file.format(AREA=area,YEAR=base_year)
raster_lulc_base = clip_raster(raster_path=lulc_base,
                          shp_path=shp_file,
                          tmp_path=tmp_path,
                          all_touched=all_touched)

#Recorta mapa final de LULC
lulc_end = lulc_file.format(AREA=area,YEAR=end_year)
raster_lulc_end = clip_raster(raster_path=lulc_end,
                          shp_path=shp_file,
                          tmp_path=tmp_path,
                          all_touched=all_touched)

#Recorta mapa de area
area_raster = area_file.format(AREA=area)
area_raster = clip_raster(raster_path=area_raster,
                          shp_path=shp_file,
                          tmp_path=tmp_path,
                          all_touched=all_touched)

# #Recorta mapa de Veg Sec
# sec_veg_end = sec_veg_file.format(AREA=area,YEAR=end_year)
# sec_veg_end = clip_raster(raster_path=sec_veg_end,
#                           shp_path=shp_file,
#                           tmp_path=tmp_path,
#                           all_touched=all_touched)

#Recorta mapa de condicao
condition_map_file_base = condition_map_file_base.format(AREA=area,BASE_YEAR=base_year)
condition_map_file_base = clip_raster(raster_path=condition_map_file_base,
                          shp_path=shp_file,
                          tmp_path=tmp_path,
                          all_touched=all_touched)

condition_map_file_end = condition_map_file_end.format(AREA=area,END_YEAR=end_year)
condition_map_file_end = clip_raster(raster_path=condition_map_file_end,
                          shp_path=shp_file,
                          tmp_path=tmp_path,
                          all_touched=all_touched)

# #Recorta mapa de pixels de borda
# edge_map_file = edge_map_file.format(AREA=area,YEAR=end_year)
# edge_map_file = clip_raster(raster_path=edge_map_file,
#                           shp_path=shp_file,
#                           tmp_path=tmp_path,
#                           all_touched=all_touched)

# #Recorta mapa de historico de queimadas
# fire_map_file = fire_map_file.format(AREA=area,YEAR=end_year)
# fire_map_file = clip_raster(raster_path=fire_map_file,
#                           shp_path=shp_file,
#                           tmp_path=tmp_path,
#                           all_touched=all_touched)

#Recorta mapa de Unidades Operacionais
opunit_id_map_file = opunit_id_map_file.format(AREA=area,YEAR=end_year)
opunit_id_map_file = clip_raster(raster_path=opunit_id_map_file,
                          shp_path=shp_file,
                          tmp_path=tmp_path,
                          all_touched=all_touched)

#recorta shape do ibge com o estado
path_shape_fito = clip_shp_w_shp(shp_t_clip=fito_file,cut_shp=state_shape_file,tmp_path=tmp_path)
#acessa o ibge e retorna a lista de shapes
shapes_raster = get_ibge_shapes(ibge_shp=path_shape_fito)
#cria o raster com a lista de shapes
ibge_raster = shapes_t_raster(shapes_raster=shapes_raster,
                              raster_std=raster_lulc_base,
                              tmp_path=tmp_path,
                              nodata=None,
                              dtype=None,
                              name='fito')
#recorta o raster do ibge
ibge_raster = clip_raster(raster_path=ibge_raster,
                          shp_path=shp_file,
                          tmp_path=tmp_path,
                          all_touched=all_touched)

#Usa o mapa base como matriz original de pixels
_, _, list_indices = access_raster(raster_lulc_end,True)
band_lulc_base, _ = get_raster_band(raster_lulc_base)
band_lulc_end, _ = get_raster_band(raster_lulc_end)
# band_sec_veg_end, _ = get_raster_band(sec_veg_end)
band_ibge_raster, _ = get_raster_band(ibge_raster)
band_area_raster, _ = get_raster_band(area_raster)
band_condition_map_base, nodata_condition_base = get_raster_band(condition_map_file_base)
band_condition_map_end, nodata_condition_end = get_raster_band(condition_map_file_end)
# band_edge_map, nodata_edge = get_raster_band(edge_map_file)
# band_fire_map, nodata_fire = get_raster_band(fire_map_file)
band_opunit_id_map, _ = get_raster_band(opunit_id_map_file)

#Converte o mapa de condicao para classes
bins = [(i+1)*20+0.1 for i in range(n_condition_classes)]
band_condition_map_base = np.digitize(band_condition_map_base, bins, right=True) + 1
band_condition_map_end = np.digitize(band_condition_map_end, bins, right=True) + 1

#print(nodata_edge,nodata_fire)
print(len(list_indices))

# Calcula a area total de cobertura %

geom = read_dissolve_shp(shp_file)

# band_perc = fractional_pixel_weights(raster_lulc_end, geom, list_indices)
band_perc = fractional_pixel_weights_optimized(raster_lulc_end, geom)

band_perc_area = (band_perc * band_area_raster).astype(np.float32)

# Mascara com os pixels validos (LULC final != 0) -- usada para filtrar
# TUDO antes de montar o DataFrame, em vez de processar o raster inteiro.
mask_validos = band_lulc_end != 0

soma_total_area = float(band_perc_area[mask_validos].sum())
print(f'Soma total de area: {soma_total_area}')

# df = pd.DataFrame(columns=[#f'LULC_{base_year}',
#                            f'LULC_{end_year}',
#                            'Sec_Veg',
#                            'IBGE',
#                            'Classe_Borda',
#                            'Classe_Queimada',
#                            'Qtd_pixels',
#                            'Area m2'])

# Aplica a mascara de pixels validos DIRETAMENTE em cada banda, 
# em vez de empilhar/reshapar o raster inteiro e só filtrar depois.
df = pd.DataFrame({
    'OpUnit': band_opunit_id_map[mask_validos],
    f'LULC_{base_year}': band_lulc_base[mask_validos],
    f'LULC_{end_year}': band_lulc_end[mask_validos],
    # 'Sec_Veg': band_sec_veg_end[mask_validos],
    'IBGE': band_ibge_raster[mask_validos],
    f'Condicao_{base_year}': band_condition_map_base[mask_validos],
    f'Condicao_{end_year}': band_condition_map_end[mask_validos],
    # 'Classe_Borda': band_edge_map[mask_validos],
    # 'Classe_Queimada': band_fire_map[mask_validos],
    'Area m2': band_perc_area[mask_validos],
})

# Conta as repetições de cada combinação
df['Qtd_pixels'] = df.groupby([
                           'OpUnit',
                           f'LULC_{base_year}',
                           f'LULC_{end_year}',
                        #    'Sec_Veg',
                           'IBGE',
                           f'Condicao_{base_year}',
                           f'Condicao_{end_year}',
                        #    'Classe_Borda',
                        #    'Classe_Queimada',
                           #'Area m2'
                           ])['OpUnit'].transform('count')

df = df.groupby([
                'OpUnit',
                f'LULC_{base_year}',
                f'LULC_{end_year}',
                # 'Sec_Veg',
                'IBGE',
                f'Condicao_{base_year}',
                f'Condicao_{end_year}',
                # 'Classe_Borda',
                # 'Classe_Queimada',
                'Qtd_pixels'
                ], as_index=False)['Area m2'].sum()

# Para obter as combinações únicas
combinacoes_unicas = df.drop_duplicates().reset_index(drop=True)

# combinacoes_unicas = combinacoes_unicas.groupby([#f'LULC_{base_year}',
#                            'OpUnit',
#                            f'LULC_{end_year}',
#                            'Sec_Veg',
#                            'IBGE',
#                            'Classe_Borda'
#                            #'Classe_Queimada'
#                            ], as_index=False)[['Area m2', 'Qtd_pixels']].sum()

# Substitui os valores nodas por None
# combinacoes_unicas.loc[combinacoes_unicas['Classe_Borda'] == nodata_edge, 'Classe_Borda'] = None
# combinacoes_unicas.loc[combinacoes_unicas['Classe_Queimada'] == nodata_fire, 'Classe_Queimada'] = None
combinacoes_unicas.loc[combinacoes_unicas[f'Condicao_{base_year}'] == nodata_condition_base, f'Condicao_{base_year}'] = None
combinacoes_unicas.loc[combinacoes_unicas[f'Condicao_{end_year}'] == nodata_condition_end, f'Condicao_{end_year}'] = None

combinacoes_unicas['Area m2'] = (combinacoes_unicas['Area m2'] / 10).round(2)

combinacoes_unicas['OpUnit'] = combinacoes_unicas['OpUnit'].replace(uni_op[area])
combinacoes_unicas[f'LULC_{base_year}'] = combinacoes_unicas[f'LULC_{base_year}'].replace(dict_lulc)
combinacoes_unicas[f'LULC_{end_year}'] = combinacoes_unicas[f'LULC_{end_year}'].replace(dict_lulc)
combinacoes_unicas['IBGE'] = combinacoes_unicas['IBGE'].replace(dict_ibge)
# combinacoes_unicas['Classe_Borda'] = combinacoes_unicas['Classe_Borda'].replace(dict_edge)
# combinacoes_unicas['Classe_Queimada'] = combinacoes_unicas['Classe_Queimada'].replace(dict_fire)
combinacoes_unicas[f'Condicao_{base_year}'] = combinacoes_unicas[f'Condicao_{base_year}'].replace(dict_condicao)
combinacoes_unicas[f'Condicao_{end_year}'] = combinacoes_unicas[f'Condicao_{end_year}'].replace(dict_condicao)

print(combinacoes_unicas)
print(combinacoes_unicas['Qtd_pixels'].sum())
print(combinacoes_unicas['Area m2'].sum())
combinacoes_unicas.to_csv(f'{out_path}/lulc_condicao_legenda_{area}.csv',index=False)
combinacoes_unicas.to_excel(f'{out_path}/lulc_condicao_legenda_{area}.xlsx',index=False)