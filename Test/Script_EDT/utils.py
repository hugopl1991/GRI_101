import pandas as pd
import numpy as np


# ============================================================
# NOMES DE COLUNAS (dependentes do ano-base e ano-fim)
# ============================================================
def build_column_names(base_year, end_year):
    """Gera os nomes de colunas dependentes do ano-base e ano-fim."""
    return {
        'lulc_base': f'LULC_{base_year}',
        'lulc_end': f'LULC_{end_year}',
        'relulc_base': f'ReLULC{base_year}',
        'relulc_end': f'ReLULC{end_year}',
        'cond_base': f'Condicao_{base_year}',
        'cond_end': f'Condicao_{end_year}',
        'recond_base': f'ReCond{base_year}',
        'recond_end': f'ReCond{end_year}',
        'area_base': f'Area_{base_year}',
        'area_end': f'Area_{end_year}',
    }


# ============================================================
# CARGA E PREPARAÇÃO DOS DADOS
# ============================================================
def carregar_dados(file_fuca, file_reclass, cols, size_pixel):
    """
    Lê e prepara os dados brutos das planilhas, tolerando a ausência de abas
    específicas do Pará (geral/canga/N4N5) para rodar em outros estados.
    """
    try:
        FUCA = pd.read_excel(file_fuca, sheet_name='Sheet1')

        # Usa ExcelFile para poder checar quais abas existem antes de ler
        xls = pd.ExcelFile(file_reclass)
        Reclass_IBGE = pd.read_excel(xls, sheet_name='Reclass_IBGE')

        # Tabela GERAL de reclassificação de LULC: regra padrão aplicada quando
        # a linha não é OpUnit N4N5 nem pertence a uma OpUnit com Refúgio
        # Vegetacional Montano (canga). Aceita o nome novo 'Reclass_LULC_geral'
        # ou o nome legado 'Reclass_LULC_floresta' (planilhas antigas do PA).
        if 'Reclass_LULC_geral' in xls.sheet_names:
            Reclass_geral = pd.read_excel(xls, sheet_name='Reclass_LULC_geral')
        elif 'Reclass_LULC_floresta' in xls.sheet_names:
            Reclass_geral = pd.read_excel(xls, sheet_name='Reclass_LULC_floresta')
        else:
            Reclass_geral = pd.DataFrame(columns=['LULC', 'Reclass_LULC'])  # fallback vazio

        # Estados sem as abas de Canga/N4N5 (ex: MG) usam DataFrames vazios de fallback
        if 'Reclass_LULC_canga' in xls.sheet_names:
            Reclass_canga = pd.read_excel(xls, sheet_name='Reclass_LULC_canga')
        else:
            Reclass_canga = pd.DataFrame(columns=['LULC', 'Reclass_LULC'])

        if 'Reclass_LULC_N4N5' in xls.sheet_names:
            Reclass_N4N5 = pd.read_excel(xls, sheet_name='Reclass_LULC_N4N5')
        else:
            Reclass_N4N5 = pd.DataFrame(columns=['LULC', 'Reclass_LULC'])

        # Prioridade da regra GERAL:
        # - No Pará (aba Reclass_LULC_canga presente): mantém a lógica histórica
        #   em que a própria tabela de canga também serve como regra geral para
        #   as linhas que não são N4N5 nem OpUnit com canga.
        # - Em outros estados (sem aba de canga): usa a tabela geral/floresta
        #   (Reclass_LULC_geral, ou o nome legado Reclass_LULC_floresta).
        if not Reclass_canga.empty:
            Reclass_geral = Reclass_canga

    except FileNotFoundError as e:
        print(f"Erro ao carregar arquivos: Verifique se os caminhos estão corretos. Detalhe: {e}")
        raise

    # Limpeza básica e padronização
    for col in [cols['lulc_base'], cols['lulc_end']]:
        FUCA[col] = FUCA[col].astype(str).str.strip()
        FUCA.loc[FUCA[col] == "0", col] = 'Zero'

    # Regra específica PARNA (se a classe não existir na área, simplesmente não faz nada)
    idx_parna = FUCA[cols['lulc_end']] == "S11D - PARNA"
    FUCA.loc[idx_parna, cols['lulc_base']] = 'S11D'

    # Cálculo de área (tamanho do pixel vem do config.yaml)
    idx_zero = FUCA['Area m2'] == 0
    FUCA.loc[idx_zero, 'Area m2'] = FUCA.loc[idx_zero, 'Qtd_pixels'] * (size_pixel ** 2)
    FUCA['Area_ha'] = (FUCA['Area m2'] / 10000)

    return FUCA, Reclass_IBGE, Reclass_geral, Reclass_canga, Reclass_N4N5


# ============================================================
# RECLASSIFICAÇÃO
# ============================================================
def reclass_novo(var, opunit, ibge, lookup_geral, lookup_N4N5, lookup_canga, keycol, valcol):
    """
    Aplica as regras de reclassificação baseadas na Unidade Operacional e IBGE.

    Tolera lookups vazios (estados sem as tabelas de canga/N4N5): o dict()
    correspondente fica vazio e o .map() simplesmente não aplica essas regras,
    deixando o valor como NaN para as linhas afetadas.
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

    idx_N4N5 = is_N4N5
    out[idx_N4N5] = var_txt[idx_N4N5].map(dict_N4N5)

    idx_canga = ~is_N4N5 & is_canga_opunit
    out[idx_canga] = var_txt[idx_canga].map(dict_canga)

    idx_geral = ~is_N4N5 & ~is_canga_opunit
    out[idx_geral] = var_txt[idx_geral].map(dict_geral)

    return out


# ============================================================
# TABELAS INTERMEDIÁRIAS (106ai, 106b e 107ai)
# ============================================================
def gerar_tabelas_intermediarias(FUCA, cols, path_out_106, path_out_106b, path_out_107,
                                  path_out_reclass, sep, decimal, float_format):
    """
    Gera e exporta as tabelas 106ai, 106b e 107ai (incluindo GroupCount).

    - G106:  conversão de ecossistemas naturais, usando o LULC RECLASSIFICADO
             (ReLULC) do ano final.
    - G106b: mesma lógica do 106, mas agrupando pelo LULC BRUTO (não
             reclassificado) do ano final -- restaurada nesta versão.
    - G107b: área por classe de condição reclassificada (ReCond).
    """
    ReLULCBase_txt = FUCA[cols['relulc_base']].astype(str).str.strip().str.lower()
    ReLULCEnd_txt = FUCA[cols['relulc_end']].astype(str).str.strip().str.lower()

    # ==========================================
    # Tabela 106ai
    # ==========================================
    nat_changed = (ReLULCBase_txt != "antrópico") & (ReLULCBase_txt != ReLULCEnd_txt)
    FUCA_nat_changed = FUCA[nat_changed]

    G106 = FUCA_nat_changed.groupby(
        ['OpUnit', 'ReIBGE', cols['relulc_base'], cols['relulc_end']], as_index=False
    ).agg(
        GroupCount=('OpUnit', 'size'),
        sum_Area_ha=('Area_ha', 'sum')
    )

    # Tabela 106b: mesmo agrupamento, mas com o LULC bruto do ano final
    G106b = FUCA_nat_changed.groupby(
        ['OpUnit', 'ReIBGE', cols['relulc_base'], cols['lulc_end']], as_index=False
    ).agg(
        GroupCount=('OpUnit', 'size'),
        sum_Area_ha=('Area_ha', 'sum')
    )

    # ==========================================
    # Tabela 107ai
    # ==========================================
    ant_base = ReLULCBase_txt == "antrópico"
    ant_end = ReLULCEnd_txt == "antrópico"

    FUCA[cols['recond_base']] = np.where(ant_base, 'Zero', FUCA[cols['cond_base']])
    FUCA[cols['recond_end']] = np.where(ant_end, 'Zero', FUCA[cols['cond_end']])

    G107b = FUCA.groupby(
        ['OpUnit', 'ReIBGE', cols['recond_base'], cols['recond_end']], as_index=False
    ).agg(
        GroupCount=('OpUnit', 'size'),
        sum_Area_ha=('Area_ha', 'sum')
    )

    # Exportando com os caminhos e formatação vindos do config.yaml
    export_kwargs = dict(index=False, sep=sep, decimal=decimal, float_format=float_format)
    G106.to_csv(path_out_106, **export_kwargs)
    #G106b.to_csv(path_out_106b, **export_kwargs)
    G107b.to_csv(path_out_107, **export_kwargs)
    FUCA.to_csv(path_out_reclass, **export_kwargs)

    return ant_base, ant_end


# ============================================================
# BALANÇO NATURAL
# ============================================================
def calcular_balanco(FUCA, cols, ant_base, ant_end):
    """Calcula o balanço natural, antrópico e total por OpUnit."""
    isNatBase, isNatEnd = ~ant_base, ~ant_end
    area_base_col, area_end_col = cols['area_base'], cols['area_end']

    # 1. Classes Naturais
    baseNat = FUCA[['OpUnit', 'ReIBGE']].drop_duplicates()
    GBase = FUCA[isNatBase].groupby(['OpUnit', 'ReIBGE'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': area_base_col})
    GEnd = FUCA[isNatEnd].groupby(['OpUnit', 'ReIBGE'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': area_end_col})
    Gganho = FUCA[~isNatBase & isNatEnd].groupby(['OpUnit', 'ReIBGE'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': 'Ganho'})
    Gperda = FUCA[isNatBase & ~isNatEnd].groupby(['OpUnit', 'ReIBGE'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': 'Perda'})

    BalancoNat = baseNat.merge(GBase, on=['OpUnit', 'ReIBGE'], how='left')\
                        .merge(Gganho, on=['OpUnit', 'ReIBGE'], how='left')\
                        .merge(Gperda, on=['OpUnit', 'ReIBGE'], how='left')\
                        .merge(GEnd, on=['OpUnit', 'ReIBGE'], how='left').fillna(0)

    BalancoNat['Ganho_pct'] = np.where(BalancoNat[area_base_col] > 0, BalancoNat['Ganho'] / BalancoNat[area_base_col], 0)
    BalancoNat['Perda_pct'] = np.where(BalancoNat[area_base_col] > 0, BalancoNat['Perda'] / BalancoNat[area_base_col], 0)

    idxNaturais = (~BalancoNat['ReIBGE'].str.strip().str.lower().isin(["antrópico", "total"])) & (BalancoNat['ReIBGE'].str.strip() != "")
    BalancoNat = BalancoNat[idxNaturais].copy()

    # 2. Antrópico
    baseOp = FUCA[['OpUnit']].drop_duplicates()
    GAntBase = FUCA[~isNatBase].groupby('OpUnit', as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': area_base_col})
    GAntEnd = FUCA[~isNatEnd].groupby('OpUnit', as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': area_end_col})

    BalancoAnt = baseOp.merge(GAntBase, on='OpUnit', how='left').merge(GAntEnd, on='OpUnit', how='left').fillna(0)
    BalancoAnt = BalancoAnt.assign(ReIBGE="Antrópico", Ganho=0.0, Ganho_pct=np.nan, Perda=0.0, Perda_pct=np.nan)

    # 3. Total
    BalancoTot = FUCA.groupby('OpUnit', as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': area_base_col})
    BalancoTot[area_end_col] = BalancoTot[area_base_col]

    GGanhoTot = BalancoNat.groupby('OpUnit', as_index=False)['Ganho'].sum()
    GPerdaTot = BalancoNat.groupby('OpUnit', as_index=False)['Perda'].sum()

    BalancoTot = BalancoTot.merge(GGanhoTot, on='OpUnit', how='left').merge(GPerdaTot, on='OpUnit', how='left').fillna(0)
    BalancoTot['Ganho_pct'] = np.where(BalancoTot[area_base_col] > 0, BalancoTot['Ganho'] / BalancoTot[area_base_col], 0)
    BalancoTot['Perda_pct'] = np.where(BalancoTot[area_base_col] > 0, BalancoTot['Perda'] / BalancoTot[area_base_col], 0)
    BalancoTot['ReIBGE'] = "Total"

    # 4. Formatação Final
    rename_cols = {'ReIBGE': 'Classe'}
    frames = [df.rename(columns=rename_cols) for df in [BalancoNat, BalancoAnt, BalancoTot]]

    cols_order = ['OpUnit', 'Classe', area_base_col, 'Ganho', 'Ganho_pct', 'Perda', 'Perda_pct', area_end_col]
    SaidaBalanco = pd.concat(frames, ignore_index=True)[cols_order]

    ordem = {"Antrópico": 2, "Total": 3}
    SaidaBalanco['ordClasse'] = SaidaBalanco['Classe'].map(ordem).fillna(1)

    return SaidaBalanco.sort_values(by=['OpUnit', 'ordClasse', 'Classe']).drop(columns=['ordClasse'])
