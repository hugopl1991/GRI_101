# -*- coding: utf-8 -*-
"""
Modulo de queimadas do FUCA

Link do código-fonte: https://github.com/CID-ITV/ITV_TEA_FUCA-back
"""

from fuca.functions import *

def get_burning_coef(xlsx_path: str, area: str) -> dict:
  """
    Função que obtem os coeficientes de combustao por classe de uso do solo.
    
    Entrada:
        xlsx_path: String do arquivo xlsx que contém os coeficientes de combustao.
        area: String que contém a área de interesse.
        
    Saída: Retorna um dicionario com os coeficientes de combustao separados por classe de uso.
  """

  wb_obj = openpyxl.load_workbook(xlsx_path, data_only=True) 

  burning_dict = {}

  for row in wb_obj[area].iter_rows(min_row=2,max_row=wb_obj[area].max_row):
    if row[1].value != None:
      burning_dict[row[1].value] = float(row[2].value)
  
  return burning_dict

def get_emission_coef(xlsx_path: str, area: str) -> dict:
  """
    Função que obtem os coeficientes de emissao de GEE por classe de uso do solo.
    
    Entrada:
        xlsx_path: String do arquivo xlsx que contém os coeficientes de emissao.
        area: String que contém a área de interesse.
        
    Saída: Retorna um dicionario com os coeficientes de emissao separados por classe de uso.
  """

  wb_obj = openpyxl.load_workbook(xlsx_path, data_only=True) 

  emission_dict = {'CO':{},'CH4':{},'N2O':{},'Nox':{}}

  for row in wb_obj[area].iter_rows(min_row=2,max_row=wb_obj[area].max_row):
    if row[0].value != None:
      emission_dict['CO'][row[0].value] = float(row[2].value)
      emission_dict['CH4'][row[0].value] = float(row[3].value)
      emission_dict['N2O'][row[0].value] = float(row[4].value)
      emission_dict['Nox'][row[0].value] = float(row[5].value)
  
  return emission_dict

def calc_burning_raster(path_raster_lulc: str, path_raster_sec: str, path_raster_fire: str,
                        path_raster_agb: str, path_shp: str, combustion_file: str,
                        id_class: int, area: str, year: str, path_tmp: str, path_out: str):
  """
    Função que gera o mapa emissao por queimadas para uma determinada area e ano.
    
    Entrada:
        path_raster_lulc: String contendo o caminho do mapa de classe de uso.
        path_raster_sec: String contendo o caminho do mapa de vegetacao secundaria.
        path_raster_fire: String contendo o caminho do mapa de areas queimadas.
        path_raster_agb: String contendo o caminho do mapa de agb.
        path_shp: String com o caminho do shapefile da area de interesse.
        combustion_file: String com o caminho do arquivo contendo os coeficientes de combustao.
        id_class: Inteiro com a classe de vegetacao natural.
        area: String contendo a area de interesse.
        year: Inteiro contendo o ano de interesse.
        path_tmp: String com o caminho da pasta temporaria.
        path_out: String com o caminho da pasta de saida.
        
    Saída: Retorna um dicionario com os coeficientes de emissao separados por classe de uso.
  """

  burning_dict = get_burning_coef(xlsx_path=combustion_file,area=area)

  path_raster_lulc = clip_raster(raster_path=path_raster_lulc,shp_path=path_shp,tmp_path=path_tmp)
  path_raster_sec = clip_raster(raster_path=path_raster_sec,shp_path=path_shp,tmp_path=path_tmp)
  path_raster_fire = clip_raster(raster_path=path_raster_fire,shp_path=path_shp,tmp_path=path_tmp)
  path_raster_agb = clip_raster(raster_path=path_raster_agb,shp_path=path_shp,tmp_path=path_tmp)

  _,_,list_indices = access_raster(raster_path=path_raster_fire,list_ind=True)

  band,_ = access_raster(raster_path=path_raster_lulc,list_ind=False)

  dict_classes = create_raster_dict(band=band,list_indices=list_indices)
  band, list_indices = None, None

  if id_class in dict_classes:
    band,_,list_indices = access_raster(raster_path=path_raster_sec,list_ind=True)

    dict_idade = create_raster_dict(band=band,list_indices=dict_classes[id_class])
    band = None
    list_indices = None

    for id in dict_idade:
      dict_classes[id_class] = list( set(dict_classes[id_class]) - set(dict_idade[id]))

  band,_ = access_raster(raster_path=path_raster_agb,list_ind=False)

  vetor_value = []
  vetor_pixel = []
  
  if id_class in dict_classes:
    for id in dict_idade:
      for ind in dict_idade[id]:
        pixel = band[ind[0]][ind[1]]
        pixel = pixel/0.47
        if id >= 1 and id < 18:
          vetor_value.append(pixel*burning_dict[100]*0.001)
        else:
          vetor_value.append(pixel*burning_dict[200]*0.001)
        vetor_pixel.append(ind)
    dict_idade = None

  for id in dict_classes:
    for ind in dict_classes[id]:
      pixel = band[ind[0]][ind[1]]
      pixel = pixel/0.47
      vetor_value.append(pixel*burning_dict[id]*0.001)
      vetor_pixel.append(ind)
  dict_classes = None
  band = None

  raster_burning = make_raster(vetor_pixels=vetor_pixel, vetor_value=vetor_value, raster_std=path_raster_agb,
                               est_interesse=area, ano_interesse=year, tmp_path=path_out,
                               name='burning',final_name=None, nodata=-9999,
                               dtype='float32', descriptions='Raster with combustion values separated by land use class')
  
  vetor_value, vetor_pixel = None, None

  return raster_burning

def make_gas_emission_table(path_raster_lulc: str, path_raster_sec: str, raster_burning: str,
                            path_shp: str, emission_file: str, id_class: int, name_file: str,
                            area: str, year: int, path_tmp: str, path_out: str, country: str):
  """
    Funcao que gera a tabela de emissao de carbono por queimada por classe de uso.
    
    Entrada:
        path_raster_lulc: String com o caminho do mapa de classes de uso.
        path_raster_sec: String com o caminho do mapa de idade de vegetacao secundaria.
        raster_burning: String com o caminho do mapa de queimada.
        emission_file: String com o caminho do arquivo que contem os coeficientes de emissao.
        id_class: Inteiro com o classe de vegetacao primaria.
        path_shp: String com o caminho do shapefile da area de interesse.
        area: String com o nome da area de interesse.
        year: Inteiro com o ano de interesse.
        name_file: String do nome final que se deseja que a tabela tenha.
        tmp_path: String do caminho da pasta temporaria.
        path_out: String do caminho da pasta de saida.
        pais: String que informa o pais da area de interesse.
        
    Saída: Gera a tabela e salva na pasta de indicada.
  """

  path_raster_sec = clip_raster(raster_path=path_raster_sec,shp_path=path_shp,tmp_path=path_tmp)
  path_raster_lulc = clip_raster(raster_path=path_raster_lulc,shp_path=path_shp,tmp_path=path_tmp)

  emission_dict = get_emission_coef(xlsx_path=emission_file,area=country)

  _,_,list_indices = access_raster(raster_path=raster_burning,list_ind=True)

  band,_ = access_raster(raster_path=path_raster_lulc,list_ind=False)

  dict_classes = create_raster_dict(band=band,list_indices=list_indices)
  band, list_indices = None, None

  if id_class in dict_classes:

    _,_,list_indices = access_raster(raster_path=path_raster_sec,list_ind=True)

    list_idades = set(dict_classes[id_class]).intersection(set(list_indices))
    list_indices = None

    dict_classes[id_class] = list( set(dict_classes[id_class]) - set(list_idades))

  band,_ = access_raster(raster_path=raster_burning,list_ind=False)
  list_final = []

  for id in dict_classes:
    for ind in dict_classes[id]:
      pixel = band[ind[0]][ind[1]]
      co = pixel*emission_dict['CO'][id]
      ch4 = pixel*emission_dict['CH4'][id]
      n2o = pixel*emission_dict['N2O'][id]
      nox = pixel*emission_dict['Nox'][id]

      tmp = {"Classe":id,"SF":0,"CO":co,"CH4":ch4,"N2O":n2o,"Nox":nox,'burning':pixel}
      list_final.append(tmp.copy())

  if id_class in dict_classes:

    for ind in list_idades:
      pixel = band[ind[0]][ind[1]]
      co = pixel*emission_dict['CO'][id_class]
      ch4 = pixel*emission_dict['CH4'][id_class]
      n2o = pixel*emission_dict['N2O'][id_class]
      nox = pixel*emission_dict['Nox'][id_class]

      tmp = {"Classe":id_class,"SF":1,"CO":co,"CH4":ch4,"N2O":n2o,"Nox":nox,'burning':pixel}
      list_final.append(tmp.copy())
  band = None

  df = pd.DataFrame(list_final)
  list_final = None

  dict_final = []
  list_gas = ['CO','CH4','N2O','Nox']

  for classe in dict_classes:
    for sf in [0,1]:
      df_tmp = df.loc[(df['Classe'] == classe) & (df['SF'] == sf)]
      qtd = len(df_tmp)
      tmp = {"Classe":classe,"SF":sf,"Qtd":qtd}
      tmp['burning'] = df_tmp['burning'].sum()
      for gas in list_gas:
        gas_total = df_tmp[gas].sum()
        gas_media = df_tmp[gas].mean()
        gas_std = df_tmp[gas].std()
        
        tmp[gas+'_total'] = float("{:.5f}".format(gas_total))
        tmp[gas+'_media'] = float("{:.5f}".format(gas_media))
        tmp[gas+'_std'] = float("{:.5f}".format(gas_std))
      dict_final.append(tmp.copy())

  df, df_tmp = None, None

  df = pd.DataFrame(dict_final)
  if len(df) == 0:
    tmp = {"Classe":0,"SF":0,"Qtd":0,'CO_media':0,'CH4_media':0,'N2O_media':0,'Nox_media':0}
    df = pd.DataFrame([tmp])
  else:

    df = df.loc[(df['Qtd'] > 0)]

  if name_file == None:
    name_file = 'Tabela_'+area+'_queimada_'+str(year)+'.csv'
  else:
    if '.csv' not in name_file:
      name_file += '.csv'

  df.to_csv(path_out+name_file,index=False)