"""
fetch_live.py  --  Live evidence-layer fetcher for the CMiH-2026 pegmatite MPM pipeline
========================================================================================

Turns a bounding box into an aligned stack of GeoTIFF evidence rasters, pulled live
from the **Microsoft Planetary Computer** STAC API (free, no API key):

  * Copernicus GLO-30 DEM   (collection ``cop-dem-glo-30``)  -> elevation + terrain derivatives
  * Sentinel-2 L2A          (collection ``sentinel-2-l2a``)  -> pegmatite alteration band ratios

The output is a folder of single-band GeoTIFFs, all reprojected to a common CRS/grid,
plus a ``manifest.json`` describing them. This folder is exactly what
``adapters.RealDataLoader`` already ingests -- so the workflow becomes:

    live STAC  ->  fetch_live.py  ->  folder of aligned GeoTIFFs  ->  RealDataLoader  ->  MPM pipeline

i.e. this module *produces* the local files the existing loader consumes. It does not
change the pipeline; it feeds it.

--------------------------------------------------------------------------------------
WHY THESE LAYERS (mineral-system / spectral rationale)
--------------------------------------------------------------------------------------
LCT (Li-Cs-Ta) pegmatites and their alteration halos are mapped from Sentinel-2 mainly
via iron-oxide and clay/AlOH (sericite-muscovite) ratios, with a vegetation mask to
suppress false positives (Cardoso-Fernandes et al. 2019, 2020; Gemusse et al. 2019).
The shoulder-ratio construction -- band(s) on the flanks of an absorption feature over
the band in the feature -- is the standard formulation. Implemented here:

  iron_oxide  = B04 / B02            ferric iron / gossan (red over blue)
  ferrous     = B12 / B08            ferrous iron / mafic index (SWIR2 over NIR)
  aloh_clay   = B11 / B12            AlOH ~2200 nm: sericite/muscovite/clay -> the key halo
  laterite    = B11 / B08            clay+iron laterite/regolith context
  ndvi        = (B08 - B04)/(B08+B04)  vegetation -- used as a mask/penalty, not a target

Terrain layers from the DEM (resistant pegmatite bodies can stand out by differential
erosion, so local highs / roughness are weak positive evidence):

  slope_deg   surface slope in degrees
  tpi         topographic position index (centre minus neighbourhood mean)
  roughness   local standard deviation of elevation

All ratios are computed on a robustly-normalised (2-98 pct clipped) 0-1 scale in the
convenience ``pegmatite_favorability`` composite, but each raw evidence raster is also
written so the trained MPM model does its own weighting rather than trusting a fixed
recipe.

--------------------------------------------------------------------------------------
NETWORK REQUIREMENTS
--------------------------------------------------------------------------------------
Reads Cloud-Optimized GeoTIFFs directly over HTTPS (GDAL /vsicurl/) from
``*.blob.core.windows.net`` after signing with the ``planetary-computer`` package, and
queries ``planetarycomputer.microsoft.com``. Run this on a machine with open internet.
(It will NOT run inside a sandbox whose egress is restricted to PyPI/GitHub.)

    pip install pystac-client planetary-computer rasterio numpy

--------------------------------------------------------------------------------------
USAGE
--------------------------------------------------------------------------------------
CLI (Marlagalla-Mandya Li belt, Karnataka -- adjust bbox to your AOI):

    python fetch_live.py \
        --bbox 76.75 12.45 77.05 12.75 \
        --start 2023-11-01 --end 2024-05-31 \
        --res 20 --max-cloud 15 --out data/live_marlagalla

Then point the pipeline at it:

    from adapters import RealDataLoader
    loader = RealDataLoader("data/live_marlagalla")     # reads the GeoTIFFs written here

Python:

    from fetch_live import build_evidence_stack
    manifest = build_evidence_stack(
        bbox=(76.75, 12.45, 77.05, 12.75),
        date_range=("2023-11-01", "2024-05-31"),
        out_dir="data/live_marlagalla",
        target_res=20.0, max_cloud=15.0,
    )
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# ----------------------------------------------------------------------------------
# Optional heavy deps are imported lazily inside the fetch functions so that the pure
# numpy core (and its tests) run with numpy alone.
# ----------------------------------------------------------------------------------

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
DEM_COLLECTION = "cop-dem-glo-30"
S2_COLLECTION = "sentinel-2-l2a"

# Sentinel-2 L2A asset keys on Planetary Computer (surface reflectance, scaled 0-10000).
S2_BANDS = ("B02", "B03", "B04", "B08", "B11", "B12")
S2_SCL = "SCL"  # scene classification layer, for cloud/shadow masking
S2_REFL_SCALE = 1.0e-4  # DN -> reflectance

# SCL classes to drop from median composites (cloud shadow / clouds / cirrus / snow).
SCL_MASK_CLASSES = (3, 8, 9, 10, 11)


# ==================================================================================
#  PURE NUMPY CORE  (no rasterio / STAC -- fully unit-testable offline)
# ==================================================================================

def safe_ratio(a: np.ndarray, b: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Elementwise a/b that never returns inf/nan from a zero denominator.

    Denominator is floored to ``eps`` in magnitude (sign-preserving). NaNs in the
    inputs propagate as NaN (caller decides how to treat them).
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    denom = np.where(np.abs(b) < eps, np.sign(b) * eps + (b == 0) * eps, b)
    return a / denom


def ndvi(nir: np.ndarray, red: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Normalised Difference Vegetation Index in [-1, 1]. Dense vegetation -> ~+1."""
    nir = np.asarray(nir, dtype=np.float64)
    red = np.asarray(red, dtype=np.float64)
    denom = nir + red
    denom = np.where(np.abs(denom) < eps, eps, denom)
    out = (nir - red) / denom
    return np.clip(out, -1.0, 1.0)


def iron_oxide_ratio(b04: np.ndarray, b02: np.ndarray) -> np.ndarray:
    """Ferric-iron / gossan proxy: red over blue. Higher over iron-oxide-stained ground."""
    return safe_ratio(b04, b02)


def ferrous_ratio(b12: np.ndarray, b08: np.ndarray) -> np.ndarray:
    """Ferrous-iron / mafic proxy: SWIR2 over NIR."""
    return safe_ratio(b12, b08)


def aloh_clay_ratio(b11: np.ndarray, b12: np.ndarray) -> np.ndarray:
    """AlOH (~2200 nm) sericite/muscovite/clay proxy: SWIR1 over SWIR2.

    This is the alteration-halo discriminator most diagnostic of LCT pegmatite
    footprints in the Sentinel-2 literature.
    """
    return safe_ratio(b11, b12)


def laterite_ratio(b11: np.ndarray, b08: np.ndarray) -> np.ndarray:
    """Clay+iron regolith/laterite context: SWIR1 over NIR."""
    return safe_ratio(b11, b08)


def robust_minmax_norm(a: np.ndarray, lo_pct: float = 2.0, hi_pct: float = 98.0
                       ) -> np.ndarray:
    """Scale to [0, 1] using percentile clipping so a few outliers don't crush the range.

    NaNs are ignored for the percentile estimate and preserved in the output.
    A flat array maps to all-zeros.
    """
    a = np.asarray(a, dtype=np.float64)
    finite = a[np.isfinite(a)]
    if finite.size == 0:
        return np.zeros_like(a)
    lo = np.percentile(finite, lo_pct)
    hi = np.percentile(finite, hi_pct)
    if not np.isfinite(hi - lo) or (hi - lo) < 1e-12:
        out = np.zeros_like(a)
        out[~np.isfinite(a)] = np.nan
        return out
    out = (a - lo) / (hi - lo)
    out = np.clip(out, 0.0, 1.0)
    out[~np.isfinite(a)] = np.nan
    return out


def pegmatite_favorability(b02, b03, b04, b08, b11, b12,
                           w_clay: float = 0.5, w_iron: float = 0.3,
                           w_veg: float = 0.2) -> np.ndarray:
    """Convenience 0-1 spectral favorability composite.

    High AlOH/clay + moderate iron-oxide + low vegetation. This is a *transparent
    default* only; the MPM model should ideally weight the raw ratios itself.
    """
    clay = robust_minmax_norm(aloh_clay_ratio(b11, b12))
    iron = robust_minmax_norm(iron_oxide_ratio(b04, b02))
    veg = robust_minmax_norm(ndvi(b08, b04))  # 0..1 where 1 = most vegetated
    fav = w_clay * clay + w_iron * iron - w_veg * veg
    return robust_minmax_norm(fav)


# --- terrain derivatives -----------------------------------------------------------

def slope_degrees(dem: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """Slope in degrees from a 2-D elevation grid via central differences.

    ``dx``/``dy`` are the ground cell sizes (metres) in x (columns) and y (rows).
    Edges use one-sided gradients (numpy default). A planar ramp returns a constant
    slope equal to atan of its true gradient.
    """
    dem = np.asarray(dem, dtype=np.float64)
    gy, gx = np.gradient(dem, dy, dx)  # np.gradient returns d/drow, d/dcol
    grad = np.hypot(gx, gy)
    return np.degrees(np.arctan(grad))


def _neighbourhood_stat(dem: np.ndarray, size: int, stat: str) -> np.ndarray:
    """Moving-window mean or std with a square window of odd side ``size`` (edge-reflected)."""
    if size % 2 == 0:
        raise ValueError("window size must be odd")
    dem = np.asarray(dem, dtype=np.float64)
    r = size // 2
    padded = np.pad(dem, r, mode="reflect")
    # Build the stack of shifted windows and reduce -- clear and dependency-free.
    acc = np.zeros_like(dem)
    acc_sq = np.zeros_like(dem)
    n = size * size
    H, W = dem.shape
    for i in range(size):
        for j in range(size):
            win = padded[i:i + H, j:j + W]
            acc += win
            acc_sq += win * win
    mean = acc / n
    if stat == "mean":
        return mean
    if stat == "std":
        var = np.maximum(acc_sq / n - mean * mean, 0.0)
        return np.sqrt(var)
    raise ValueError(stat)


def tpi(dem: np.ndarray, size: int = 5) -> np.ndarray:
    """Topographic Position Index: centre elevation minus neighbourhood mean.

    Positive on local highs (ridges/knobs), negative in depressions.
    """
    return np.asarray(dem, dtype=np.float64) - _neighbourhood_stat(dem, size, "mean")


def roughness(dem: np.ndarray, size: int = 5) -> np.ndarray:
    """Local terrain roughness: standard deviation of elevation in a moving window."""
    return _neighbourhood_stat(dem, size, "std")


# ==================================================================================
#  GRID / CRS HELPERS
# ==================================================================================

def utm_epsg_for(lon: float, lat: float) -> int:
    """Return the EPSG code of the UTM zone containing (lon, lat). WGS84 UTM N/S."""
    zone = int(math.floor((lon + 180.0) / 6.0) % 60) + 1
    return (32600 if lat >= 0 else 32700) + zone


def _target_grid(bbox_ll: Tuple[float, float, float, float], dst_epsg: int,
                 res: float):
    """Compute (transform, width, height) for a regular grid covering ``bbox_ll``
    (min_lon, min_lat, max_lon, max_lat) in the destination CRS at ``res`` metres."""
    from rasterio.warp import transform_bounds
    from rasterio.transform import from_origin

    min_lon, min_lat, max_lon, max_lat = bbox_ll
    xmin, ymin, xmax, ymax = transform_bounds(
        "EPSG:4326", f"EPSG:{dst_epsg}", min_lon, min_lat, max_lon, max_lat, densify_pts=21
    )
    # snap outward to res
    xmin = math.floor(xmin / res) * res
    ymin = math.floor(ymin / res) * res
    xmax = math.ceil(xmax / res) * res
    ymax = math.ceil(ymax / res) * res
    width = int(round((xmax - xmin) / res))
    height = int(round((ymax - ymin) / res))
    transform = from_origin(xmin, ymax, res, res)
    return transform, width, height


def _gdal_env():
    """rasterio.Env tuned for reading many remote COGs efficiently."""
    import rasterio
    return rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        GDAL_HTTP_MULTIRANGE="YES",
        GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
        VSI_CACHE="TRUE",
    )


def _reproject_href_to_grid(href: str, dst_crs: str, transform, width: int, height: int,
                            resampling: str = "bilinear",
                            src_nodata: Optional[float] = None) -> np.ndarray:
    """Warp a single-band remote raster (COG over /vsicurl/) onto the target grid.

    Returns a float64 array of shape (height, width) with NaN where no data.
    """
    import rasterio
    from rasterio.warp import reproject, Resampling

    rs = getattr(Resampling, resampling)
    dst = np.full((height, width), np.nan, dtype=np.float64)
    with rasterio.open(href) as src:
        arr = src.read(1).astype(np.float64)
        nodata = src.nodata if src_nodata is None else src_nodata
        if nodata is not None:
            arr = np.where(arr == nodata, np.nan, arr)
        reproject(
            source=arr,
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=rs,
            src_nodata=np.nan,
            dst_nodata=np.nan,
        )
    return dst


def _write_geotiff(path: str, arr: np.ndarray, dst_crs: str, transform,
                   nodata: float = np.nan) -> None:
    import rasterio
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "count": 1,
        "height": arr.shape[0],
        "width": arr.shape[1],
        "crs": dst_crs,
        "transform": transform,
        "nodata": nodata,
        "compress": "deflate",
        "predictor": 2,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype(np.float32), 1)


# ==================================================================================
#  STAC FETCH
# ==================================================================================

def _open_catalog():
    import pystac_client
    import planetary_computer
    return pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)


def fetch_dem(bbox_ll, out_dir: str, dst_epsg: int, res: float) -> Dict[str, str]:
    """Fetch + mosaic Copernicus GLO-30 DEM over the AOI and write elevation + derivatives.

    Returns {layer_name: filepath}.
    """
    import planetary_computer

    transform, width, height = _target_grid(bbox_ll, dst_epsg, res)
    dst_crs = f"EPSG:{dst_epsg}"
    catalog = _open_catalog()
    search = catalog.search(collections=[DEM_COLLECTION], bbox=list(bbox_ll))
    items = list(search.items())
    if not items:
        raise RuntimeError(f"No {DEM_COLLECTION} tiles found for bbox {bbox_ll}")

    # Warp each intersecting tile onto the grid, then mosaic by nan-aware averaging.
    dst_crs_str = dst_crs
    stack = np.full((len(items), height, width), np.nan, dtype=np.float64)
    with _gdal_env():
        for k, item in enumerate(items):
            asset = item.assets.get("data") or next(iter(item.assets.values()))
            href = planetary_computer.sign(asset.href)
            stack[k] = _reproject_href_to_grid(
                href, dst_crs_str, transform, width, height, resampling="bilinear"
            )
    dem = np.nanmean(stack, axis=0)

    dx = dy = float(res)
    layers = {
        "dem": dem,
        "slope_deg": slope_degrees(dem, dx, dy),
        "tpi": tpi(dem, size=5),
        "roughness": roughness(dem, size=5),
    }
    paths = {}
    for name, arr in layers.items():
        p = os.path.join(out_dir, f"{name}.tif")
        _write_geotiff(p, arr, dst_crs, transform)
        paths[name] = p
    return paths


def fetch_sentinel2(bbox_ll, date_range, out_dir: str, dst_epsg: int, res: float,
                    max_cloud: float = 20.0, max_scenes: int = 8,
                    method: str = "median") -> Dict[str, str]:
    """Fetch Sentinel-2 L2A over the AOI/date range and write alteration evidence rasters.

    method="median" builds an SCL-masked per-band median composite over the least-cloudy
    scenes (robust to residual cloud/shadow). method="best" uses the single least-cloudy
    scene. Returns {layer_name: filepath}.
    """
    import planetary_computer

    transform, width, height = _target_grid(bbox_ll, dst_epsg, res)
    dst_crs = f"EPSG:{dst_epsg}"
    catalog = _open_catalog()
    search = catalog.search(
        collections=[S2_COLLECTION],
        bbox=list(bbox_ll),
        datetime=f"{date_range[0]}/{date_range[1]}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
    )
    items = list(search.items())
    if not items:
        raise RuntimeError(
            f"No {S2_COLLECTION} scenes < {max_cloud}% cloud for bbox {bbox_ll} "
            f"in {date_range[0]}..{date_range[1]}. Loosen --max-cloud or widen dates."
        )
    items.sort(key=lambda it: it.properties.get("eo:cloud_cover", 100.0))
    if method == "best":
        items = items[:1]
    else:
        items = items[:max_scenes]

    # Read every needed band of every chosen scene onto the common grid, mask by SCL.
    band_stacks: Dict[str, List[np.ndarray]] = {b: [] for b in S2_BANDS}
    with _gdal_env():
        for item in items:
            signed = planetary_computer.sign(item)
            # cloud/shadow mask from SCL (nearest -- it's a class raster)
            scl = _reproject_href_to_grid(
                signed.assets[S2_SCL].href, dst_crs, transform, width, height,
                resampling="nearest",
            )
            bad = np.isin(np.rint(scl), SCL_MASK_CLASSES) | ~np.isfinite(scl)
            for b in S2_BANDS:
                refl = _reproject_href_to_grid(
                    signed.assets[b].href, dst_crs, transform, width, height,
                    resampling="bilinear",
                ) * S2_REFL_SCALE
                refl = np.where(bad, np.nan, refl)
                band_stacks[b].append(refl)

    reduce_fn = (lambda s: s[0]) if method == "best" else (
        lambda s: np.nanmedian(np.stack(s, axis=0), axis=0))
    B = {b: reduce_fn(band_stacks[b]) for b in S2_BANDS}
    b02, b03, b04, b08, b11, b12 = (B["B02"], B["B03"], B["B04"],
                                    B["B08"], B["B11"], B["B12"])

    layers = {
        "s2_iron_oxide": iron_oxide_ratio(b04, b02),
        "s2_ferrous": ferrous_ratio(b12, b08),
        "s2_aloh_clay": aloh_clay_ratio(b11, b12),
        "s2_laterite": laterite_ratio(b11, b08),
        "s2_ndvi": ndvi(b08, b04),
        "s2_pegmatite_favorability": pegmatite_favorability(b02, b03, b04, b08, b11, b12),
    }
    paths = {}
    for name, arr in layers.items():
        p = os.path.join(out_dir, f"{name}.tif")
        _write_geotiff(p, arr, dst_crs, transform)
        paths[name] = p
    return paths


# ==================================================================================
#  ORCHESTRATOR
# ==================================================================================

def build_evidence_stack(bbox, date_range, out_dir: str,
                         target_res: float = 20.0, dst_epsg: Optional[int] = None,
                         max_cloud: float = 20.0, max_scenes: int = 8,
                         s2_method: str = "median",
                         layers: Sequence[str] = ("dem", "s2")) -> dict:
    """Fetch the requested evidence layers, write aligned GeoTIFFs + manifest.json.

    Parameters
    ----------
    bbox : (min_lon, min_lat, max_lon, max_lat)  in WGS84 degrees.
    date_range : (start, end) ISO dates, for Sentinel-2.
    out_dir : output folder (created); RealDataLoader points here afterwards.
    target_res : output pixel size in metres (default 20 m -- SWIR-limited).
    dst_epsg : output CRS EPSG; default auto-UTM from the bbox centroid.
    layers : any of ("dem", "s2").
    """
    os.makedirs(out_dir, exist_ok=True)
    min_lon, min_lat, max_lon, max_lat = bbox
    if dst_epsg is None:
        dst_epsg = utm_epsg_for((min_lon + max_lon) / 2.0, (min_lat + max_lat) / 2.0)

    written: Dict[str, str] = {}
    if "dem" in layers:
        print(f"[dem] fetching {DEM_COLLECTION} ...", flush=True)
        written.update(fetch_dem(bbox, out_dir, dst_epsg, target_res))
    if "s2" in layers:
        print(f"[s2 ] fetching {S2_COLLECTION} ({s2_method}) ...", flush=True)
        written.update(fetch_sentinel2(bbox, date_range, out_dir, dst_epsg, target_res,
                                       max_cloud=max_cloud, max_scenes=max_scenes,
                                       method=s2_method))

    transform, width, height = _target_grid(bbox, dst_epsg, target_res)
    manifest = {
        "generated_utc": datetime.utcnow().isoformat() + "Z",
        "source": "Microsoft Planetary Computer STAC",
        "stac_url": STAC_URL,
        "bbox_wgs84": list(bbox),
        "date_range": list(date_range),
        "crs": f"EPSG:{dst_epsg}",
        "resolution_m": target_res,
        "grid": {"width": width, "height": height},
        "max_cloud_pct": max_cloud,
        "s2_method": s2_method,
        "layers": {name: os.path.basename(p) for name, p in written.items()},
        "band_ratio_refs": "Cardoso-Fernandes et al. 2019/2020; Gemusse et al. 2019",
    }
    mpath = os.path.join(out_dir, "manifest.json")
    with open(mpath, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"[ok ] wrote {len(written)} rasters + manifest to {out_dir}", flush=True)
    return manifest


# ==================================================================================
#  CLI
# ==================================================================================

def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Fetch Copernicus DEM + Sentinel-2 pegmatite evidence rasters "
                    "from Planetary Computer into an aligned GeoTIFF stack.")
    p.add_argument("--bbox", nargs=4, type=float, required=True,
                   metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
                   help="AOI bounding box in WGS84 degrees.")
    p.add_argument("--start", default="2023-11-01", help="Sentinel-2 start date (ISO).")
    p.add_argument("--end", default="2024-05-31", help="Sentinel-2 end date (ISO).")
    p.add_argument("--res", type=float, default=20.0, help="Output pixel size (m).")
    p.add_argument("--epsg", type=int, default=None, help="Output EPSG (default auto-UTM).")
    p.add_argument("--max-cloud", type=float, default=20.0, help="Max scene cloud %%.")
    p.add_argument("--max-scenes", type=int, default=8, help="Scenes in median composite.")
    p.add_argument("--s2-method", choices=("median", "best"), default="median")
    p.add_argument("--layers", nargs="+", default=["dem", "s2"], choices=["dem", "s2"])
    p.add_argument("--out", required=True, help="Output folder.")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    build_evidence_stack(
        bbox=tuple(args.bbox),
        date_range=(args.start, args.end),
        out_dir=args.out,
        target_res=args.res,
        dst_epsg=args.epsg,
        max_cloud=args.max_cloud,
        max_scenes=args.max_scenes,
        s2_method=args.s2_method,
        layers=tuple(args.layers),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
