# -*- coding: utf-8 -*-
"""
Modulo de vegetacao secundaria do FUCA

Link do código-fonte: https://github.com/CID-ITV/FUCA
"""

import os
import numpy as np
from typing import *
from fuca.functions import *

def make_sec_veg_raster(band_age: np.ndarray, raster_std: str, area: str,
                        year: int, tmp_path: str, name: str, final_name: str,
                        descriptions: str) -> str:
  """
    Funcao que cria o raster final.
    
    Entrada:
        band_age: Matriz numpy de pixels.
        raster_std: Caminho do raster que sera usado como padrao.
        area: Area de interesse.
        ano_interesse: Ano de interesse.
        tmp_path: Caminho da pasta onde sera salvo o raster gerado.
        name: Nome intermediario que estara no nome final do arquivo raster a ser gerado.
        final_name: Nome final do arquivo raster a ser gerado.
        descriptions: String com descricao do raster que sera gerado.
        
    Saída:
        Retorna o caminho onde o raster gerado foi salvo.
  """ 
  with rasterio.open(raster_std) as dataset:
      profile = dataset.profile

      profile.update(
        dtype=rasterio.uint8,
        count=1,
        compress='lzw',
        nodata = 0)

      if final_name == None:
        final_name = tmp_path+"raster_"+name+"_"+area+"_"+str(year)+".tif"
      else:
        final_name = tmp_path+final_name
  #Salva o raster que foi criado
      with rasterio.open(final_name, "w", **profile,) as dest:
          dest.set_band_description(1, descriptions)
          dest.write(band_age, indexes=1)
      dest.close()
  dataset.close()

  dataset = None
  dest = None

  return final_name

def calculate_sec_veg_age(path_raster_prior: str, path_raster_later: str, anthropic_list: List[int], forest_class: int,
                          band_water: np.ndarray, band_age: np.ndarray, year: int, start_year: int, area: str, out_path: str,
                          final_name: str) -> str:

  """
    Funcao que calcula a idade da vegetacao secundaria por ano.
    
    Entrada:
        path_raster_prior: String com o caminho do raster de LUCC do ano anterior.
        path_raster_later: String com o caminho do raster de LUCC do ano posterior.
        band_agua: Matriz numpy com os pixels de agua.
        anthropic_list: Lista com as classes antropicas.
        forest_class: Integer com a classe que representa a floresta.
        band_age: Matriz numpy de pixels de idade.
        year: Integer do ano de interesse.
        start_year: Integer do ano que se inicia a serie temporal.
        area: String da area de interesse.
        out_path: Caminho da pasta onde sera salvo o raster gerado.
        
    Saída:
        Retorna uma string com caminho onde o raster de idade gerado foi salvo.
  """ 

  print('Acessa o raster de {}'.format(year))
  # Acessa o raster de classificacao do ano anterior
  band_antes, _ = get_raster_band(raster_path=path_raster_prior)

  # Seta todos os pixels antropicos com 100
  for i in anthropic_list:
    band_antes[band_antes == i] = 100
  # Seta todos os demais pixels como 0
  band_antes[band_antes != 100] = 2

  if year == start_year:
    print("Cria o mapa de idade 0")
    # Cria a matriz de idade de vegetacao secundaria
    band_age = np.zeros(band_antes.shape)

  print('Acessa o raster de {}'.format(year+1))
  # Acessa o raster de classificacao do proximo ano
  band_depois, _ = get_raster_band(raster_path=path_raster_later)

  # Seta todos os pixels floresta com 100
  band_depois[band_depois == forest_class] = 100
  # Seta todos os demais pixels como 0
  band_depois[band_depois != 100] = 0

  print("Cria mascara de quem e igual")
  # Cria a mascara boolena para elementos que sao iguais
  mask_equal = (band_antes == band_depois)
  band_antes = None
  # Converte a mascara para o tipo inteiro True = 1 e False = 0
  mask_equal = mask_equal.astype(int)


  if year > start_year:
    # Seta todos os pixels floresta com 100
    band_depois[band_depois == 100] = 1
    band_age = band_age * band_depois
    band_depois = None

    band_aux = np.zeros(band_age.shape)
    band_aux = (band_age != band_aux)

    band_age = band_age + band_aux
    band_aux = None


  band_age = band_age + mask_equal
  mask_equal = None

  band_age = band_age * band_water
  band_age = band_age.astype(int)

  print("Gera o raster de idade")

  raster_idade = make_sec_veg_raster(band_age = band_age, raster_std=path_raster_later, area=area,
                        year=year+1, tmp_path=out_path, name='', final_name=final_name,
                        descriptions='Secondary Vegetation Age Raster')
  
  return raster_idade, band_age