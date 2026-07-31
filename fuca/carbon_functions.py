# -*- coding: utf-8 -*-
"""
Funcoes para trabalhar com mapas de carbono

Link do código-fonte: https://github.com/CID-ITV/ITV_TEA_FUCA-back
"""

import os
from fuca.functions import *
import pandas as pd

def calc_rasters_diff(raster_current: str, raster_pass: str, area: str, 
                      interest_year: int, tmp_path: str, name: str = None) -> str:
  """
    Funcao que calcula a diferenca entre dois rasters.
    
    Entrada:
        raster_current: String com o caminho do mapa de carbono do ano atual.
        raster_pass: String com o caminho do mapa de carbono do ano anterior.
        area: String da area de interesse.
        interest_year: String com o ano de interesse (ano atual - ano anterior).
        tmp_path: String com o caminho da pasta temporaria.
        name: String com o nome que se deseja colocar no mapa.
        
    Saída: Retorna String com o caminho do mapa de diferenca que foi gerado.
  """
  band_current, _, list_indices_current = access_raster(raster_path=raster_current,list_ind=True)

  pixel_result_list = []
  value_result_list = []
  for ind in list_indices_current:
    value1 = band_current[ind[0]][ind[1]]
    if value1 < 0:
      value1 = 0
    pixel_result_list.append(ind)
    value_result_list.append(value1)
  band_current, list_indices_current = None, None
  
  band_pass, _ = access_raster(raster_path=raster_pass,list_ind=False)

  for i in range(len(pixel_result_list)):
    ind = pixel_result_list[i]
    value2 = band_pass[ind[0]][ind[1]]
    if value2 < 0:
      value2 = 0
    value_result_list[i] -= value2
  band_pass = None 

  raster = make_raster(vetor_pixels = pixel_result_list, vetor_value = value_result_list, raster_std=raster_current, 
                       est_interesse=area, ano_interesse=interest_year, tmp_path=tmp_path,
                       name=name,final_name=None,nodata=-9999,dtype='float32',descriptions='Carbon Diff in Mg-C/ha')
  pixel_result_list, value_result_list = None, None

  return raster

def make_emission_removal_raster(path_raster: str, path_LULC: str, area: str, year: str, 
                                classes_nat: List[int],  tmp_path: str, save_zip: str,
                                shp_path: str, path_out: str, carbon_type: str,
                                all_touched: bool = False) -> str:
  """
    Funcao que calcula e gera os mapas de Emissao Escopo 1, Emissao Biogenica e Remocao de carbono
    e salva em um zip.
    
    Entrada:
        path_raster: String com o caminho do mapa de diferenca.
        path_LULC: String com o caminho do mapa de classe de uso do ano atual.
        area: String com o nome da area de interesse.
        year: String com a diferenca de anos (ano atual - ano anterior).
        classes_nat: Lista contendo as classes de uso naturais.
        tmp_path: String contendo o caminho da pasta temporaria.
        save_zip: String contendo nome do arquivo zip que sera gerado para salvar os mapas.
        shp_path: String contendo o caminho do arquivo shapefile da area de interesse.
        path_out: String contendo o caminho da pasta de output que sera salvo o zip.
        carbon_type: String contendo o tipo de carbono do mapa. (Ex: TAGB_BGB).
        all_touched: Variavel booleana que define se o recorte sera feito com all_touched=True ou False.
        
    Saída: Retorna uma String com o caminho que foi salvo o zip.
  """
  if not os.path.exists(tmp_path):
    os.makedirs(tmp_path)
  tmp_path = tmp_path+'/' 
  
  band, _, list_indices = access_raster(raster_path=path_raster,list_ind=True)
  #band = band*0.33#Multiplica todos os valores

  positivos_indices = []
  positivos_value = []
  negativos_indices = []

  for ind in list_indices:
    pixel = band[ind[0]][ind[1]]
    if pixel > 0:
      positivos_indices.append(ind)
      positivos_value.append(pixel*0.33)
    elif pixel < 0:
      negativos_indices.append(ind)
  band, list_indices = None, None
  raster_remocao = make_raster(vetor_pixels=positivos_indices,vetor_value=positivos_value,raster_std=path_raster,
                               est_interesse=None, ano_interesse=None, tmp_path=tmp_path, name=None,
                               final_name=area+'_'+carbon_type+'_Remocao_CO2e_'+year+'.tif',
                               nodata=-9999,dtype='float32',descriptions='Carbon removal in MgCO2eq')
  
  print("Salva o raster da remocao no arquivo "+save_zip)
  if not os.path.isfile(save_zip):
      save_zip = zip_file(path_file=raster_remocao, path_output="", name=save_zip)
  else: 
      add_zip(path_zip=save_zip, path_file=raster_remocao)

 #list_indices = list(set(list_indices)-set(positivos_indices))
  path_LULC = clip_raster(raster_path=path_LULC,shp_path=shp_path,tmp_path=tmp_path,all_touched=all_touched)
  band, _ = access_raster(raster_path=path_LULC,list_ind=False)
  #print(path_LULC)
  dentro_indices = []
  fora_indices = []

  for ind in negativos_indices:
    pixel = band[ind[0]][ind[1]]
    if pixel in classes_nat:
      dentro_indices.append(ind)
    else:
      fora_indices.append(ind)
  band, negativos_indices = None, None

  dentro_value = []
  fora_value = []

  band, _ = access_raster(raster_path=path_raster,list_ind=False)
  for ind in dentro_indices:
    pixel = band[ind[0]][ind[1]]
    dentro_value.append(pixel*0.33)
  #dentro_value = [band[ind[0]][ind[1]]*0.33 for ind in dentro_indices]
  for ind in fora_indices:
    pixel = band[ind[0]][ind[1]]
    fora_value.append(pixel*0.33)
  #fora_value = [band[ind[0]][ind[1]]*0.33 for ind in fora_indices]
  band = None

  raster_dentro = make_raster(vetor_pixels=dentro_indices,vetor_value=dentro_value,raster_std=path_raster,
                              est_interesse=None, ano_interesse=None,tmp_path=tmp_path, name=None,
                              final_name=area+'_'+carbon_type+'_EmissaoE1_CO2e_'+year+'.tif',
                              nodata=-9999,dtype='float32',descriptions='Scope 1 Carbon Emission in MgCO2eq')
  
  add_zip(path_zip=save_zip, path_file=raster_dentro)

  raster_fora = make_raster(vetor_pixels=fora_indices,vetor_value=fora_value, raster_std=path_raster,
                            est_interesse=None, ano_interesse=None, tmp_path=tmp_path, name=None,
                            final_name=area+'_'+carbon_type+'_Emissaobio_CO2e_'+year+'.tif',
                            nodata=-9999,dtype='float32',descriptions='Biogenic Carbon Emission in MgCO2eq')
  
  add_zip(path_zip=save_zip, path_file=raster_fora)
  
  return save_zip

def sum_biomass_soil(path_LULC: str, path_raster_biomass: str, path_raster_soil: str,
                     area: str, year: int, path_shp: str, path_tmp: str,
                     path_out: str, no_veg_classes: List[int]):
  """
    Funcao que calcula e gera os mapas de carbono total ao somar mapas de TAGB-BGB + C solo.
    
    Entrada:
        path_LULC: String com o caminho do mapa de classe de uso do ano atual.
        path_raster_biomass: String com o caminho do mapa de carbono por biomassa.
        path_raster_soil: String com o caminho do mapa de carbono no solo.
        area: String com o nome da area de interesse.
        year: Inteiro do ano atual.
        path_shp: String contendo o caminho do arquivo shapefile da area de interesse.
        path_tmp: String contendo o caminho para salvar arquivos temporarios.
        path_out: String contendo o caminho para salvar a saida.
        no_veg_classes: Lista contendo as classes de uso nao vegetadas que serao zeradas.
        
    Saída: Retorna uma String com o caminho que foi salvo o raster.
  """
  path_LULC = clip_raster(raster_path=path_LULC,shp_path=path_shp,tmp_path=path_tmp)
  band_map,_,list_indices = access_raster(raster_path=path_LULC,list_ind=True)
  dict_classes = create_raster_dict(band=band_map,list_indices=list_indices)
  band_map = None

  remove_classes = {id:dict_classes[id] for id in no_veg_classes if id in dict_classes}
  dict_classes = None

  for id in remove_classes:
    list_indices = list( set(list_indices) - set(remove_classes[id]))

  vetor_pixel = []
  vetor_value = []

  band_biomass,_ = access_raster(raster_path=path_raster_biomass,list_ind=False)

  for ind in list_indices:
    pixel_b = band_biomass[ind[0]][ind[1]]
    vetor_value.append(pixel_b)
    vetor_pixel.append(ind)

  band_biomass = None

  band_soil,_ = access_raster(raster_path=path_raster_soil,list_ind=False)

  for c,ind in enumerate(list_indices):
    pixel_s = band_soil[ind[0]][ind[1]]
    if pixel_s < 0:
      pixel_s = 0
    vetor_value[c] += pixel_s

  band_soil, list_indices = None, None

  for id in remove_classes:
    for ind in remove_classes[id]:
      vetor_value.append(0)
      vetor_pixel.append(ind)

  path_raster_carbon = make_raster(vetor_pixels=vetor_pixel, vetor_value=vetor_value,
                                raster_std=path_raster_biomass, est_interesse=area,
                                ano_interesse=year,tmp_path=path_out, name='Ctotal_MgCha', final_name= None,
                                nodata=-9999,dtype='float32',descriptions='Total carbon (Aboveground + Dead wood + Litter +Belowground) in Mg-C/ha')

  return path_raster_carbon

def make_carbon_table(path_raster_LULC: str,
                      path_raster_sec: str,
                      path_raster_Carbon: str,
                      id_class: int,
                      shp_path: str,
                      area: str,
                      year: int,
                      name_file: str,
                      tmp_path: str,
                      path_out: str,
                      carbon_type: str,
                      all_touched: bool = False):
  """
    Funcao que gera a tabela de quantidade de carbono por classe de uso.
    
    Entrada:
        path_raster_LULC: String com o caminho do mapa de classes de uso.
        path_raster_sec: String com o caminho do mapa de idade de vegetacao secundaria.
        path_raster_Carbon: String com o caminho do mapa de carbono.
        id_class: Inteiro com o classe de vegetacao primaria.
        shp_path: String com o caminho do shapefile da area de interesse.
        area: String com o nome da area de interesse.
        year: Inteiro com o ano de interesse.
        name_file: String do nome final que se deseja que a tabela tenha.
        tmp_path: String do caminho da pasta temporaria.
        path_out: String do caminho da pasta de saida.
        carbon_type: String com o tipo do mapa de carbono (Ex: TAGB_BGB, Ctotal, C_soil).
        all_touched: Variavel booleana que define se o recorte sera feito com all_touched=True ou False.
        
    Saída: Gera a tabela e salva na pasta de indicada.
  """

  path_raster_LULC = clip_raster(raster_path=path_raster_LULC,shp_path=shp_path,tmp_path=tmp_path,all_touched=all_touched)
  raster_C_tmp = clip_raster(raster_path=path_raster_Carbon,shp_path=shp_path,tmp_path=tmp_path,all_touched=all_touched)

  _,_,list_indices = access_raster(raster_path=raster_C_tmp,list_ind=True)

  band,_ = access_raster(raster_path=path_raster_LULC,list_ind=False)

  dict_classes = create_raster_dict(band=band,list_indices=list_indices)
  band, list_indices = None, None

  if path_raster_sec != None:
    if id_class in dict_classes:
      path_raster_sec = clip_raster(raster_path=path_raster_sec,shp_path=shp_path,tmp_path=tmp_path,all_touched=all_touched)
      _,_,list_indices = access_raster(raster_path=path_raster_sec,list_ind=True)

      list_idades = set(dict_classes[id_class]).intersection(set(list_indices))
      list_indices = None

      dict_classes[id_class] = list( set(dict_classes[id_class]) - set(list_idades))
    else:
      list_idades = []

  band,_ = access_raster(raster_path=path_raster_Carbon,list_ind=False)
  list_final = []

  for id in dict_classes:
    for ind in dict_classes[id]:
      pixel = band[ind[0]][ind[1]]

      tmp = {"Classe":id,"SF":0,carbon_type+"_MgCha":pixel}
      list_final.append(tmp.copy())

  if path_raster_sec != None:
    for ind in list_idades:
      pixel = band[ind[0]][ind[1]]

      tmp = {"Classe":id_class,"SF":1,carbon_type+"_MgCha":pixel}
      list_final.append(tmp.copy())
  band = None

  df = pd.DataFrame(list_final)
  list_final = None

  dict_final = []

  for classe in dict_classes:
    for sf in [0,1]:
      df_tmp = df.loc[(df['Classe'] == classe) & (df['SF'] == sf)]
      qtd = len(df_tmp)
      tmp = {"Classe":classe,"SF":sf,"Qtd_npixels":qtd}
      c_total = df_tmp[carbon_type+'_MgCha'].sum()
      c_media = df_tmp[carbon_type+'_MgCha'].mean()
      c_std = df_tmp[carbon_type+'_MgCha'].std()
      #tmp = {"Tipo":tipo,"Classe":classe,"SF":sf,"Qtd":qtd,"Carbono_Total":c_total,'Carbono_media':c_media,'Carbono_std':c_std}
      tmp[carbon_type+'_total_sum_MgCha'] = float("{:.5f}".format(c_total))
      tmp[carbon_type+'_media_MgCha'] = float("{:.5f}".format(c_media))
      tmp[carbon_type+'_std_MgCha'] = float("{:.5f}".format(c_std))
      dict_final.append(tmp.copy())

  if len(dict_classes) == 0:
    tmp = {"Classe":0,"SF":0,"Qtd_npixels":0}
    tmp[carbon_type+'_total_sum_MgCha'] = 0
    tmp[carbon_type+'_media_MgCha'] = 0
    tmp[carbon_type+'_std_MgCha'] = 0
    dict_final.append(tmp.copy())

  df, df_tmp = None, None

  df = pd.DataFrame(dict_final)

  df = df.loc[(df['Qtd_npixels'] > 0)]

  df.loc['Total'] = df.sum()
  df.at['Total', 'Classe'] = 'Total'

  if name_file == None:
    name_file = 'Tabela_{}_{}_{}.csv'.format(area,carbon_type,year)
  else:
    if '.csv' not in name_file:
      name_file += '.csv'

  df.to_csv(path_out+name_file,index=False)

def make_carbon_table_by_line(path_raster_LULC: str,
                              path_raster_sec: str,
                              path_raster_Carbon: str,
                              id_class: int,
                              shp_path: str,
                              area: str,
                              year: int,
                              name_file: str,
                              tmp_path: str,
                              path_out: str,
                              carbon_type: str,
                              all_touched: bool = False):
  """
    Funcao que gera a tabela de quantidade de carbono por classe de uso considerando cada feicao de um shapefile.
    
    Entrada:
        path_raster_LULC: String com o caminho do mapa de classes de uso.
        path_raster_sec: String com o caminho do mapa de idade de vegetacao secundaria.
        path_raster_Carbon: String com o caminho do mapa de carbono.
        id_class: Inteiro com o classe de vegetacao primaria.
        shp_path: String com o caminho do shapefile da area de interesse.
        area: String com o nome da area de interesse.
        year: Inteiro com o ano de interesse.
        name_file: String do nome final que se deseja que a tabela tenha.
        tmp_path: String do caminho da pasta temporaria.
        path_out: String do caminho da pasta de saida.
        carbon_type: String com o tipo do mapa de carbono (Ex: TAGB_BGB, Ctotal, C_soil).
        all_touched: Variavel booleana que define se o recorte sera feito com all_touched=True ou False.
        
    Saída: Gera a tabela e salva na pasta de indicada.
  """

  shapes_dict = get_shapes_from_file(shp_path=shp_path)
  area_df = calculate_area_from_shape(shp_path=shp_path)

  for shape_key in shapes_dict:
    print('For line {}'.format(shape_key))
    path_raster_LULC_tmp = clip_raster(raster_path=path_raster_LULC,shapes=shapes_dict[shape_key],tmp_path=tmp_path,all_touched=all_touched)
    raster_C_tmp = clip_raster(raster_path=path_raster_Carbon,shapes=shapes_dict[shape_key],tmp_path=tmp_path,all_touched=all_touched)

    _,_,list_indices = access_raster(raster_path=raster_C_tmp,list_ind=True)

    band,_ = access_raster(raster_path=path_raster_LULC_tmp,list_ind=False)
    band_perc = fractional_pixel_weights(raster_C_tmp, shapes_dict[shape_key][0], list_indices)

    dict_classes = create_raster_dict(band=band,list_indices=list_indices)
    band, list_indices = None, None

    if path_raster_sec != None:
      if id_class in dict_classes:
        path_raster_sec_tmp = clip_raster(raster_path=path_raster_sec,shapes=shapes_dict[shape_key],tmp_path=tmp_path,all_touched=all_touched)
        _,_,list_indices = access_raster(raster_path=path_raster_sec_tmp,list_ind=True)

        list_idades = set(dict_classes[id_class]).intersection(set(list_indices))
        list_indices = None

        dict_classes[id_class] = list( set(dict_classes[id_class]) - set(list_idades))
      else:
        list_idades = []

    band,_ = access_raster(raster_path=raster_C_tmp,list_ind=False)
    list_final = []

    for id in dict_classes:
      for ind in dict_classes[id]:
        perc_value = band_perc[ind[0]][ind[1]]
        pixel = band[ind[0]][ind[1]] * perc_value

        tmp = {"Classe":id,"SF":0,"pixel_cover":perc_value,carbon_type+"_MgCha":pixel}
        list_final.append(tmp.copy())

    if path_raster_sec != None:
      for ind in list_idades:
        perc_value = band_perc[ind[0]][ind[1]]
        pixel = band[ind[0]][ind[1]] * perc_value

        tmp = {"Classe":id_class,"SF":1,"pixel_cover":perc_value,carbon_type+"_MgCha":pixel}
        list_final.append(tmp.copy())
    band = None

    df = pd.DataFrame(list_final)
    list_final = None

    dict_final = []

    area_m_total = area_df.loc[shape_key, 'area']# / 10**6
    print('area_m_total: {}'.format(area_m_total/ 10000))
    for classe in dict_classes:
      for sf in [0,1]:
        df_tmp = df.loc[(df['Classe'] == classe) & (df['SF'] == sf)]
        qtd = len(df_tmp)
        tmp = {"Classe":classe,"SF":sf,"Qtd_npixels":qtd}
        c_soil_total = df_tmp[carbon_type+'_MgCha'].sum()
        c_soil_media = df_tmp[carbon_type+'_MgCha'].mean()
        c_soil_std = df_tmp[carbon_type+'_MgCha'].std()
        area_km = df_tmp['pixel_cover'].sum() * 0.09#30 * 30 / 10**4
        #tmp = {"Tipo":tipo,"Classe":classe,"SF":sf,"Qtd":qtd,"Carbono_Total":c_total,'Carbono_media':c_media,'Carbono_std':c_std}
        tmp['area_ha'] = float("{:.6f}".format(area_km))
        tmp[carbon_type+'_total_sum_MgCha'] = float("{:.5f}".format(c_soil_total))
        tmp[carbon_type+'_media_MgCha'] = float("{:.5f}".format(c_soil_media))
        tmp[carbon_type+'_std_MgCha'] = float("{:.5f}".format(c_soil_std))
        dict_final.append(tmp.copy())

    df, df_tmp = None, None

    df = pd.DataFrame(dict_final)
    if len(df) > 0:
      df = df.loc[(df['Qtd_npixels'] > 0)]
    else:
      tmp = {"Classe":0,
             "SF":0,
             "Qtd_npixels":0,
             "area_m2":0,
             carbon_type+"_total_sum_MgCha":0,
             carbon_type+"_media_MgCha":0,
             carbon_type+"_std_MgCha":0}
      df = pd.DataFrame([tmp])
    
    df.loc['Total'] = df.sum()
    df.at['Total', 'Classe'] = 'Total'
    df.at['Total', carbon_type+'_media_MgCha'] = 0
    df.at['Total', carbon_type+'_std_MgCha'] = 0

    if name_file == None:
      name_file = 'Tabela_{}-{}_{}_{}.csv'.format(shape_key,area,carbon_type,year)
    else:
      name_file = '{}-{}'.format(shape_key, name_file)
      if '.csv' not in name_file:
        name_file += '.csv'

    df.to_csv(path_out+name_file,index=False)
    name_file = None