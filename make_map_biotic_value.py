import sys
import os
from pathlib import Path

import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterio.warp import reproject
from rasterio.enums import Resampling
import yaml

from fuca.functions import clip_raster, get_raster_band
from biotic_value import (
    apply_condition,
    load_biotic_coefficients,
    map_biotic_value,
    preserve_condition_values,
    write_raster,
)


def format_path(template: str, *, area: str, year: int) -> str:
    return template.format(AREA=area, YEAR=year, END_YEAR=year, BASE_YEAR=year)


def clip_with_fuca(
    raster_path: str, shape_path: str, tmp_path: str, final_name: str
) -> str:
    """Recorta e alinha o shapefile operacional usando o helper FUCA."""
    Path(tmp_path).mkdir(parents=True, exist_ok=True)
    tmp_dir = str(Path(tmp_path)) + os.sep
    return clip_raster(
        raster_path=raster_path,
        shp_path=shape_path,
        tmp_path=tmp_dir,
        final_name=final_name,
        all_touched=False,
    )


def read_condition_on_grid(condition_path: str, reference_path: str) -> tuple[np.ndarray, int | float | None]:
    """Lê a condição reprojetada para a grade recortada do MapBiomas."""
    with rasterio.open(reference_path) as reference, rasterio.open(condition_path) as source:
        condition = np.full(reference.shape, source.nodata if source.nodata is not None else 0, dtype=np.float32)
        reproject(
            source=source.read(1),
            destination=condition,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata,
            dst_transform=reference.transform,
            dst_crs=reference.crs,
            dst_nodata=source.nodata if source.nodata is not None else 0,
            resampling=Resampling.nearest,
        )
        return condition, source.nodata


def read_mask_on_grid(mask_path: str, reference_path: str) -> np.ndarray:
    """Lê um raster-máscara na grade do MapBiomas recortado."""
    with rasterio.open(reference_path) as reference, rasterio.open(mask_path) as source:
        mask_data = np.zeros(reference.shape, dtype=np.float32)
        reproject(
            source=source.read(1),
            destination=mask_data,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata,
            dst_transform=reference.transform,
            dst_crs=reference.crs,
            dst_nodata=0,
            resampling=Resampling.nearest,
        )
        return mask_data


def assert_aligned(reference_path: str, other_path: str) -> None:
    with rasterio.open(reference_path) as reference, rasterio.open(other_path) as other:
        if (
            reference.shape != other.shape
            or reference.transform != other.transform
            or reference.crs != other.crs
        ):
            raise ValueError(
                f"Raster desalinhado: {other_path}. "
                "Dimensão, transformação e CRS devem coincidir com o MapBiomas."
            )


def rasterize_rad_shape(shape_path: str, reference_path: str) -> np.ndarray:
    """Rasteriza o shape RAD diretamente no grid do MapBiomas."""
    path = Path(shape_path)
    if not path.is_file():
        raise FileNotFoundError(f"Shape de RAD não encontrado: {path}")

    with rasterio.open(reference_path) as reference:
        reference_crs = reference.crs
        shape = reference.shape
        transform = reference.transform

    shapes = gpd.read_file(path)
    if shapes.empty:
        raise ValueError(f"Shape de RAD vazio: {path}")
    if shapes.crs is None:
        raise ValueError(f"Shape de RAD sem CRS definido: {path}")
    if reference_crs is None:
        raise ValueError(f"MapBiomas sem CRS definido: {reference_path}")

    shapes = shapes.to_crs(reference_crs)
    return rasterize(
        ((geometry, 1) for geometry in shapes.geometry if geometry is not None),
        out_shape=shape,
        transform=transform,
        fill=0,
        dtype="uint8",
        all_touched=False,
    )


def main() -> None:
    with open("config.yaml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    paths, data = config["Paths"], config["Data"]
    area, year = data["area"], data["end_year"]

    lulc_path = format_path(paths["lulc_path"], area=area, year=year)
    condition_path = format_path(paths["condition_map_file_end"], area=area, year=year)
    shape_path = paths["shp_file"].format(AREA=area)
    tmp_path = paths["tmp_path"]
    lulc_path = clip_with_fuca(
        lulc_path, shape_path, tmp_path, f"mapbiomas_{area}_{year}.tif"
    )
    coefficients = load_biotic_coefficients(
        format_path(paths["biotic_value_table"], area=area, year=year)
    )
    lulc, lulc_nodata = get_raster_band(lulc_path)
    condition, condition_nodata = read_condition_on_grid(condition_path, lulc_path)

    secondary_vegetation_mask = None
    if data.get("secondary_vegetation_mask", True):
        secondary_path = format_path(paths["sec_veg_map_file"], area=area, year=year)
        secondary_path = clip_with_fuca(
            secondary_path,
            shape_path,
            tmp_path,
            f"sec_veg_{area}_{year}.tif",
        )
        secondary_vegetation_mask = read_mask_on_grid(secondary_path, lulc_path) > 0

    rad_shape_path = paths.get("rad_shape_file", "")
    rad = None
    rad_nodata = None
    if rad_shape_path:
        rad = rasterize_rad_shape(rad_shape_path, lulc_path)
        rad_nodata = 0
    rad_pixels = (rad != rad_nodata) & (rad != 0) if rad is not None else None

    bv, valid = map_biotic_value(
        lulc,
        coefficients,
        nodata=lulc_nodata,
        nodata_classes={int(class_id) for class_id in data.get("lulc_nodata_classes", [0])},
        rad=rad,
        rad_nodata=rad_nodata,
        rad_value=float(data.get("rad_bv", 0.2083)),
    )
    bv_map_valid = valid.copy()
    if secondary_vegetation_mask is not None:
        bv_map_valid[secondary_vegetation_mask] = False

    bv_scale = float(data.get("biotic_value_scale", 100.0))
    if bv_scale <= 0:
        raise ValueError("biotic_value_scale deve ser maior que zero.")
    bv *= bv_scale

    bvfinal = apply_condition(
        bv,
        condition,
        valid=valid,
        condition_nodata=condition_nodata,
        condition_scale=float(data.get("condition_scale", 100.0)),
        nodata=float(data.get("biotic_value_nodata", -9999)),
    )
    if secondary_vegetation_mask is not None:
        bvfinal = preserve_condition_values(
            bvfinal,
            condition,
            secondary_vegetation_mask,
            condition_nodata=condition_nodata,
        )

    output_dir = Path(paths["out_dir"])
    nodata = float(data.get("biotic_value_nodata", -9999))
    write_raster(
        str(output_dir / f"map_biotic_value_{area}_{year}.tif"),
        lulc_path,
        np.where(bv_map_valid, bv, nodata),
        nodata,
        "Valor biótico por classe MapBiomas",
    )
    write_raster(
        str(output_dir / f"map_biotic_value_final_{area}_{year}.tif"),
        lulc_path,
        bvfinal,
        nodata,
        "Valor biótico final (BV x condição)",
    )
    print(f"[OK] Mapas de BV gerados para {area}/{year}.")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, KeyError) as error:
        print(f"[ERRO] {error}", file=sys.stderr)
        raise
