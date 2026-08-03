import pandas as pd
import numpy as np

def reclass_novo(var, opunit, ibge, lookup_geral, lookup_N4N5, lookup_canga, keycol, valcol):
    """
    Função equivalente a reclass_novo do MATLAB.
    Reclassifica uma variável baseada na Unidade Operacional e regras do IBGE.
    """
    # Padroniza entradas como string
    var_txt = var.astype(str).str.strip()
    opunit_txt = opunit.astype(str).str.strip().str.upper()
    ibge_txt = ibge.astype(str).str.strip()

    # Cria dicionários a partir dos lookups para mapeamento rápido
    dict_geral = dict(zip(lookup_geral[keycol].astype(str).str.strip(), lookup_geral[valcol]))
    dict_N4N5 = dict(zip(lookup_N4N5[keycol].astype(str).str.strip(), lookup_N4N5[valcol]))
    dict_canga = dict(zip(lookup_canga[keycol].astype(str).str.strip(), lookup_canga[valcol]))

    # Define o tipo da saída
    out = pd.Series(index=var.index, dtype=object)

    # Identificar OpUnits com canga (Refúgio Vegetacional Montano)
    is_refugio = ibge_txt == "Refúgio Vegetacional Montano"
    opunits_com_canga = opunit_txt[is_refugio].unique()

    # Regras por linha, herdando a regra da OpUnit
    is_N4N5 = opunit_txt == "N4N5"
    is_canga_opunit = opunit_txt.isin(opunits_com_canga)

    # 1) OpUnit N4N5 -> usa lookup_N4N5
    idx_N4N5 = is_N4N5
    out[idx_N4N5] = var_txt[idx_N4N5].map(dict_N4N5)

    # 2) Não N4N5, mas OpUnit tem Refúgio Vegetacional Montano -> usa lookup_canga
    idx_canga = ~is_N4N5 & is_canga_opunit
    out[idx_canga] = var_txt[idx_canga].map(dict_canga)

    # 3) Restante -> usa lookup_geral
    idx_geral = ~is_N4N5 & ~is_canga_opunit
    out[idx_geral] = var_txt[idx_geral].map(dict_geral)

    return out


def main():
    # ================================
    # Ler planilhas
    # ================================
    file = r'output/lulc_condicao_legenda_PA.xlsx'
    file_reclass = 'inputs/Planilhas/Reclass_PA.xlsx'

    # Lê as tabelas
    FUCA = pd.read_excel(file, sheet_name='Sheet1')
    Reclass_IBGE = pd.read_excel(file_reclass, sheet_name='Reclass_IBGE')
    Reclass_canga = pd.read_excel(file_reclass, sheet_name='Reclass_LULC_canga')
    Reclass_N4N5 = pd.read_excel(file_reclass, sheet_name='Reclass_LULC_N4N5')

    # Limpa espaços e transforma em string para garantir o filtro correto
    FUCA['LULC_2020'] = FUCA['LULC_2020'].astype(str).str.strip()
    FUCA['LULC_2024'] = FUCA['LULC_2024'].astype(str).str.strip()

    # Substituir 0 por Zero
    FUCA.loc[FUCA['LULC_2020'] == "0", 'LULC_2020'] = 'Zero'
    FUCA.loc[FUCA['LULC_2024'] == "0", 'LULC_2024'] = 'Zero'

    # Substituir S11D - PARNA por S11D
    idx_parna = FUCA['LULC_2024'] == "S11D - PARNA"
    FUCA.loc[idx_parna, 'LULC_2020'] = 'S11D'

    # ================================
    # Converter área
    # ================================
    # Se vier com área zero, calcular pelo número de pixels
    idx_zero = FUCA['Area m2'] == 0
    FUCA.loc[idx_zero, 'Area m2'] = FUCA.loc[idx_zero, 'Qtd_pixels'] * 30 * 30

    # Área em ha
    FUCA['Area_ha'] = (FUCA['Area m2'] / 10000)

    # ================================
    # Reclassificação
    # ================================
    # Reclassificar IBGE
    dict_ibge = dict(zip(Reclass_IBGE['IBGE'], Reclass_IBGE['Reclass_IBGE']))
    FUCA['ReIBGE'] = FUCA['IBGE'].map(dict_ibge).fillna(FUCA['IBGE']).astype(str)

    # Mostra as áreas com refúgio Vegetacional Montano
    print("OpUnit com Refúgio Vegetacional Montano:")
    teste_opunit = FUCA.loc[FUCA['ReIBGE'] == "Refúgio Vegetacional Montano", 'OpUnit'].unique()
    print(teste_opunit)

    # Reclassifica Uso da terra
    # Obs: no código original do Matlab, o `lookup_geral` recebe Reclass_canga. 
    # Manteve-se o mesmo comportamento aqui.
    FUCA['ReLULC20'] = reclass_novo(
        FUCA['LULC_2020'], FUCA['OpUnit'], FUCA['ReIBGE'],
        Reclass_canga, Reclass_N4N5, Reclass_canga, 'LULC', 'Reclass_LULC'
    )
    
    FUCA['ReLULC24'] = reclass_novo(
        FUCA['LULC_2024'], FUCA['OpUnit'], FUCA['ReIBGE'],
        Reclass_canga, Reclass_N4N5, Reclass_canga, 'LULC', 'Reclass_LULC'
    )

    # ====================================================
    # TABELA 106ai - conversão de ecossistemas naturais
    # ====================================================
    ReLULC20_txt = FUCA['ReLULC20'].astype(str).str.strip().str.lower()
    ReLULC24_txt = FUCA['ReLULC24'].astype(str).str.strip().str.lower()
    
    nat_changed = (ReLULC20_txt != "antrópico") & (ReLULC20_txt != ReLULC24_txt)
    FUCA_nat_changed = FUCA[nat_changed]

    # Substituição de .sum() por .agg() para obter GroupCount e sum_Area_ha
    G106 = FUCA_nat_changed.groupby(['OpUnit', 'ReIBGE', 'ReLULC20', 'ReLULC24'], as_index=False).agg(
        GroupCount=('OpUnit', 'size'),
        sum_Area_ha=('Area_ha', 'sum')
    )
    
    G106b = FUCA_nat_changed.groupby(['OpUnit', 'ReIBGE', 'ReLULC20', 'LULC_2024'], as_index=False).agg(
        GroupCount=('OpUnit', 'size'),
        sum_Area_ha=('Area_ha', 'sum')
    )

    # ====================================================
    # TABELA 107ai - área de ecossistemas por classe de condição
    # ====================================================
    ant20 = ReLULC20_txt == "antrópico"
    ant24 = ReLULC24_txt == "antrópico"
    
    FUCA['ReCond20'] = FUCA['Condicao_2020']
    FUCA['ReCond24'] = FUCA['Condicao_2024']
    FUCA.loc[ant20, 'ReCond20'] = 'Zero'
    FUCA.loc[ant24, 'ReCond24'] = 'Zero'

    # Substituição de .sum() por .agg() para obter GroupCount e sum_Area_ha
    G107b = FUCA.groupby(['OpUnit', 'ReIBGE', 'ReCond20', 'ReCond24'], as_index=False).agg(
        GroupCount=('OpUnit', 'size'),
        sum_Area_ha=('Area_ha', 'sum')
    )

    # ================================
    # Exportar resultados iniciais
    # ================================
    G106.to_csv('output/Saida1016.csv', 
                index=False,
                float_format='%.2f',
                sep=';',
                decimal='.'
                )
    # G106b.to_csv('Saida1016b.csv', index=False)
    G107b.to_csv('output/Saida1017b.csv', 
                index=False,
                float_format='%.2f',
                sep=';',
                decimal='.'
                )
    FUCA.to_csv('output/lulc_condicao_reclass.csv', 
                index=False,
                float_format='%.2f',
                sep=';',
                decimal='.'
                )
    
    print('Tabelas geradas com sucesso.')

    # ====================================================
    # TABELA BALANÇO NATURAL POR ReIBGE
    # ====================================================
    isNat20 = ~ant20
    isNat24 = ~ant24

    # ---- 1) classes naturais por ReIBGE
    G2020 = FUCA[isNat20].groupby(['OpUnit', 'ReIBGE'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': 'Area2020'})
    G2024 = FUCA[isNat24].groupby(['OpUnit', 'ReIBGE'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': 'Area2024'})
    
    # Ganho: antrópico -> natural
    Gganho = FUCA[~isNat20 & isNat24].groupby(['OpUnit', 'ReIBGE'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': 'Ganho'})
    
    # Perda: natural -> antrópico
    Gperda = FUCA[isNat20 & ~isNat24].groupby(['OpUnit', 'ReIBGE'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': 'Perda'})

    # Base de combinações OpUnit x ReIBGE
    baseNat = FUCA[['OpUnit', 'ReIBGE']].drop_duplicates()

    # Mesclagens (Outer Joins)
    BalancoNat = baseNat.merge(G2020, on=['OpUnit', 'ReIBGE'], how='left')
    BalancoNat = BalancoNat.merge(Gganho, on=['OpUnit', 'ReIBGE'], how='left')
    BalancoNat = BalancoNat.merge(Gperda, on=['OpUnit', 'ReIBGE'], how='left')
    BalancoNat = BalancoNat.merge(G2024, on=['OpUnit', 'ReIBGE'], how='left')

    # Trocar NaN por zero
    BalancoNat[['Area2020', 'Ganho', 'Perda', 'Area2024']] = BalancoNat[['Area2020', 'Ganho', 'Perda', 'Area2024']].fillna(0)

    # Ganho% e Perda%
    BalancoNat['Ganho_pct'] = np.where(BalancoNat['Area2020'] > 0, BalancoNat['Ganho'] / BalancoNat['Area2020'], 0)
    BalancoNat['Perda_pct'] = np.where(BalancoNat['Area2020'] > 0, BalancoNat['Perda'] / BalancoNat['Area2020'], 0)

    # Mantém só classes naturais explícitas
    reibge_txt = BalancoNat['ReIBGE'].astype(str).str.strip().str.lower()
    idxNaturais = (reibge_txt != "antrópico") & (reibge_txt != "total") & (reibge_txt.str.len() > 0)
    BalancoNat = BalancoNat[idxNaturais].copy()

    # ---- 2) linha Antrópico por OpUnit
    GAnt2020 = FUCA[~isNat20].groupby(['OpUnit'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': 'Area2020'})
    GAnt2024 = FUCA[~isNat24].groupby(['OpUnit'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': 'Area2024'})

    baseOp = FUCA[['OpUnit']].drop_duplicates()
    
    BalancoAnt = baseOp.merge(GAnt2020, on='OpUnit', how='left')
    BalancoAnt = BalancoAnt.merge(GAnt2024, on='OpUnit', how='left')
    BalancoAnt[['Area2020', 'Area2024']] = BalancoAnt[['Area2020', 'Area2024']].fillna(0)
    
    BalancoAnt['ReIBGE'] = "Antrópico"
    BalancoAnt['Ganho'] = 0.0
    BalancoAnt['Ganho_pct'] = np.nan
    BalancoAnt['Perda'] = 0.0
    BalancoAnt['Perda_pct'] = np.nan

    # ---- 3) linha Total por OpUnit
    BalancoTot = FUCA.groupby(['OpUnit'], as_index=False)['Area_ha'].sum().rename(columns={'Area_ha': 'Area2020'})
    BalancoTot['Area2024'] = BalancoTot['Area2020']  # Total da OpUnit não muda

    GGanhoTot = BalancoNat.groupby(['OpUnit'], as_index=False)['Ganho'].sum()
    GPerdaTot = BalancoNat.groupby(['OpUnit'], as_index=False)['Perda'].sum()

    BalancoTot = BalancoTot.merge(GGanhoTot, on='OpUnit', how='left')
    BalancoTot = BalancoTot.merge(GPerdaTot, on='OpUnit', how='left')
    BalancoTot[['Ganho', 'Perda']] = BalancoTot[['Ganho', 'Perda']].fillna(0)

    BalancoTot['Ganho_pct'] = np.where(BalancoTot['Area2020'] > 0, BalancoTot['Ganho'] / BalancoTot['Area2020'], 0)
    BalancoTot['Perda_pct'] = np.where(BalancoTot['Area2020'] > 0, BalancoTot['Perda'] / BalancoTot['Area2020'], 0)
    BalancoTot['ReIBGE'] = "Total"

    # ---- 4) padronizar nomes e juntar tudo
    rename_cols = {
        'ReIBGE': 'Classe', 'Area2020': 'Area_2020', 'Area2024': 'Area_2024'
    }
    
    BalancoNat = BalancoNat.rename(columns=rename_cols)
    BalancoAnt = BalancoAnt.rename(columns=rename_cols)
    BalancoTot = BalancoTot.rename(columns=rename_cols)

    cols_order = ['OpUnit', 'Classe', 'Area_2020', 'Ganho', 'Ganho_pct', 'Perda', 'Perda_pct', 'Area_2024']
    
    SaidaBalanco = pd.concat([
        BalancoNat[cols_order],
        BalancoAnt[cols_order],
        BalancoTot[cols_order]
    ], ignore_index=True)

    # Ordenação customizada: Naturais (1), Antrópico (2), Total (3)
    def class_order(c):
        if c == "Antrópico": return 2
        elif c == "Total": return 3
        return 1

    SaidaBalanco['ordClasse'] = SaidaBalanco['Classe'].apply(class_order)
    SaidaBalanco = SaidaBalanco.sort_values(by=['OpUnit', 'ordClasse', 'Classe']).drop(columns=['ordClasse'])

    # Exportar arquivo
    SaidaBalanco.to_csv('output/Saida_balanco_natural.csv', 
                        index=False,
                        float_format='%.2f',
                        sep=';',
                        decimal='.'
                        )
    print('Tabela de balanço gerada com sucesso.')

if __name__ == "__main__":
    main()

print("\n[OK] Tabelas GRI Geradas!")