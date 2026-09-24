"""Reclassificação de MapBiomas para valor biótico e aplicação da condição."""

from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


EXCLUDED_CLASSES = {60, 61, 62, 80}


def load_biotic_coefficients(path: str) -> dict[int, float]:
    """Carrega mapbiomas_id_bv.txt e remove as classes reservadas."""
    table_path = Path(path)
    if not table_path.is_file():
        raise FileNotFoundError(f"Tabela de BV não encontrada: {table_path}")

    table = pd.read_csv(table_path, sep=None, engine="python")
    table = table.rename(columns={"id_class": "mapbiomas_class"})
    required = {"mapbiomas_class", "bv"}
    missing = required - set(table.columns)
    if missing:
        raise ValueError(
            f"Tabela de BV sem as colunas obrigatórias: {', '.join(sorted(missing))}"
        )

    classes = pd.to_numeric(table["mapbiomas_class"], errors="coerce")
    values = pd.to_numeric(table["bv"], errors="coerce")
    if classes.isna().any() or values.isna().any():
        raise ValueError("Tabela de BV contém classe ou valor não numérico.")
    if (values < 0).any():
        raise ValueError("Tabela de BV contém valores negativos.")

    clean = pd.DataFrame({"class": classes.astype(int), "bv": values})
    clean = clean[~clean["class"].isin(EXCLUDED_CLASSES)]
    if clean["class"].duplicated().any():
        duplicated = sorted(clean.loc[clean["class"].duplicated(), "class"].unique())
        raise ValueError(f"Tabela de BV contém classes duplicadas: {duplicated}")
    return dict(zip(clean["class"], clean["bv"]))


def map_biotic_value(
    lulc: np.ndarray,
    coefficients: dict[int, float],
    *,
    nodata: int | float | None,
    nodata_classes: set[int] | None = None,
    rad: np.ndarray | None = None,
    rad_nodata: int | float | None = None,
    rad_value: float = 0.2083,
) -> tuple[np.ndarray, np.ndarray]:
    """Gera BV e máscara de pixels válidos a partir de um raster MapBiomas."""
    result = np.zeros(lulc.shape, dtype=np.float32)
    valid = np.ones(lulc.shape, dtype=bool)
    if nodata is not None:
        valid &= lulc != nodata
    if nodata_classes:
        valid &= ~np.isin(lulc, list(nodata_classes))

    known = np.zeros(lulc.shape, dtype=bool)
    for class_id, value in coefficients.items():
        pixels = lulc == class_id
        result[pixels] = value
        known |= pixels

    if rad is not None:
        if rad.shape != lulc.shape:
            raise ValueError("Raster de RAD não possui a mesma dimensão do MapBiomas.")
        rad_pixels = np.ones(rad.shape, dtype=bool)
        if rad_nodata is not None:
            rad_pixels &= rad != rad_nodata
        rad_pixels &= rad != 0
        result[rad_pixels] = rad_value
        known |= rad_pixels

    missing = valid & ~known
    if missing.any():
        classes = np.unique(lulc[missing]).tolist()
        raise ValueError(
            f"Classes MapBiomas sem BV (incluindo classes não configuradas): {classes}"
        )
    valid &= known
    return result, valid


def apply_condition(
    bv: np.ndarray,
    condition: np.ndarray,
    *,
    valid: np.ndarray,
    condition_nodata: int | float | None,
    condition_scale: float = 100.0,
    nodata: float = -9999.0,
) -> np.ndarray:
    """Calcula BVfinal = BV * condição."""
    if bv.shape != condition.shape or bv.shape != valid.shape:
        raise ValueError("BV, condição e máscara de validade precisam ter a mesma dimensão.")
    if condition_scale <= 0:
        raise ValueError("condition_scale deve ser maior que zero.")

    output = np.full(bv.shape, nodata, dtype=np.float32)
    condition_factor = condition.astype(np.float32) / condition_scale
    if condition_nodata is not None:
        condition_valid = condition != condition_nodata
    else:
        condition_valid = np.ones(condition.shape, dtype=bool)
    usable = valid & condition_valid
    output[usable] = bv[usable] * np.clip(condition_factor[usable], 0.0, 1.0)
    return output


def write_raster(path: str, template: str, data: np.ndarray, nodata: float, description: str) -> None:
    """Escreve um raster float32 usando o georreferenciamento do template."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(template) as source:
        profile = source.profile.copy()
        profile.update(dtype="float32", count=1, nodata=nodata, compress="lzw")
        with rasterio.open(output_path, "w", **profile) as destination:
            destination.set_band_description(1, description)
            destination.write(data.astype(np.float32), 1)
