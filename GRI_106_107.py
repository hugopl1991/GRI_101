import pandas as pd
import numpy as np
import yaml

# ================================
# Configurações Iniciais
# ================================
with open('config.yaml', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

PATHS, DATA = cfg['Paths'], cfg['Data']


# Formatando os caminhos com a variável de Área
AREA = DATA['area']
SIZE_PIXEL = DATA['size_pixel']
BASE_YEAR = DATA['base_year_compare']
END_YEAR = DATA['end_year']
SEP = DATA['separator']
DECIMAL = DATA['decimal_separator']
FLOAT_FORMAT = DATA['float_format']

FILE_TABLE = PATHS['file_table_comparison'].format(AREA=AREA)
FILE_RECLASS = PATHS['file_reclass_path'].format(AREA=AREA)

OUT_G106 = PATHS['output_g106']
OUT_G107 = PATHS['output_g107']
OUT_LULC_COND = PATHS['output_lulc_cond']
OUT_BALANCE = PATHS['output_balance']

def reclass_novo(var, opunit, ibge, lookup_geral, lookup_N4N5, lookup_canga, keycol, valcol):
    """
    Reclassifica uma variável baseada na Unidade Operacional e regras do IBGE.
    """
    var_txt = var.astype(str).str.strip()
    opunit_txt = opunit.astype(str).str.strip().str.upper()
    ibge_txt = ibge.astype(str).str.strip()

    dict_geral = dict(zip(lookup_geral[keycol].astype(str).str.strip(), lookup_geral[valcol]))
    dict_N4N5 = dict(zip(lookup_N4N5[keycol].astype(str).str.strip(), lookup_N4N5[valcol]))
    dict_canga = dict(zip(lookup_canga[keycol].astype(str).str.strip(), lookup_canga[valcol]))

    out = pd.Series(index=var.index, dtype=object)

    is_refugio = ibge_txt == "Refúgio Vegetacional Montano"
    opunits_com_canga = opunit_txt[is_refugio].unique()

    is_N4N5 = opunit_txt == "N4N5"
    is_canga_opunit = opunit_txt.isin(opunits_com_canga)

    # 1) OpUnit N4N5
    idx_N4N5 = is_N4N5
    out[idx_N4N5] = var_txt[idx_N4N5].map(dict_N4N5)

    # 2) Não N4N5, mas OpUnit tem Refúgio
    idx_canga = ~is_N4N5 & is_canga_opunit
    out[idx_canga] = var_txt[idx_canga].map(dict_canga)

    # 3) Restante
    idx_geral = ~is_N4N5 & ~is_canga_opunit
    out[idx_geral] = var_txt[idx_geral].map(dict_geral)

    return out


def main():
    # Nomes dinâmicos para colunas baseados no ano
    col_lulc_base = f'LULC_{BASE_YEAR}'
    col_lulc_end = f'LULC_{END_YEAR}'
    col_relulc_base = f'ReLULC_{BASE_YEAR}'
    col_relulc_end = f'ReLULC_{END_YEAR}'
    col_cond_base = f'Condicao_{BASE_YEAR}'
    col_cond_end = f'Condicao_{END_YEAR}'
    col_recond_base = f'ReCond_{BASE_YEAR}'
    col_recond_end = f'ReCond_{END_YEAR}'
    col_area_base = f'Area{BASE_YEAR}'
    col_area_end = f'Area{END_YEAR}'

    # ================================
    # Ler planilhas
    # ================================
    FUCA = pd.read_excel(FILE_TABLE, sheet_name='Sheet1')
    Reclass_IBGE = pd.read_excel(FILE_RECLASS, sheet_name='Reclass_IBGE')
    Reclass_canga = pd.read_excel(FILE_RECLASS, sheet_name='Reclass_LULC_canga')
    Reclass_N4N5 = pd.read_excel(FILE_RECLASS, sheet_name='Reclass_LULC_N4N5')

    FUCA[col_lulc_base] = FUCA[col_lulc_base].astype(str).str.strip()
    FUCA[col_lulc_end] = FUCA[col_lulc_end].astype(str).str.strip()

    FUCA.loc[FUCA[col_lulc_base] == "0", col_lulc_base] = 'Zero'
    FUCA.loc[FUCA[col_lulc_end] == "0", col_lulc_end] = 'Zero'

    idx_parna = FUCA[col_lulc_end] == "S11D - PARNA"
    FUCA.loc[idx_parna, col_lulc_base] = 'S11D'

    # ================================
    # Converter área
    # ================================
    idx_zero = FUCA['Area m2'] == 0
    FUCA.loc[idx_zero, 'Area m2'] = FUCA.loc[idx_zero, 'Qtd_pixels'] * (SIZE_PIXEL ** 2)
    FUCA['Area_ha'] = (FUCA['Area m2'] / 10000)

    # ================================
    # Reclassificação
    # ================================
    dict_ibge = dict(zip(Reclass_IBGE['IBGE'], Reclass_IBGE['Reclass_IBGE']))
    FUCA['ReIBGE'] = FUCA['IBGE'].map(dict_ibge).fillna(FUCA['IBGE']).astype(str)

    print("OpUnit com Refúgio Vegetacional Montano:")
    teste_opunit = FUCA.loc[FUCA['ReIBGE'] == "Refúgio Vegetacional Montano", 'OpUnit'].unique()
    print(teste_opunit)

    FUCA[col_relulc_base] = reclass_novo(
        FUCA[col_lulc_base], FUCA['OpUnit'], FUCA['ReIBGE'],
        Reclass_canga, Reclass_N4N5, Reclass_canga, 'LULC', 'Reclass_LULC'
    )

    FUCA[col_relulc_end] = reclass_novo(
        FUCA[col_lulc_end], FUCA['OpUnit'], FUCA['ReIBGE'],
        Reclass_canga, Reclass_N4N5, Reclass_canga, 'LULC', 'Reclass_LULC'
    )

    # ====================================================
    # TABELA 106ai - conversão de ecossistemas naturais
    # ====================================================
    ReLULCBaseY_txt = FUCA[col_relulc_base].astype(str).str.strip().str.lower()
    ReLULCEndY_txt = FUCA[col_relulc_end].astype(str).str.strip().str.lower()
    
    nat_changed = (ReLULCBaseY_txt != "antrópico") & (ReLULCBaseY_txt != ReLULCEndY_txt)
    FUCA_nat_changed = FUCA[nat_changed]

    G106 = FUCA_nat_changed.groupby(['OpUnit', 'ReIBGE', col_relulc_base, col_relulc_end], as_index=False).agg(
        GroupCount=('OpUnit', 'size'),
        sum_Area_ha=('Area_ha', 'sum')
    )
    
    G106b = FUCA_nat_changed.groupby(['OpUnit', 'ReIBGE', col_relulc_base, col_lulc_end], as_index=False).agg(
        GroupCount=('OpUnit', 'size'),
        sum_Area_ha=('Area_ha', 'sum')
    )

    # ====================================================
    # TABELA 107ai - área de ecossistemas por classe de condição
    # ====================================================
    antBaseY = ReLULCBaseY_txt == "antrópico"
    antEndY = ReLULCEndY_txt == "antrópico"

    FUCA[col_recond_base] = FUCA[col_cond_base]   
    FUCA[col_recond_end] = FUCA[col_cond_end]
    FUCA.loc[antBaseY, col_recond_base] = 'Zero'
    FUCA.loc[antEndY, col_recond_end] = 'Zero'

    G107b = FUCA.groupby(['OpUnit', 'ReIBGE', col_recond_base, col_recond_end], as_index=False).agg(
        GroupCount=('OpUnit', 'size'),
        sum_Area_ha=('Area_ha', 'sum')
    )

    # ================================
    # Exportar resultados iniciais
    # ================================
    G106.to_csv(OUT_G106, index=False,  sep=SEP, decimal=DECIMAL, float_format=FLOAT_FORMAT)
    G107b.to_csv(OUT_G107, index=False, sep=SEP, decimal=DECIMAL, float_format=FLOAT_FORMAT)
    FUCA.to_csv(OUT_LULC_COND, index=False, sep=SEP, decimal=DECIMAL, float_format=FLOAT_FORMAT)

    print('Tabelas parciais geradas com sucesso.')

    # ====================================================
    # TABELA BALANÇO NATURAL POR ReIBGE
    # ====================================================
    isNatBaseY = ~antBaseY
    isNatEndY = ~antEndY

    # ---- 1) classes naturais por ReIBGE
    G_Base = FUCA[isNatBaseY].groupby(['OpUnit', 'ReIBGE'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': col_area_base})
    G_End = FUCA[isNatEndY].groupby(['OpUnit', 'ReIBGE'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': col_area_end})
    
    Gganho = FUCA[~isNatBaseY & isNatEndY].groupby(['OpUnit', 'ReIBGE'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': 'Ganho'})
    Gperda = FUCA[isNatBaseY & ~isNatEndY].groupby(['OpUnit', 'ReIBGE'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': 'Perda'})

    baseNat = FUCA[['OpUnit', 'ReIBGE']].drop_duplicates()

    BalancoNat = baseNat.merge(G_Base, on=['OpUnit', 'ReIBGE'], how='left')
    BalancoNat = BalancoNat.merge(Gganho, on=['OpUnit', 'ReIBGE'], how='left')
    BalancoNat = BalancoNat.merge(Gperda, on=['OpUnit', 'ReIBGE'], how='left')
    BalancoNat = BalancoNat.merge(G_End, on=['OpUnit', 'ReIBGE'], how='left')

    BalancoNat[[col_area_base, 'Ganho', 'Perda', col_area_end]] = BalancoNat[[col_area_base, 'Ganho', 'Perda', col_area_end]].fillna(0)

    BalancoNat['Ganho_pct'] = np.where(BalancoNat[col_area_base] > 0, BalancoNat['Ganho'] / BalancoNat[col_area_base], 0)
    BalancoNat['Perda_pct'] = np.where(BalancoNat[col_area_base] > 0, BalancoNat['Perda'] / BalancoNat[col_area_base], 0)

    reibge_txt = BalancoNat['ReIBGE'].astype(str).str.strip().str.lower()
    idxNaturais = (reibge_txt != "antrópico") & (reibge_txt != "total") & (reibge_txt.str.len() > 0)
    BalancoNat = BalancoNat[idxNaturais].copy()

    # ---- 2) linha Antrópico por OpUnit
    GAntBase = FUCA[~isNatBaseY].groupby(['OpUnit'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': col_area_base})
    GAntEnd = FUCA[~isNatEndY].groupby(['OpUnit'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': col_area_end})

    baseOp = FUCA[['OpUnit']].drop_duplicates()
    
    BalancoAnt = baseOp.merge(GAntBase, on='OpUnit', how='left')
    BalancoAnt = BalancoAnt.merge(GAntEnd, on='OpUnit', how='left')
    BalancoAnt[[col_area_base, col_area_end]] = BalancoAnt[[col_area_base, col_area_end]].fillna(0)
    
    BalancoAnt['ReIBGE'] = "Antrópico"
    BalancoAnt['Ganho'] = 0.0
    BalancoAnt['Ganho_pct'] = np.nan
    BalancoAnt['Perda'] = 0.0
    BalancoAnt['Perda_pct'] = np.nan

    # ---- 3) linha Total por OpUnit
    BalancoTot = FUCA.groupby(['OpUnit'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': col_area_base})
    BalancoTot[col_area_end] = BalancoTot[col_area_base] 

    GGanhoTot = BalancoNat.groupby(['OpUnit'], as_index=False)['Ganho'].sum()
    GPerdaTot = BalancoNat.groupby(['OpUnit'], as_index=False)['Perda'].sum()

    BalancoTot = BalancoTot.merge(GGanhoTot, on='OpUnit', how='left')
    BalancoTot = BalancoTot.merge(GPerdaTot, on='OpUnit', how='left')
    BalancoTot[['Ganho', 'Perda']] = BalancoTot[['Ganho', 'Perda']].fillna(0)

    BalancoTot['Ganho_pct'] = np.where(BalancoTot[col_area_base] > 0, BalancoTot['Ganho'] / BalancoTot[col_area_base], 0)
    BalancoTot['Perda_pct'] = np.where(BalancoTot[col_area_base] > 0, BalancoTot['Perda'] / BalancoTot[col_area_base], 0)
    BalancoTot['ReIBGE'] = "Total"

    # ---- 4) padronizar nomes e juntar tudo
    col_out_base = f'Area_{BASE_YEAR}'
    col_out_end = f'Area_{END_YEAR}'

    rename_cols = {
        'ReIBGE': 'Classe', col_area_base: col_out_base, col_area_end: col_out_end
    }
    
    BalancoNat = BalancoNat.rename(columns=rename_cols)
    BalancoAnt = BalancoAnt.rename(columns=rename_cols)
    BalancoTot = BalancoTot.rename(columns=rename_cols)

    cols_order = ['OpUnit', 'Classe', col_out_base, 'Ganho', 'Ganho_pct', 'Perda', 'Perda_pct', col_out_end]
    
    SaidaBalanco = pd.concat([
        BalancoNat[cols_order],
        BalancoAnt[cols_order],
        BalancoTot[cols_order]
    ], ignore_index=True)

    def class_order(c):
        if c == "Antrópico": return 2
        elif c == "Total": return 3
        return 1

    SaidaBalanco['ordClasse'] = SaidaBalanco['Classe'].apply(class_order)
    SaidaBalanco = SaidaBalanco.sort_values(by=['OpUnit', 'ordClasse', 'Classe']).drop(columns=['ordClasse'])

    SaidaBalanco.to_csv(OUT_BALANCE, index=False, sep=SEP, decimal=DECIMAL, float_format=FLOAT_FORMAT)
    
    print('Tabela de balanço gerada com sucesso.')

if __name__ == "__main__":
    main()
