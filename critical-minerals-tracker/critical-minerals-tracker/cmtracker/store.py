"""
Data store / access layer.

Turns raw records (live connectors or bundled sample corpus) into a tidy pandas
DataFrame, applies the global sidebar filters, and provides small utilities
(export, watchlist alert logic).
"""

from __future__ import annotations

import io

import pandas as pd

from .schema import COLUMNS
from .seed_data import build_corpus


def records_to_df(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records, columns=COLUMNS)
    if df.empty:
        return df
    # normalize dtypes
    for c in ("minerals", "domains", "orgs", "people", "codes"):
        df[c] = df[c].apply(lambda v: v if isinstance(v, list) else ([] if pd.isna(v) else [v]))
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["citations"] = pd.to_numeric(df["citations"], errors="coerce").fillna(0).astype(int)
    df["is_india"] = df["is_india"].astype(bool)
    # drop rows we couldn't classify at all (no mineral) to keep the corpus on-topic
    df = df[df["minerals"].apply(len) > 0].reset_index(drop=True)
    return df


def load_sample_df() -> pd.DataFrame:
    return records_to_df(build_corpus())


def apply_filters(
    df: pd.DataFrame,
    minerals: list[str] | None = None,
    domains: list[str] | None = None,
    countries: list[str] | None = None,
    record_types: list[str] | None = None,
    year_range: tuple[int, int] | None = None,
    text: str | None = None,
) -> pd.DataFrame:
    d = df
    if minerals:
        d = d[d["minerals"].apply(lambda xs: any(m in xs for m in minerals))]
    if domains:
        d = d[d["domains"].apply(lambda xs: any(x in xs for x in domains))]
    if countries:
        d = d[d["country"].isin(countries)]
    if record_types:
        d = d[d["record_type"].isin(record_types)]
    if year_range:
        lo, hi = year_range
        d = d[(d["year"] >= lo) & (d["year"] <= hi)]
    if text:
        t = text.lower()
        d = d[
            d["title"].str.lower().str.contains(t, na=False)
            | d["abstract"].str.lower().str.contains(t, na=False)
            | d["org"].str.lower().str.contains(t, na=False)
        ]
    return d.reset_index(drop=True)


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    out = df.copy()
    for c in ("minerals", "domains", "orgs", "people", "codes"):
        out[c] = out[c].apply(lambda xs: "; ".join(map(str, xs)) if isinstance(xs, list) else xs)
    buf = io.StringIO()
    out.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def new_since(df: pd.DataFrame, cutoff_year: int) -> pd.DataFrame:
    """Watchlist alert: records at/after a cutoff year, newest first."""
    d = df[df["year"] >= cutoff_year]
    return d.sort_values(["year", "citations"], ascending=False).reset_index(drop=True)
