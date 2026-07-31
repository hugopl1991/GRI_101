# -*- coding: utf-8 -*-
"""
Funcao de estoque de biomassa do FUCA

Link do código-fonte: https://github.com/CID-ITV/ITV_TEA_FUCA-back
"""

import os
from fuca.functions import *

def carbon_biomass(path_mapbiomas = None, mapbio_clipped = False,
          path_shp = None, path_florest_sec = None,
          florest_sec_clipped = False, id_class=None, 
          max_agb=None,razao_ini=None,a1=None,
          path_ibge_raster = None,
          ibge_raster_clipped = None, path_ibge_shape = None,
          ibge_shape_clipped = False, path_agb_raster = None,
          agb_raster_clipped = False, path_ecozone_shape = None,
          ecozone_shape_clipped = False, path_ecozone_raster = None,
          ecozone_raster_clipped = False, path_output = None,
          forest_id_file = None,  agb_file = None, ecozone_file = None,
          est_interesse = None, ano_interesse = None, tmp_path = None, save_zip = None, all_touched=False):
  """
    Funcao que calcula e gera os mapas de TAGB, BGB e TAGB+BGB.
    
    Entrada:
        path_mapbiomas: Caminho do raster de classes de vegetacao principal.
        mapbio_clipped: Variavel booleana que informa se o raster de classes de vegetacao principal esta recortado.
        path_shp: Caminho do arquivo shapefile da area de interesse.
        path_florest_sec: Caminho do raster de classes de vegetacao secundaria.
        florest_sec_clipped: Variavel booleana que informa se o raster de vegetacao secundaria esta recortado.
        id_class: Variavel que informa o ID de floresta do raster de vegetacao principal.
        max_agb: Valor maximo de AGB da vegetacao secundaria.
        razao_ini: Valor da razao que descreve o crescimento de AGB por idade.
        a1: Valor inicial de AGB que recebera pixels com idade 1.
        path_ibge_raster: Caminho do raster de classes de vegetacao auxiliar.
        ibge_raster_clipped: Variavel booleana que informa se o raster de classes de vegetacao auxiliar esta recortado.
        path_ibge_shape: Caminho do shapefile de classes de vegetacao auxiliar.
        ibge_shape_clipped: Variavel booleana que informa se o shapefile de classes de vegetacao auxiliar esta recortado.
        path_agb_raster: Caminho do raster de AGB.
        agb_raster_clipped: Variavel booleana que informa se o raster de AGB esta recortado.
        path_ecozone_shape: Caminho do shapefile de Ecozonas.
        ecozone_shape_clipped: Variavel booleana que informa se o shapefile de Ecozonas esta recortado.
        path_ecozone_raster: Caminho do raster de Ecozonas.
        ecozone_raster_clipped: Variavel booleana que informa se o raster de Ecozonas esta recortado.
        path_output: Caminho da pasta de saida.
        forest_id_file: Arquivo xlsx que contém os valores de ID.
        agb_file: Arquivo xlsx que contém os valores de AGB.
        ecozone_file: Arquivo xlsx que contém os IDs de ecozonas e coeficientes de BGB.
        est_interesse: Area de interesse.
        ano_interesse: Ano de interesse.
        tmp_path: Caminho da pasta temporaria.
        save_zip: Nome do arquivo zip que sera salvo os dados gerados.
        all_touched: Variavel booleana que informa se todos os pixels que intersectam o poligono serao considerados.
        
    Saída: Os resultados gerados são salvos em um arquivo zip.
  """
  import time
  start_time = time.time()
  print('\nStarting FUCA execution for the state of '+est_interesse+' for the year of '+ str(ano_interesse))
  print("Create the temporary directory "+tmp_path)
  if not os.path.exists(tmp_path):
    os.makedirs(tmp_path)
  tmp_path = tmp_path+'/'

  #Obtem os IDs de vegetação do estado
  print('Getting the state\'s Vegetation IDs from the file '+forest_id_file)
  veg_p_estado = get_forest_id(xlsx_path=forest_id_file,list_estados=[est_interesse])
  print('Getting the AGB values and BGB coefficient from the file '+agb_file)
  agb_p_estado, agb_ibge, bgb_p_estado = get_agb_value(xlsx_path=agb_file,veg_p_estado=veg_p_estado)
  #
  #print(agb_ibge)
  #
  #Verifica o crs do raster. Se for direferente do esperado reprojeta
  if not checkCRS(raster_path=path_mapbiomas,crs_std='EPSG:4326'):
    print('Reproject raster file '+path_mapbiomas+' to CRS EPSG:4326')
    path_mapbiomas = convert_raster(raster_path=path_mapbiomas,crs_std='EPSG:4326',tmp_path=tmp_path)

  #Caso o raster ainda não esteja recortado. Recorta com o shapefile
  if not mapbio_clipped:
    print('Clip the raster file '+path_mapbiomas+' to the state of '+est_interesse)
    path_mapbiomas = clip_raster(raster_path=path_mapbiomas,shp_path=path_shp,tmp_path=tmp_path,all_touched=all_touched)

  print('Access the mapbiomas of the state of '+est_interesse)
  band, _, list_indices_map = access_raster(raster_path=path_mapbiomas,list_ind=True)

  class_not_in_table = {}
  dict_classes = {'natural':{},'antropica':{}}
  for ind in list_indices_map:
    pixel = band[ind[0]][ind[1]]
    if pixel in veg_p_estado[est_interesse]['natural']:
      if pixel not in dict_classes['natural']:
        dict_classes['natural'][pixel] = []
        dict_classes['natural'][pixel].append(ind)
      else:
        dict_classes['natural'][pixel].append(ind)
    elif pixel in veg_p_estado[est_interesse]['antropica']:
      if pixel not in dict_classes['antropica']:
        dict_classes['antropica'][pixel] = []
        dict_classes['antropica'][pixel].append(ind)
      else:
        dict_classes['antropica'][pixel].append(ind)
    else:
      if pixel not in class_not_in_table:
        class_not_in_table[pixel] = 1
      else:
        class_not_in_table[pixel] += 1
  band = None

  if len(class_not_in_table) != 0:
    print('There are pixels of unlisted classes!')
    for i in class_not_in_table:
      print('For class {} exist {} pixels'.format(i,class_not_in_table[i]))

    resp = ''
    while(resp != 'Y' or resp != 'N'):
      resp = input("Do you want to proceed with the run? (Y or N)")
      if resp == 'Y':
        pass
      else:
        sys.exit()

  class_not_in_table = None
  dict_ibge = {}
  if path_ibge_raster == None and path_ibge_shape == None:
    pass
  else:
    if id_class in list(dict_classes['natural'].keys()) and len(agb_ibge) != 0:
      if path_ibge_raster:
        if not ibge_raster_clipped:
          print('Clip the raster file '+path_ibge_raster+' to the state of '+est_interesse)
          path_ibge_raster = clip_raster(raster_path=path_ibge_raster,shp_path=path_shp,tmp_path=tmp_path, all_touched=all_touched)
      else:
        if not ibge_shape_clipped:
          print('Clip the shapefile '+path_ibge_shape+' to the state of '+est_interesse)
          path_ibge_shape = clip_shp_w_shp(shp_t_clip=path_ibge_shape,cut_shp=path_shp,tmp_path=tmp_path)

        print('Convert IBGE shapefile to raster')
        shapes_raster = get_ibge_shapes(ibge_shp=path_ibge_shape)
        path_ibge_raster = shapes_t_raster(shapes_raster=shapes_raster,raster_std=path_mapbiomas,tmp_path=tmp_path,nodata=0,dtype=None, name="ibge")
        shapes_raster = None

      if not checkCRS(raster_path=path_ibge_raster,crs_std='EPSG:4326'):
        print('Reproject raster file '+path_ibge_raster+' to CRS EPSG:4326')
        path_ibge_raster = convert_raster(raster_path=path_ibge_raster,crs_std='EPSG:4326',tmp_path=tmp_path)

      print('Access the IBGE raster')
      band, _ = access_raster(raster_path=path_ibge_raster,list_ind=False)

      for ind in dict_classes['natural'][id_class]:
        try:
          pixel = band[ind[0]][ind[1]]
          if pixel not in dict_ibge:
            dict_ibge[pixel] = []
            dict_ibge[pixel].append(ind)
          else:
            dict_ibge[pixel].append(ind)
        except:
          if est_interesse == "Indonesia":
            dict_ibge[1].append(ind)
      band = None
      #
      #print(len(dict_classes['natural'][3]))
      #print(len(dict_ibge[3]))
      #
      print('Combine the pixels of the Mapbiomas with the IBGE')
      dict_classes, agb_p_estado = join_ibge_mapbio(id_class=id_class,dict_classes=dict_classes,dict_ibge=dict_ibge,agb_ibge=agb_ibge,agb_p_estado=agb_p_estado,est_interesse=est_interesse)
      dict_ibge = None

  if path_florest_sec != False:
    if not checkCRS(raster_path=path_florest_sec,crs_std='EPSG:4326'):
      print('Reproject raster file '+path_florest_sec+' to CRS EPSG:4326')
      path_florest_sec = convert_raster(raster_path=path_florest_sec,crs_std='EPSG:4326',tmp_path=tmp_path)
    if not florest_sec_clipped:
      print('Clip the raster file '+path_florest_sec+' to the state of '+est_interesse)
      path_florest_sec = clip_raster(raster_path=path_florest_sec,shp_path=path_shp,tmp_path=tmp_path, all_touched=all_touched)

    print('Access the Secondary Forest raster')
    band, nodata, list_indices = access_raster(raster_path=path_florest_sec,list_ind=True)
    remove_list = list(set(list_indices)-set(list_indices_map))
    for i in remove_list:
      list_indices.remove(i)

    list_indices_map, remove_list = None, None

    print("Removes intersections between Mapbiomas and Secondary Forest raster")
    tmp = {}
    for forest in dict_classes['natural']:
      if forest == id_class or forest > 300:
        tmp[forest] = list(set(list_indices).intersection(dict_classes['natural'][forest]))

    print("Get the ages of secondary vegetation")
    idade_classes = {}
    for forest in tmp:
      for ind in tmp[forest]:
        pixel = band[ind[0]][ind[1]]
        if pixel not in idade_classes:
          idade_classes[pixel] = []
          idade_classes[pixel].append(ind)
        else:
          idade_classes[pixel].append(ind)
    band, tmp = None, None
    list_indices = None

    for map_id in dict_classes['natural']:
      if map_id == id_class or map_id > 300:
        for idade_id in idade_classes:
          dict_classes['natural'][map_id] = list(set(dict_classes['natural'][map_id])-set(idade_classes[idade_id]))

    dict_classes['secundaria'] = {}
    for idade_id in idade_classes:
      dict_classes['secundaria'][idade_id] = idade_classes[idade_id]
    idade_classes = None
  else:
    dict_classes['secundaria'] = {}

  dict_agb = dict.fromkeys(dict_classes['natural'])

  if path_agb_raster != None:
    if not checkCRS(raster_path=path_agb_raster,crs_std='EPSG:4326'):
      print('Reproject raster file '+path_agb_raster+' to CRS EPSG:4326')
      path_agb_raster = convert_raster(raster_path=path_agb_raster,crs_std='EPSG:4326',tmp_path=tmp_path)
    if not agb_raster_clipped:
      print('Clip the raster file '+path_agb_raster+' to the state of '+est_interesse)
      path_agb_raster = clip_raster(raster_path=path_agb_raster,shp_path=path_shp,tmp_path=tmp_path, all_touched=all_touched)

    print('Access the AGB raster from state of '+est_interesse)
    band, nodata = access_raster(raster_path=path_agb_raster,list_ind=False)
    band, nodata = check_is_nan(band=band,nodata=nodata)

    for forest in dict_classes['natural']:
      dict_agb[forest] = []
      if forest == id_class or forest == 4 or forest > 300:
        for pixel in dict_classes['natural'][forest]:
          value = band[pixel[0]][pixel[1]]
          if value == nodata:
            dict_agb[forest].append(value)
          else:
            dict_agb[forest].append(value*0.47)#converte o valor de AGB para carbono (AGB = BIOMASSA)
      else:
        for p in dict_classes['natural'][forest]:
          dict_agb[forest].append(nodata)
    band = None
  else:
    print('Fill in the AGB values taken from the file '+agb_file)
    nodata = -9999
    for forest in dict_classes['natural']:
      dict_agb[forest] = []
      for p in dict_classes['natural'][forest]:
        dict_agb[forest].append(nodata)

  for i in dict_agb:
    tmp = np.array(dict_agb[i],dtype='float32')
    tmp[tmp == nodata] = agb_p_estado[est_interesse]['natural'][i]
    dict_agb[i] = tmp
  tmp = None

  #Cria o vetor de pixels
  vetor_pixels, vetor_agb = make_raster_indices(dict_classes=dict_classes, dict_agb=dict_agb, agb_p_estado=agb_p_estado, est_interesse=est_interesse, max_agb=max_agb,razao_ini=razao_ini,a1=a1)
  dict_agb = None
  #Acessa as ecozonas
  if path_ecozone_raster:
    if not ecozone_raster_clipped:
      print('Clip the raster file '+path_ecozone_raster+' to the state of '+est_interesse)
      path_ecozone_raster = clip_raster(raster_path=path_ecozone_raster,shp_path=path_shp,tmp_path=tmp_path, all_touched=all_touched)
  else:
    if not ecozone_shape_clipped:
      print('Clip the shapefile '+path_ecozone_shape+' to the state of '+est_interesse)
      path_ecozone_shape = clip_shp_w_shp(shp_t_clip=path_ecozone_shape,cut_shp=path_shp,tmp_path=tmp_path)

    print('Convert ecozone shapefile to raster')
    shapes_raster = get_ecozone_shapes(eco_shp=path_ecozone_shape,col_interesse="GEZ_CODE")
    path_ecozone_raster = shapes_t_raster(shapes_raster=shapes_raster,raster_std=path_mapbiomas,tmp_path=tmp_path,nodata=0,dtype=None, name="ecozone")
    shapes_raster = None

  if not checkCRS(raster_path=path_ecozone_raster,crs_std='EPSG:4326'):
    print('Reproject raster file '+path_ecozone_raster+' to CRS EPSG:4326')
    path_ecozone_raster = convert_raster(raster_path=path_ecozone_raster,crs_std='EPSG:4326',tmp_path=tmp_path)

  print('Access the Ecozone raster')
  band, _ = access_raster(raster_path=path_ecozone_raster,list_ind=False)
  dict_ecozones = access_ecozones(xlsx_path=ecozone_file,est_interesse=est_interesse)

  band_map, _ = access_raster(raster_path=path_mapbiomas,list_ind=False)
  #Cria o vetor de BGB
  vetor_bgb = []
  for c, pixel in enumerate(vetor_pixels):
    map_id = band_map[pixel[0]][pixel[1]]
    if bgb_p_estado[map_id] == 99:
      eco_ID = band[pixel[0]][pixel[1]]
      #print(eco_ID)
      vetor_bgb.append(vetor_agb[c]*dict_ecozones[eco_ID])
    else:
      vetor_bgb.append(vetor_agb[c]*bgb_p_estado[map_id])
  band_map, band = None, None
  time.sleep(2)
  #Cria o raster de AGB
  print('Creates the AGB raster of the state of '+est_interesse)
  raster_agb = make_raster(vetor_pixels=vetor_pixels, vetor_value=vetor_agb, raster_std=path_mapbiomas, est_interesse=est_interesse, ano_interesse=ano_interesse,tmp_path=tmp_path, name='TAGB_MgCha',final_name=None, nodata=-9999,dtype='float32',descriptions='Raster AGB Carbon in Mg-C/ha')
  if not os.path.isfile(save_zip):
    save_zip = zip_file(path_file=raster_agb, path_output='', name=save_zip)
  else:
    add_zip(path_zip=save_zip, path_file=raster_agb)
    #print('Copy the AGB raster to the directory '+path_output)
    #copy_raster(file_path=raster_agb,out_path=path_output)

  print('Calculates the sha256 of the file '+raster_agb+' and copy it to the directory '+path_output)
  hash = checksum_sha256(file_path=raster_agb)
  add_zip(path_zip=save_zip, path_file=hash)
  #copy_raster(file_path=hash,out_path=path_output)

  #Cria o raster de BGB
  print('Creates the BGB raster of the state of '+est_interesse)
  raster_agb = make_raster(vetor_pixels=vetor_pixels, vetor_value=vetor_bgb, raster_std=path_mapbiomas, est_interesse=est_interesse, ano_interesse=ano_interesse,tmp_path=tmp_path, name='BGB_MgCha', final_name=None, nodata=-9999,dtype='float32',descriptions='Raster BGB Carbon in Mg-C/ha')
  add_zip(path_zip=save_zip, path_file=raster_agb)
  #print('Copy the BGB raster to the directory '+path_output)
  #copy_raster(file_path=raster_agb,out_path=path_output)

  print('Calculates the sha256 of the file '+raster_agb+' and copy it to the directory '+path_output)
  hash = checksum_sha256(file_path=raster_agb)
  add_zip(path_zip=save_zip, path_file=hash)
  #copy_raster(file_path=hash,out_path=path_output)

  #Cria o vetor de estoque de carbono AGB+BGB
  vetor_carbon = [vetor_agb[i]+vetor_bgb[i] for i in range(len(vetor_agb))]
  vetor_agb, vetor_bgb = None, None

  #Cria o raster de estoque de carbono AGB+BGB
  print('Creates the carbon raster of the state of '+est_interesse)
  raster_agb = make_raster(vetor_pixels=vetor_pixels, vetor_value=vetor_carbon, raster_std=path_mapbiomas, est_interesse=est_interesse, ano_interesse=ano_interesse,tmp_path=tmp_path, name='TAGB_BGB_MgCha',final_name=None, nodata=-9999,dtype='float32',descriptions='Raster AGB(MM+L)+BGB Carbon in Mg-C/ha')
  add_zip(path_zip=save_zip, path_file=raster_agb)
  #print('Copy the carbon raster to the directory '+path_output)
  #copy_raster(file_path=raster_agb,out_path=path_output)

  print('Calculates the sha256 of the file '+raster_agb+' and copy it to the directory '+path_output)
  hash = checksum_sha256(file_path=raster_agb)
  add_zip(path_zip=save_zip, path_file=hash)
  #copy_raster(file_path=hash,out_path=path_output)

  copy_raster(file_path=save_zip,out_path=path_output)

  #print('Delete the temporary folder '+tmp_path+' and generated files')
  #del_folder(dest=tmp_path)
  ##########################################################Retirar#################################################################
  print("--- %s seconds ---" % (time.time() - start_time))