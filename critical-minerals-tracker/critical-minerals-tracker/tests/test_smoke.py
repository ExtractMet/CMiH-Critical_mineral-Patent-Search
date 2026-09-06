"""Smoke + unit tests. Run: pytest -q"""
from __future__ import annotations

import pandas as pd

from cmtracker import analytics as A
from cmtracker import store as S
from cmtracker.connectors import OpenAlexClient, PatentsViewClient, _deinvert_abstract
from cmtracker.seed_data import build_corpus
from cmtracker.taxonomy import CRITICAL_MINERALS, classify_text


def test_thirty_minerals():
    assert len(CRITICAL_MINERALS) == 30


def test_classifier():
    minerals, domains = classify_text(
        "Hydrometallurgical recovery of lithium and cobalt from spent lithium-ion batteries"
    )
    assert "Lithium" in minerals and "Cobalt" in minerals
    assert "Recycling & Urban Mining" in domains
    assert "Extractive Metallurgy" in domains


def test_corpus_deterministic():
    a = build_corpus()
    b = build_corpus()
    assert len(a) == len(b) > 400
    assert [r["id"] for r in a] == [r["id"] for r in b]  # deterministic


def test_dataframe_and_filters():
    df = S.load_sample_df()
    assert not df.empty
    assert df["minerals"].apply(len).min() >= 1  # every row on-topic
    li = S.apply_filters(df, minerals=["Lithium"])
    assert not li.empty
    assert li["minerals"].apply(lambda xs: "Lithium" in xs).all()


def test_analytics_pipeline():
    df = S.load_sample_df()
    h = A.headline(df)
    assert h["total"] == len(df) and h["patents"] + h["research"] == h["total"]
    assert not A.filings_by_year(df).empty
    assert not A.mineral_domain_matrix(df).empty
    em = A.emerging(df, "domains")
    assert not em.empty and "growth_pct" in em.columns
    gap = A.india_gap(df)
    assert len(gap) == 30 and gap["priority_gap"].notna().all()


def test_india_flag_present():
    df = S.load_sample_df()
    assert df["is_india"].sum() > 0


def test_openalex_normalize():
    work = {
        "id": "https://openalex.org/W123", "doi": "https://doi.org/10.1/x",
        "title": "Recovery of rare earth elements from monazite by solvent extraction",
        "publication_year": 2023, "publication_date": "2023-05-01",
        "cited_by_count": 7, "open_access": {"is_oa": True},
        "abstract_inverted_index": {"Rare": [0], "earth": [1], "recovery": [2]},
        "authorships": [{"author": {"display_name": "A Kumar"},
                         "institutions": [{"display_name": "IIT Madras", "country_code": "IN"}]}],
        "concepts": [{"display_name": "Rare earth element"}],
    }
    rec = OpenAlexClient._normalize(work)
    assert rec["record_type"] == "Research"
    assert rec["country"] == "IN" and rec["is_india"] is True
    assert "REE" in rec["minerals"]
    assert rec["citations"] == 7


def test_patentsview_normalize():
    pat = {
        "patent_id": "11111111",
        "patent_title": "Recycling of cobalt and nickel from spent lithium-ion batteries",
        "patent_abstract": "A hydrometallurgical process ...",
        "patent_date": "2022-08-09",
        "assignees": [{"assignee_organization": "Redwood Materials", "assignee_country": "US"}],
        "inventors": [{"inventor_name_last": "Straubel"}],
        "cpc_current": [{"cpc_group_id": "C22B"}],
    }
    rec = PatentsViewClient._normalize(pat)
    assert rec["record_type"] == "Patent" and rec["source_db"] == "PatentsView"
    assert "Cobalt" in rec["minerals"] and "Recycling & Urban Mining" in rec["domains"]
    assert rec["url"].endswith("US11111111")


def test_deinvert():
    assert _deinvert_abstract({"hello": [0], "world": [1]}) == "hello world"
    assert _deinvert_abstract(None) == ""


def test_csv_export():
    df = S.load_sample_df().head(20)
    blob = S.to_csv_bytes(df)
    assert b"title" in blob and len(blob) > 100
