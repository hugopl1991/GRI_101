import yaml

from utils import (
    build_column_names,
    carregar_dados,
    reclass_novo,
    gerar_tabelas_intermediarias,
    calcular_balanco,
)

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

OUT_G106 = PATHS['output_g106'].format(AREA=AREA)
OUT_G106B = PATHS['output_g106b'].format(AREA=AREA)
OUT_G107 = PATHS['output_g107'].format(AREA=AREA)
OUT_LULC_COND = PATHS['output_lulc_cond'].format(AREA=AREA)
OUT_BALANCE = PATHS['output_balance'].format(AREA=AREA)


def main():
    print("Iniciando processamento...")

    cols = build_column_names(BASE_YEAR, END_YEAR)

    # 1. Carregar os dados
    FUCA, Reclass_IBGE, Reclass_geral, Reclass_canga, Reclass_N4N5 = carregar_dados(
        FILE_TABLE, FILE_RECLASS, cols, SIZE_PIXEL
    )

    # 2. Reclassificar áreas
    dict_ibge = dict(zip(Reclass_IBGE['IBGE'], Reclass_IBGE['Reclass_IBGE']))
    FUCA['ReIBGE'] = FUCA['IBGE'].map(dict_ibge).fillna(FUCA['IBGE']).astype(str)

    FUCA[cols['relulc_base']] = reclass_novo(
        FUCA[cols['lulc_base']], FUCA['OpUnit'], FUCA['ReIBGE'],
        Reclass_geral, Reclass_N4N5, Reclass_canga, 'LULC', 'Reclass_LULC'
    )
    FUCA[cols['relulc_end']] = reclass_novo(
        FUCA[cols['lulc_end']], FUCA['OpUnit'], FUCA['ReIBGE'],
        Reclass_geral, Reclass_N4N5, Reclass_canga, 'LULC', 'Reclass_LULC'
    )

    # 3. Gerar tabelas intermediárias (106ai, 106b e 107ai)
    ant_base, ant_end = gerar_tabelas_intermediarias(
        FUCA, cols,
        path_out_106=OUT_G106,
        path_out_106b=OUT_G106B,
        path_out_107=OUT_G107,
        path_out_reclass=OUT_LULC_COND,
        sep=SEP,
        decimal=DECIMAL,
        float_format=FLOAT_FORMAT,
    )
    print("Tabelas intermediárias 106ai e 107ai exportadas.")

    # 4. Calcular balanço e exportar final
    SaidaBalanco = calcular_balanco(FUCA, cols, ant_base, ant_end)
    SaidaBalanco.to_csv(
        OUT_BALANCE,
        index=False,
        sep=SEP,
        decimal=DECIMAL,
        float_format=FLOAT_FORMAT,
    )

    print("Tabela de balanço gerada com sucesso.")


if __name__ == "__main__":
    main()
