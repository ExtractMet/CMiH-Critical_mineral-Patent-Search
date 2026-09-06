# Critical Minerals — Smart Technology & Patent Tracker

**Critical Minerals Innovation Hackathon 2026 (CMiH 2026) · Problem Statement 2**
*JNARDDC, Nagpur — Ministry of Mines · in support of the National Critical Mineral Mission*

An intuitive, web-based system that unifies **patents** and **R&D** across India's
30 critical minerals into one searchable, analyzable corpus — and turns that corpus
into decision-grade intelligence: technology landscapes, emerging-signal detection,
and an **India self-reliance gap** analysis.

---

## The problem (as set)

> *"Smart Technology and Patent Tracker for Critical Minerals — create an intuitive,
> web-based Smart R&D and Patent Tracking System to track technological developments
> and patents relevant to the critical minerals ecosystem."*

Critical-minerals technology intelligence today is fragmented across patent offices
(USPTO, EPO, WIPO, CNIPA) and research indexes, with no view that is organized around
**India's priorities**: its 30 critical minerals and the full processing value chain.
A policymaker cannot easily ask *"where is India's IP thin on the minerals we depend
on most?"* — this tool is built to answer exactly that.

## What it does

| Capability | Detail |
|---|---|
| **Unified corpus** | Patents (USPTO **PatentsView**) + research (**OpenAlex**) normalized into one schema |
| **Auto-classification** | Every record tagged against India's **30 critical minerals** and an **8-stage value chain** (exploration → mining → beneficiation → metallurgy → separation → recycling → substitution → environment) via a transparent keyword classifier |
| **Overview** | Headline KPIs, patent-vs-research activity over time, filing CAGR, top minerals / domains / jurisdictions |
| **Explorers** | Full-text + faceted search over patents and research, sortable, with links out and CSV export |
| **Technology landscape** | Mineral × domain **intensity heatmap**, top assignees/institutions, domain→mineral sunburst |
| **Trends & signals** | **Emerging-technology detection** — momentum of each domain/mineral (last 3 yrs vs prior 3), growth ranking, trajectory overlays |
| **India focus** | **Self-reliance gap score** = import-dependency × (low domestic IP share); surfaces strategically vital minerals under-represented in Indian IP + most-active Indian institutions |
| **Watchlist & alerts** | Save mineral/domain watches; flag newest activity — the continuous-monitoring layer |

## Live data vs demo mode

- **Demo mode (default):** ships with a bundled, deterministic **sample corpus**
  (~520 records) engineered to mirror real landscape patterns — China-dominant
  patenting, recycling as the fastest-growing domain, India concentrated in a few
  CSIR labs / IITs / IREL / BARC. **Runs instantly, no keys, no network.**
  These figures are *illustrative, not official statistics* (the app says so).
- **Live mode:** queries **OpenAlex** (free, just a contact email) and
  **USPTO PatentsView** (free API key) and classifies real records on the fly.
  Any failure degrades gracefully back to the sample corpus.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

For live mode, copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml`
and add your OpenAlex email and (optionally) a PatentsView key.

### Deploy to Streamlit Community Cloud
1. Push this folder to a GitHub repo.
2. On [share.streamlit.io](https://share.streamlit.io) → **New app** → point to `app.py`.
3. Add secrets (`OPENALEX_MAILTO`, `PATENTSVIEW_API_KEY`) in **App → Settings → Secrets**.

## Architecture

```
connectors.py   live APIs (OpenAlex, PatentsView) + normalization + graceful fallback
     │
schema.py       one flat record shape for every source
     │
taxonomy.py     30 critical minerals + 8 value-chain domains + keyword classifier   ← domain source of truth
     │
seed_data.py    deterministic, realistic sample corpus (demo mode)
     │
store.py        records → DataFrame, global filters, CSV export, alert logic
     │
analytics.py    pure, testable: trends, CAGR, landscape matrix, emerging signals, India gap
     │
app.py          Streamlit UI — 8 tabs
```

Design principles: **pure analytics** (no UI coupling, fully unit-tested), a single
**normalized schema** so sources are interchangeable, and a **taxonomy that domain
experts edit** as the single source of truth.

## Tests

```bash
pytest -q          # 10 tests: taxonomy, corpus determinism, analytics, connector normalization
```

## Roadmap to production

- Add **Espacenet/OPS**, **Lens.org**, and **WIPO PATENTSCOPE** connectors
  (PATENTSCOPE is key for capturing **Indian** patent applications).
- **Semantic search & clustering** via embeddings (beyond keyword classification).
- Scheduled crawler → database so **alerts fire on genuinely new filings**.
- Patent **family de-duplication** (DOCDB/INPADOC) and legal-status enrichment.
- Assignee **co-invention / citation networks** for collaboration mapping.

---

*Built for CMiH 2026. India's 30 critical minerals per Ministry of Mines (June 2023).*
