"""
Live data connectors.

These hit real, public APIs and normalize responses into the shared schema:

  * OpenAlexClient   - https://api.openalex.org/works   (FREE, no key; research/R&D)
  * PatentsViewClient- https://search.patentsview.org   (USPTO; API key via secrets)

Design goals:
  * never crash the app - any network / auth failure returns [] and is reported
    up so the UI can fall back to the bundled sample corpus;
  * short timeouts;
  * live records are auto-tagged with minerals/domains via the taxonomy keyword
    classifier, since the raw APIs don't carry our labels.

The sandbox used to build this app cannot reach these hosts, so the HTTP paths
are exercised at deploy time; the *normalization* logic is unit-tested against
canned payloads (see tests/).
"""

from __future__ import annotations

from datetime import date

import requests

from .schema import make_record
from .taxonomy import classify_text

_UA = {"User-Agent": "CriticalMineralsTracker/1.0 (CMiH2026; mailto:extractmet@example.org)"}
_TIMEOUT = 20


# --------------------------------------------------------------------------- #
# OpenAlex  (research publications) - free, no key
# --------------------------------------------------------------------------- #
class OpenAlexClient:
    BASE = "https://api.openalex.org/works"

    def __init__(self, mailto: str | None = None):
        self.mailto = mailto or "extractmet@example.org"

    def search(self, query: str, per_page: int = 50, from_year: int = 2015) -> list[dict]:
        params = {
            "search": query,
            "per_page": min(per_page, 200),
            "filter": f"from_publication_date:{from_year}-01-01",
            "mailto": self.mailto,
            "sort": "publication_date:desc",
        }
        try:
            r = requests.get(self.BASE, params=params, headers=_UA, timeout=_TIMEOUT)
            r.raise_for_status()
            payload = r.json()
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            raise ConnectorError(f"OpenAlex request failed: {exc}") from exc
        return [self._normalize(w) for w in payload.get("results", [])]

    @staticmethod
    def _country_from_work(w: dict) -> str | None:
        for a in w.get("authorships", []):
            for inst in a.get("institutions", []):
                cc = inst.get("country_code")
                if cc:
                    return cc.upper()
        return None

    @classmethod
    def _normalize(cls, w: dict) -> dict:
        title = w.get("title") or w.get("display_name") or ""
        # OpenAlex abstracts come as an inverted index
        abstract = _deinvert_abstract(w.get("abstract_inverted_index"))
        orgs, people = [], []
        for a in w.get("authorships", []):
            au = (a.get("author") or {}).get("display_name")
            if au:
                people.append(au)
            for inst in a.get("institutions", []):
                if inst.get("display_name"):
                    orgs.append(inst["display_name"])
        orgs = list(dict.fromkeys(orgs))          # de-dup, keep order
        concepts = [c.get("display_name") for c in w.get("concepts", []) if c.get("display_name")]
        minerals, domains = classify_text(f"{title} {abstract} {' '.join(concepts)}")
        pub_date = w.get("publication_date") or ""
        year = w.get("publication_year") or (int(pub_date[:4]) if pub_date[:4].isdigit() else None)
        oa = (w.get("open_access") or {}).get("is_oa")
        return make_record(
            id=w.get("doi") or w.get("id") or title[:60],
            record_type="Research", source_db="OpenAlex", data_kind="live",
            title=title, abstract=abstract, minerals=minerals, domains=domains,
            org=orgs[0] if orgs else None, orgs=orgs, people=people,
            country=cls._country_from_work(w), year=year, date=pub_date,
            citations=w.get("cited_by_count", 0),
            status="Open Access" if oa else "Closed",
            codes=concepts[:6],
            url=(w.get("doi") or w.get("id") or ""),
        )


# --------------------------------------------------------------------------- #
# PatentsView  (USPTO patents) - new Search API needs a key
# --------------------------------------------------------------------------- #
class PatentsViewClient:
    BASE = "https://search.patentsview.org/api/v1/patent/"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, per_page: int = 50, from_year: int = 2015) -> list[dict]:
        if not self.api_key:
            raise ConnectorError("PatentsView API key not configured (set PATENTSVIEW_API_KEY).")
        body = {
            "q": {"_and": [
                {"_text_any": {"patent_title": query}},
                {"_gte": {"patent_date": f"{from_year}-01-01"}},
            ]},
            "f": ["patent_id", "patent_title", "patent_abstract", "patent_date",
                  "assignees.assignee_organization", "assignees.assignee_country",
                  "inventors.inventor_name_last", "cpc_current.cpc_group_id"],
            "o": {"size": min(per_page, 100)},
            "s": [{"patent_date": "desc"}],
        }
        try:
            r = requests.post(self.BASE, json=body,
                              headers={**_UA, "X-Api-Key": self.api_key}, timeout=_TIMEOUT)
            r.raise_for_status()
            payload = r.json()
        except Exception as exc:  # noqa: BLE001
            raise ConnectorError(f"PatentsView request failed: {exc}") from exc
        return [self._normalize(p) for p in payload.get("patents", [])]

    @classmethod
    def _normalize(cls, p: dict) -> dict:
        title = p.get("patent_title") or ""
        abstract = p.get("patent_abstract") or ""
        assignees = p.get("assignees") or []
        orgs = [a.get("assignee_organization") for a in assignees if a.get("assignee_organization")]
        country = next((a.get("assignee_country") for a in assignees if a.get("assignee_country")), None)
        people = [a.get("inventor_name_last") for a in (p.get("inventors") or []) if a.get("inventor_name_last")]
        codes = [c.get("cpc_group_id") for c in (p.get("cpc_current") or []) if c.get("cpc_group_id")]
        minerals, domains = classify_text(f"{title} {abstract}")
        pdate = p.get("patent_date") or ""
        year = int(pdate[:4]) if pdate[:4].isdigit() else None
        pid = p.get("patent_id")
        return make_record(
            id=f"US{pid}" if pid else title[:60],
            record_type="Patent", source_db="PatentsView", data_kind="live",
            title=title, abstract=abstract, minerals=minerals, domains=domains,
            org=orgs[0] if orgs else None, orgs=orgs, people=people,
            country=(country.upper() if country else "US"), year=year, date=pdate,
            citations=0, status="Granted", codes=codes[:6],
            url=f"https://patents.google.com/patent/US{pid}" if pid else "",
        )


class ConnectorError(RuntimeError):
    """Raised on any live-source failure so callers can fall back to sample data."""


def fetch_live(queries: list[str], oa_key: str | None, pv_key: str | None,
               per_source: int = 60, from_year: int = 2015) -> tuple[list[dict], list[str]]:
    """
    Best-effort fetch across sources for a list of query strings.
    Returns (records, messages) - messages describe what worked / failed.
    """
    records: list[dict] = []
    messages: list[str] = []

    oa = OpenAlexClient(mailto=oa_key)
    pv = PatentsViewClient(api_key=pv_key)

    for q in queries:
        try:
            got = oa.search(q, per_page=per_source, from_year=from_year)
            records.extend(got)
            messages.append(f"OpenAlex '{q}': {len(got)} works")
        except ConnectorError as e:
            messages.append(str(e))
        if pv.available():
            try:
                got = pv.search(q, per_page=per_source, from_year=from_year)
                records.extend(got)
                messages.append(f"PatentsView '{q}': {len(got)} patents")
            except ConnectorError as e:
                messages.append(str(e))

    # de-duplicate by id
    seen, unique = set(), []
    for r in records:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        unique.append(r)
    return unique, messages


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _deinvert_abstract(inv: dict | None) -> str:
    """OpenAlex stores abstracts as {word: [positions]}. Rebuild the text."""
    if not inv:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)[:2000]
