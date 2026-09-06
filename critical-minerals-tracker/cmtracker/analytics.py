"""
Analytics engine.

Pure functions over a normalized pandas DataFrame (one row per record, with
list-valued `minerals` / `domains` columns). No Streamlit here, so everything
is unit-testable and reusable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .taxonomy import CRITICAL_MINERALS, DEPENDENCY_SCORE


# --------------------------------------------------------------------------- #
# Exploding list-columns
# --------------------------------------------------------------------------- #
def explode(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Explode a list-valued column (minerals / domains) to one row per value."""
    if df.empty:
        return df.assign(**{col: pd.Series(dtype=object)})
    e = df.explode(col)
    return e[e[col].notna()]


# --------------------------------------------------------------------------- #
# Headline metrics
# --------------------------------------------------------------------------- #
def headline(df: pd.DataFrame) -> dict:
    if df.empty:
        return dict(total=0, patents=0, research=0, india=0, india_share=0.0,
                    countries=0, orgs=0, latest_year=None)
    patents = int((df["record_type"] == "Patent").sum())
    research = int((df["record_type"] == "Research").sum())
    india = int(df["is_india"].sum())
    orgs = df["org"].dropna().nunique()
    return dict(
        total=len(df), patents=patents, research=research, india=india,
        india_share=round(100 * india / len(df), 1),
        countries=df["country"].dropna().nunique(),
        orgs=int(orgs),
        latest_year=int(df["year"].dropna().max()) if df["year"].notna().any() else None,
    )


# --------------------------------------------------------------------------- #
# Time series
# --------------------------------------------------------------------------- #
def filings_by_year(df: pd.DataFrame, split: str | None = None) -> pd.DataFrame:
    """Counts per year, optionally split by 'record_type' or 'country'."""
    d = df.dropna(subset=["year"]).copy()
    if d.empty:
        return pd.DataFrame(columns=["year", "count"])
    d["year"] = d["year"].astype(int)
    if split and split in d.columns:
        out = d.groupby(["year", split]).size().reset_index(name="count")
    else:
        out = d.groupby("year").size().reset_index(name="count")
    return out.sort_values("year")


def cagr(df: pd.DataFrame, start: int, end: int) -> float | None:
    d = df.dropna(subset=["year"])
    if d.empty:
        return None
    d = d[(d["year"] >= start) & (d["year"] <= end)]
    a = (d["year"] == start).sum()
    b = (d["year"] == end).sum()
    if a <= 0 or b <= 0 or end <= start:
        return None
    return round(100 * ((b / a) ** (1 / (end - start)) - 1), 1)


# --------------------------------------------------------------------------- #
# Landscape
# --------------------------------------------------------------------------- #
def mineral_domain_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot: minerals (rows) x domains (cols) counts. Powers the heatmap."""
    md = explode(explode(df, "minerals"), "domains")
    if md.empty:
        return pd.DataFrame()
    return (md.groupby(["minerals", "domains"]).size()
              .reset_index(name="count")
              .pivot(index="minerals", columns="domains", values="count")
              .fillna(0).astype(int))


def top_counts(df: pd.DataFrame, col: str, n: int = 12, explode_list: bool = False) -> pd.DataFrame:
    d = explode(df, col) if explode_list else df.dropna(subset=[col])
    if d.empty:
        return pd.DataFrame(columns=[col, "count"])
    return (d.groupby(col).size().reset_index(name="count")
              .sort_values("count", ascending=False).head(n))


# --------------------------------------------------------------------------- #
# Emerging-signal detection
# --------------------------------------------------------------------------- #
def emerging(df: pd.DataFrame, dimension: str = "domains",
             recent: int = 3, prior: int = 3, latest_year: int | None = None) -> pd.DataFrame:
    """
    Growth signal for each value of `dimension` (domains / minerals):
    compare activity in the last `recent` complete years vs the `prior` years
    before that. Returns growth ratio + share, sorted by momentum.
    """
    d = explode(df.dropna(subset=["year"]), dimension)
    if d.empty:
        return pd.DataFrame(columns=[dimension, "recent", "prior", "growth_pct", "recent_share"])
    d["year"] = d["year"].astype(int)
    ly = latest_year if latest_year is not None else int(d["year"].max())
    # use the last complete year as reference; treat ly as possibly partial
    ref = ly - 1
    recent_lo, recent_hi = ref - recent + 1, ref
    prior_lo, prior_hi = recent_lo - prior, recent_lo - 1

    rec = d[(d["year"] >= recent_lo) & (d["year"] <= recent_hi)]
    pri = d[(d["year"] >= prior_lo) & (d["year"] <= prior_hi)]
    rc = rec.groupby(dimension).size()
    pc = pri.groupby(dimension).size()
    idx = rc.index.union(pc.index)
    rc = rc.reindex(idx, fill_value=0)
    pc = pc.reindex(idx, fill_value=0)
    total_recent = rc.sum() or 1
    growth = ((rc + 1) / (pc + 1) - 1) * 100      # +1 smoothing
    out = pd.DataFrame({
        dimension: idx,
        "recent": rc.values,
        "prior": pc.values,
        "growth_pct": growth.round(0).astype(int).values,
        "recent_share": (100 * rc / total_recent).round(1).values,
    })
    return out.sort_values(["growth_pct", "recent"], ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# India self-reliance / gap analysis
# --------------------------------------------------------------------------- #
def india_gap(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each critical mineral: global vs India record counts, India share, and a
    composite 'priority gap' score = import-dependency  x  (low domestic IP).
    High score  ->  strategically important AND under-represented in Indian IP.
    """
    md = explode(df, "minerals")
    rows = []
    for m, meta in CRITICAL_MINERALS.items():
        sub = md[md["minerals"] == m]
        world = len(sub)
        india = int(sub["is_india"].sum())
        share = round(100 * india / world, 1) if world else 0.0
        dep = DEPENDENCY_SCORE[meta["dependency"]]
        # gap: high dependency, low india share  -> larger.  (share in %, 0..100)
        gap = round(dep * (1 - min(share, 100) / 100), 2)
        rows.append(dict(
            mineral=m, group=meta["group"], dependency=meta["dependency"],
            dep_score=dep, domestic=meta["domestic"],
            world=world, india=india, india_share=share,
            priority_gap=gap, note=meta["note"],
        ))
    out = pd.DataFrame(rows)
    return out.sort_values(["priority_gap", "dep_score"], ascending=False).reset_index(drop=True)


def india_orgs(df: pd.DataFrame, n: int = 12) -> pd.DataFrame:
    d = df[df["is_india"]]
    return top_counts(d, "org", n=n)
