"""
Offline unit tests for the pure-numpy core of fetch_live.py.

These verify the numerical/spectral math (the part that determines whether the evidence
layers are correct). The live STAC/COG fetch is machine-dependent (needs open internet)
and is not exercised here.

Run:  python test_fetch_core.py
"""
import numpy as np

import fetch_live as F


def _check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    assert cond, name


# ---------------------------------------------------------------------------
# safe_ratio
# ---------------------------------------------------------------------------
def test_safe_ratio_no_blowup():
    a = np.array([1.0, 2.0, 0.0, -3.0])
    b = np.array([0.0, 4.0, 0.0, 2.0])
    r = F.safe_ratio(a, b)
    _check("safe_ratio: finite everywhere (no inf/nan from zero denom)",
           np.all(np.isfinite(r)))
    _check("safe_ratio: correct where denom nonzero (2/4=0.5)",
           abs(r[1] - 0.5) < 1e-9)
    _check("safe_ratio: sign preserved (-3/2=-1.5)", abs(r[3] + 1.5) < 1e-9)


# ---------------------------------------------------------------------------
# NDVI
# ---------------------------------------------------------------------------
def test_ndvi_range_and_sign():
    nir = np.array([0.40, 0.05, 0.25])
    red = np.array([0.05, 0.40, 0.25])
    v = F.ndvi(nir, red)
    _check("ndvi: bounded in [-1,1]", np.all(v >= -1) and np.all(v <= 1))
    _check("ndvi: vegetation (NIR>>red) positive", v[0] > 0.5)
    _check("ndvi: bare/anti-veg (red>>NIR) negative", v[1] < -0.5)
    _check("ndvi: equal bands -> ~0", abs(v[2]) < 1e-9)


# ---------------------------------------------------------------------------
# alteration ratios: monotonic response in the intended direction
# ---------------------------------------------------------------------------
def test_iron_oxide_direction():
    # more red relative to blue -> larger ferric proxy
    b04 = np.array([0.10, 0.30])
    b02 = np.array([0.20, 0.10])
    r = F.iron_oxide_ratio(b04, b02)
    _check("iron_oxide: rises with red/blue", r[1] > r[0])


def test_aloh_clay_direction():
    # SWIR1 high, SWIR2 low (deep 2200nm AlOH absorption) -> larger clay proxy
    b11 = np.array([0.25, 0.30])
    b12 = np.array([0.24, 0.15])
    r = F.aloh_clay_ratio(b11, b12)
    _check("aloh_clay: rises as SWIR2 absorption deepens", r[1] > r[0])
    _check("aloh_clay: ~1 with no absorption feature", abs(r[0] - 25/24) < 1e-9)


# ---------------------------------------------------------------------------
# robust_minmax_norm
# ---------------------------------------------------------------------------
def test_robust_norm():
    a = np.linspace(0, 100, 101).astype(float)
    n = F.robust_minmax_norm(a)
    _check("robust_norm: in [0,1]", np.nanmin(n) >= 0 and np.nanmax(n) <= 1)
    _check("robust_norm: monotonic non-decreasing", np.all(np.diff(n) >= -1e-12))
    _check("robust_norm: flat array -> all zeros",
           np.allclose(F.robust_minmax_norm(np.full(50, 7.0)), 0.0))
    # NaNs preserved
    b = a.copy(); b[10] = np.nan
    nb = F.robust_minmax_norm(b)
    _check("robust_norm: NaN preserved", np.isnan(nb[10]))


def test_favorability_bounded():
    rng = np.random.default_rng(0)
    shp = (32, 32)
    bands = [rng.uniform(0.02, 0.5, shp) for _ in range(6)]
    fav = F.pegmatite_favorability(*bands)
    _check("favorability: in [0,1] ignoring NaN",
           np.nanmin(fav) >= 0 and np.nanmax(fav) <= 1)
    _check("favorability: shape preserved", fav.shape == shp)


# ---------------------------------------------------------------------------
# slope: flat and planar-ramp analytic checks
# ---------------------------------------------------------------------------
def test_slope_flat_and_ramp():
    flat = np.full((20, 20), 123.0)
    s = F.slope_degrees(flat, dx=30.0, dy=30.0)
    _check("slope: flat surface -> 0 deg", np.allclose(s, 0.0, atol=1e-9))

    # planar ramp: 1 m rise per 1 m east; with dx=1 the gradient is 1 -> 45 deg
    x = np.arange(50, dtype=float)
    ramp = np.tile(x, (50, 1))  # increases along columns (x/east)
    s2 = F.slope_degrees(ramp, dx=1.0, dy=1.0)
    _check("slope: 45-deg ramp interior -> 45 deg",
           abs(np.median(s2[2:-2, 2:-2]) - 45.0) < 1e-6)

    # gentler ramp: rise 10 m over 30 m cell -> atan(10/30)=18.43 deg
    ramp2 = np.tile(np.arange(50, dtype=float) * 10.0, (50, 1))
    s3 = F.slope_degrees(ramp2, dx=30.0, dy=30.0)
    _check("slope: atan(10/30)=18.43 deg ramp",
           abs(np.median(s3[2:-2, 2:-2]) - np.degrees(np.arctan(10/30))) < 1e-6)


# ---------------------------------------------------------------------------
# TPI: peak positive, pit negative, flat zero
# ---------------------------------------------------------------------------
def test_tpi_sign():
    dem = np.zeros((21, 21))
    dem[10, 10] = 10.0   # isolated peak
    t = F.tpi(dem, size=5)
    _check("tpi: isolated peak is positive", t[10, 10] > 0)

    dem2 = np.zeros((21, 21))
    dem2[10, 10] = -10.0  # isolated pit
    t2 = F.tpi(dem2, size=5)
    _check("tpi: isolated pit is negative", t2[10, 10] < 0)

    _check("tpi: flat surface ~0", np.allclose(F.tpi(np.full((15, 15), 5.0), 5), 0.0,
                                                atol=1e-9))


# ---------------------------------------------------------------------------
# roughness: flat zero, noisy > 0, and increases with amplitude
# ---------------------------------------------------------------------------
def test_roughness():
    flat = np.full((30, 30), 2.0)
    _check("roughness: flat -> 0", np.allclose(F.roughness(flat, 5), 0.0, atol=1e-9))

    rng = np.random.default_rng(1)
    low = rng.normal(0, 1.0, (60, 60))
    high = rng.normal(0, 5.0, (60, 60))
    rl = F.roughness(low, 5)[5:-5, 5:-5].mean()
    rh = F.roughness(high, 5)[5:-5, 5:-5].mean()
    _check("roughness: grows with elevation variance", rh > rl > 0)


# ---------------------------------------------------------------------------
# neighbourhood mean sanity (window must be odd; constant-add invariance of tpi)
# ---------------------------------------------------------------------------
def test_neighbourhood_and_invariance():
    try:
        F._neighbourhood_stat(np.zeros((5, 5)), size=4, stat="mean")
        even_ok = False
    except ValueError:
        even_ok = True
    _check("neighbourhood: rejects even window size", even_ok)

    rng = np.random.default_rng(2)
    dem = rng.normal(100, 3, (40, 40))
    t1 = F.tpi(dem, 5)
    t2 = F.tpi(dem + 500.0, 5)  # TPI is a high-pass filter -> constant offset invariant
    _check("tpi: invariant to constant elevation offset", np.allclose(t1, t2, atol=1e-9))


# ---------------------------------------------------------------------------
# UTM zone helper
# ---------------------------------------------------------------------------
def test_utm_epsg():
    # Chennai / Karnataka ~77E, ~12N -> UTM 43N = EPSG:32643
    _check("utm_epsg: 77E,12N -> 32643", F.utm_epsg_for(77.0, 12.5) == 32643)
    # southern hemisphere flips to 327xx
    _check("utm_epsg: southern hemi -> 327xx", F.utm_epsg_for(30.0, -20.0) // 100 == 327)


def run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    print(f"Running {len(fns)} test groups on fetch_live core\n" + "-" * 52)
    for fn in fns:
        fn()
    print("-" * 52)
    print("ALL CORE TESTS PASSED")


if __name__ == "__main__":
    run_all()
