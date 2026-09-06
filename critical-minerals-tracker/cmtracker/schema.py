"""
Normalized record schema.

Every source - patents (PatentsView / Espacenet) and research (OpenAlex) and the
bundled sample corpus - is mapped into this single flat dict shape so the
analytics and UI never care where a row came from.
"""

from __future__ import annotations

COLUMNS = [
    "id",            # unique id (publication no. / DOI / sample id)
    "record_type",   # "Patent" | "Research"
    "source_db",     # "PatentsView" | "OpenAlex" | "Sample"
    "data_kind",     # "live" | "sample"
    "title",
    "abstract",
    "minerals",      # list[str]  (from CRITICAL_MINERALS)
    "domains",       # list[str]  (from TECH_DOMAINS)
    "org",           # primary assignee / affiliation (str)
    "orgs",          # list[str]  all assignees / affiliations
    "people",        # list[str]  inventors / authors
    "country",       # 2-letter jurisdiction / country code
    "year",          # int
    "date",          # ISO date str (YYYY-MM-DD) or ""
    "citations",     # int
    "status",        # legal status / OA status ("Granted", "Application", ...)
    "codes",         # list[str]  CPC / IPC / concept codes
    "url",           # link out
    "is_india",      # bool  (country == IN or Indian org)
]

INDIA_ORG_HINTS = [
    "india", "csir", "iit ", "iisc", "barc", "irel", "jnarddc", "arci", "nftdc",
    "nml", "immt", "ncl", "ngri", "hindustan", "tata steel", "vedanta", "nmdc",
    "bhabha", "council of scientific", "indian institute",
]


def make_record(**kw) -> dict:
    """Build a record dict with every column present (missing -> sensible default)."""
    rec = {c: None for c in COLUMNS}
    rec.update(
        minerals=[], domains=[], orgs=[], people=[], codes=[],
        citations=0, abstract="", url="", date="", status="", is_india=False,
    )
    rec.update(kw)
    # Derive india flag from country + org text if not set explicitly.
    if not rec.get("is_india"):
        blob = " ".join(
            [str(rec.get("org") or "")] + [str(o) for o in (rec.get("orgs") or [])]
        ).lower()
        rec["is_india"] = (rec.get("country") == "IN") or any(h in blob for h in INDIA_ORG_HINTS)
    return rec
