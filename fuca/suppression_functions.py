# -*- coding: utf-8 -*-
"""
Modulo de areas suprimidas do FUCA

Link do código-fonte: https://github.com/CID-ITV/ITV_TEA_FUCA-back
"""

import os
from fuca.functions import *
from fuca.carbon_functions import *
import time

def calc_suppression(area: str,
                     year: int,
                     raster_agb_bgb: str,
                     raster_agb: str,
                     raster_bgb: str,
                     forest_id_file: str,
                     agb_file: str,
                     ecozone_file: str,
                     tmp_path: str,
                     shp_path: str,
                     save_zip: str,
                     path_shape_ecozone: str,
                     path_raster_map: str,
                     path_raster_sec: str,
                     path_shape_fito: str = None,
                     all_touched: bool = False):
  """
    Funcao que calcula o carbono por supressao para uma area e salva em um arquivo zip.
    
    Entrada:
        area: String contendo a area de interesse na qual a supressao esta inserida.
        year: Inteiro do ano em que a supressao foi realizada.
        raster_agb_bgb: String com o caminho para o mapa de TAGB + BGB.
        raster_agb: String com o caminho para o mapa de TAGB.
        raster_bgb: String com o caminho para o mapa de BGB.
        shp_path: String contendo o caminho para o shapefile da area suprimida.
        forest_id_file: Arquivo xlsx que contém os valores de ID.
        agb_file: Arquivo xlsx que contém os valores de AGB.
        ecozone_file: Arquivo xlsx que contém os IDs de ecozonas e coeficientes de BGB.
        tmp_path: String do caminho da pasta temporaria.
        save_zip: String do caminho onde sera salvo o zip gerado.
        path_shape_ecozone: String com o caminho para o shape de ecozonas.
        path_raster_map: String com o caminho para o raster de LUCC.
        path_raster_sec: String com o caminho para o raster de vegetacao secundaria.
        path_shape_fito: String com o caminho para o shape de fitofisionomia, se houver.
        dict_areas_shapes: Dicionario contendo as areas suprimidas.
        all_touched: Variavel booleana que define se o recorte sera feito com all_touched=True ou False.
        
    Saída:
  """

  print('\nCria o raster de TAGB, BGB e Carbono para areas suprimidas')

  #Obtem os IDs de vegetação do estado
  #print('Getting the state\'s Vegetation IDs from the file '+forest_id_file)
  veg_p_estado = get_forest_id(xlsx_path=forest_id_file,list_estados=[area])
  #print('Getting the AGB values and BGB coefficient from the file '+agb_file)
  agb_p_estado, agb_ibge, bgb_p_estado = get_agb_value(xlsx_path=agb_file,veg_p_estado=veg_p_estado)

  #recorta o mapbiomas
  path_raster_map = clip_raster(raster_path=path_raster_map,shp_path=shp_path,tmp_path=tmp_path,all_touched=all_touched)
  if not os.path.isfile(save_zip):
      save_zip = zip_file(path_file=path_raster_map, path_output='', name=save_zip)
  else:
    add_zip(path_zip=save_zip, path_file=path_raster_map)

  #recorta o mapa de Veg Sec
  path_raster_sec = clip_raster(raster_path=path_raster_sec,shp_path=shp_path,tmp_path=tmp_path,all_touched=all_touched)
  add_zip(path_zip=save_zip, path_file=path_raster_sec)

  #recorta o mapa de agb
  raster_agb = clip_raster(raster_path=raster_agb,shp_path=shp_path,tmp_path=tmp_path,all_touched=all_touched)
  add_zip(path_zip=save_zip, path_file=raster_agb)

  #recorta o mapa de BGB
  raster_bgb = clip_raster(raster_path=raster_bgb,shp_path=shp_path,tmp_path=tmp_path,all_touched=all_touched)
  add_zip(path_zip=save_zip, path_file=raster_bgb)

  #recorta o mapa de AGB+BGB
  raster_carbon = clip_raster(raster_path=raster_agb_bgb,shp_path=shp_path,tmp_path=tmp_path,all_touched=all_touched)
  add_zip(path_zip=save_zip, path_file=raster_carbon)

  #recorta o mapa de Ctotal
  #raster_ctotal = clip_raster(raster_path=raster_ctotal_o,shp_path=shp_path,tmp_path=tmp_path)
  #add_zip(path_zip=save_zip, path_file=raster_ctotal)

  #recorta o mapa de c solo
  #path_raster_soil = clip_raster(raster_path=path_raster_soil_o,shp_path=shp_path,tmp_path=tmp_path)
  #add_zip(path_zip=save_zip, path_file=path_raster_soil)

  #acessa o map de agb
  band,nodata,list_indices = access_raster(raster_path=raster_agb,list_ind=True)

  pixels_not_zero = []
  for ind in list_indices:
    pixel = band[ind[0]][ind[1]]
    if pixel != 0:
      pixels_not_zero.append(ind)
  band, list_indices = None, None

  band,nodata,list_indices = access_raster(raster_path=path_raster_map,list_ind=True)

  pixels_zero = []
  for ind in list_indices:
    pixels_zero.append(ind)

  band, list_indices = None, None

  pixels_zero = list(set(pixels_zero) - set(pixels_not_zero) )

  if path_shape_fito != None:
    #recorta shape do ibge com o estado
    path_shape_fito = clip_shp_w_shp(shp_t_clip=path_shape_fito,cut_shp=shp_path,tmp_path=tmp_path)
    #path_shape_ibge = clip_shp_w_shp(shp_t_clip=path_shape_ibge,cut_shp=shp_path,tmp_path=tmp_path)
    #acessa o ibge e retorna a lista de shapes
    shapes_raster = get_ibge_shapes(ibge_shp=path_shape_fito)
    #cria o raster com a lista de shapes
    ibge_raster = shapes_t_raster(shapes_raster=shapes_raster,raster_std=path_raster_map,tmp_path=tmp_path,nodata=None,dtype=None, name='fito')

    shapes_raster = None

  #recorta o mapa do ibge
  ibge_raster = clip_raster(raster_path=ibge_raster,shp_path=shp_path,tmp_path=tmp_path,all_touched=all_touched)
  add_zip(path_zip=save_zip, path_file=ibge_raster)

  #acessa o raster do ibge
  band,nodata = access_raster(raster_path=ibge_raster,list_ind=False)

  dict_ibge = {}
  for ind in pixels_zero:
    pixel = band[ind[0]][ind[1]]
    if np.isnan(pixel):
      print('nan encontrado',pixel,ind)
      continue
    if pixel not in dict_ibge:
      dict_ibge[pixel] = []
      dict_ibge[pixel].append(ind)
    else:
      dict_ibge[pixel].append(ind)

  band = None

  dict_tmp = {}
  for veg in dict_ibge:
    if agb_ibge[area][veg] not in dict_tmp:
      dict_tmp[agb_ibge[area][veg]] = dict_ibge[veg][:]
    else:
      for i in dict_ibge[veg][:]:
        dict_tmp[agb_ibge[area][veg]].append(i)

  dict_ibge = dict_tmp.copy()
  dict_tmp = None

  #acessa o map de agb e substitui pixels 0 por valores de agb segundo fitofisionomia
  band,nodata,list_indices = access_raster(raster_path=raster_agb,list_ind=True)

  dict_classes = {}
  for ind in list_indices:
    pixel = band[ind[0]][ind[1]]
    if pixel not in dict_classes:
      dict_classes[pixel] = []
      dict_classes[pixel].append(ind)
    else:
      dict_classes[pixel].append(ind)
  band, list_indices = None, None

  #remove os pixels repetidos
  for veg in dict_classes:
    dict_classes[veg] = list(set(dict_classes[veg]) - set(pixels_zero) )

  pixels_zero = None

  for veg in dict_ibge:
    if veg not in dict_classes:
      dict_classes[veg] = dict_ibge[veg][:]
    else:
      for pixel in dict_ibge[veg]:
        dict_classes[veg].append(pixel)

  #cria vetor de pixels e valores de agb
  vetor_pixels, vetor_agb = [], []

  for agb in dict_classes:
    for pixel in dict_classes[agb]:
      vetor_pixels.append(pixel)
      vetor_agb.append(agb)

  #Cria o raster de AGB
  raster_agb = make_raster(vetor_pixels=vetor_pixels, vetor_value=vetor_agb, raster_std=path_raster_map, est_interesse=area, ano_interesse=year,tmp_path=tmp_path, name='suprimido_TAGB_MgCha',nodata=-9999,dtype='float32',final_name=None,descriptions='Raster AGB(MM+L) Carbon in Mg-C/ha')
  add_zip(path_zip=save_zip, path_file=raster_agb)

  #rasteriza o shape de ecozonas
  path_shape_ecozone = clip_shp_w_shp(shp_t_clip=path_shape_ecozone,cut_shp=shp_path,tmp_path=tmp_path)
  shapes_raster = get_ecozone_shapes(eco_shp=path_shape_ecozone,col_interesse="GEZ_CODE")
  path_ecozone_raster = shapes_t_raster(shapes_raster=shapes_raster,raster_std=path_raster_map,tmp_path=tmp_path,nodata=0,dtype=None, name="ecozone")
  path_ecozone_raster = clip_raster(raster_path=path_ecozone_raster,shp_path=shp_path,tmp_path=tmp_path,all_touched=all_touched)
  add_zip(path_zip=save_zip, path_file=path_ecozone_raster)
  shapes_raster = None

  list_tmp = []
  for i in dict_ibge:
    for pixel in dict_ibge[i]:
      list_tmp.append(pixel)
  dict_ibge = None

  #Acessa o mapa de ecozonas
  band, _ = access_raster(raster_path=path_ecozone_raster,list_ind=False)
  dict_ecozones = access_ecozones(xlsx_path=ecozone_file,est_interesse=area)

  band_map, _ = access_raster(raster_path=path_raster_map,list_ind=False)
  #Cria o vetor de BGB
  vetor_bgb = []
  for c, pixel in enumerate(vetor_pixels):
    map_id = band_map[pixel[0]][pixel[1]]
    if bgb_p_estado[map_id] == 99:
      eco_ID = band[pixel[0]][pixel[1]]
      vetor_bgb.append(vetor_agb[c]*dict_ecozones[eco_ID])
    elif pixel in list_tmp:
      eco_ID = band[pixel[0]][pixel[1]]
      vetor_bgb.append(vetor_agb[c]*dict_ecozones[eco_ID])
    else:
      vetor_bgb.append(vetor_agb[c]*bgb_p_estado[map_id])
  band_map, band, list_tmp = None, None, None

  raster_agb = make_raster(vetor_pixels=vetor_pixels, vetor_value=vetor_bgb, raster_std=path_raster_map, est_interesse=area, ano_interesse=year,tmp_path=tmp_path, name='suprimido_BGB_MgCha',nodata=-9999,dtype='float32',final_name=None,descriptions='Raster BGB Carbon in Mg-C/ha')
  add_zip(path_zip=save_zip, path_file=raster_agb)

  #Cria o vetor de estoque de carbono AGB+BGB
  vetor_carbon = [vetor_agb[i]+vetor_bgb[i] for i in range(len(vetor_agb))]
  vetor_agb, vetor_bgb = None, None

  raster_agb = make_raster(vetor_pixels=vetor_pixels, vetor_value=vetor_carbon, raster_std=path_raster_map, est_interesse=area, ano_interesse=year,tmp_path=tmp_path, name='suprimido_TAGB_BGB_MgCha',nodata=-9999,dtype='float32',final_name=None,descriptions='Raster AGB(MM+L)+BGB Carbon in Mg-C/ha')
  add_zip(path_zip=save_zip, path_file=raster_agb)

  #Acessa mapa de c solo
  #band, _ = access_raster(raster_path=path_raster_soil,list_ind=False)

  # for c,ind in enumerate(vetor_pixels):
  #   pixel = band[ind[0]][ind[1]]
  #   vetor_carbon[c] += pixel
  band = None

  #raster_agb = make_raster(vetor_pixels=vetor_pixels, vetor_value=vetor_carbon, raster_std=path_raster_map, est_interesse=est_interesse, ano_interesse=ano_interesse,tmp_path=tmp_path, name='suprimido_Ctotal_MgCha',nodata=-9999,dtype='float32')
  #add_zip(path_zip=save_zip, path_file=raster_agb)
  vetor_pixels, vetor_carbon = None, None