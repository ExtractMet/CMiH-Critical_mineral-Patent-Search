"""
Bundled sample corpus.

Live connectors (OpenAlex / PatentsView) are the real thing, but a hackathon demo
must work instantly with zero keys and zero network. This module builds a corpus
that is *qualitatively faithful* to the real critical-minerals IP landscape:

  * China-dominated patenting, esp. in REE, magnets and batteries;
  * recycling / urban-mining as the fastest-growing domain post-2018;
  * battery minerals (Li, Ni, Co, Graphite) dominating volume;
  * India present but concentrated in a handful of CSIR labs, IITs, IREL, etc.,
    skewed toward REE / Ti / graphite / vanadium and recycling.

Everything here is clearly flagged data_kind="sample". It is illustrative and must
NOT be read as official statistics - the app says so prominently. Swap in the live
connectors for verified records.

`build_corpus()` is deterministic (fixed RNG seed) so charts are stable across runs.
"""

from __future__ import annotations

import random
from urllib.parse import quote_plus

from .schema import make_record
from .taxonomy import CRITICAL_MINERALS, TECH_DOMAINS

# --------------------------------------------------------------------------- #
# Realistic weights (qualitative, editable)
# --------------------------------------------------------------------------- #
_JURISDICTIONS = {  # global patent-activity share (approx, illustrative)
    "CN": 0.34, "JP": 0.14, "US": 0.14, "KR": 0.10, "EP": 0.07,
    "WO": 0.07, "DE": 0.03, "IN": 0.04, "AU": 0.03, "CA": 0.02, "FR": 0.02,
}

_MINERAL_WEIGHT = {  # patent-volume share (batteries + REE dominate)
    "Lithium": 16, "REE": 12, "Nickel": 9, "Copper": 8, "Cobalt": 8,
    "Graphite": 7, "Titanium": 6, "Silicon": 5, "Vanadium": 4, "Tungsten": 3,
    "Molybdenum": 3, "Gallium": 2, "Germanium": 2, "Indium": 2, "Tin": 2,
    "Niobium": 1.5, "Tantalum": 1.5, "Zirconium": 1.5, "PGE": 2, "Phosphorous": 2,
    "Antimony": 1, "Selenium": 1, "Cadmium": 1, "Strontium": 1, "Bismuth": 1,
    "Beryllium": 0.7, "Potash": 1, "Hafnium": 0.6, "Rhenium": 0.5, "Tellurium": 1,
}

_DOMAIN_WEIGHT = {
    "Mineral Processing & Beneficiation": 16,
    "Extractive Metallurgy": 16,
    "Separation & Refining": 15,
    "Recycling & Urban Mining": 18,      # fastest growing
    "Mining & Extraction": 14,
    "Exploration & Prospecting": 8,
    "Substitution & Materials": 8,
    "Environment & Decarbonization": 5,
}

# assignee pools per jurisdiction (realistic-sounding; illustrative only)
_ORGS = {
    "CN": ["Central South University", "Univ. of Science & Technology Beijing", "Northeastern University (CN)",
           "GEM Co. Ltd", "Ganfeng Lithium", "CATL", "China Molybdenum", "GRINM Group", "Baotou Steel Rare-Earth",
           "Tsinghua University", "Guangdong Brunp Recycling"],
    "JP": ["Sumitomo Metal Mining", "Mitsubishi Materials", "JX Advanced Metals", "Toyota Motor",
           "Shin-Etsu Chemical", "Proterial (Hitachi Metals)", "Panasonic Energy", "Tohoku University"],
    "US": ["Albemarle", "Redwood Materials", "MP Materials", "General Motors", "Dow", "3M",
           "Los Alamos National Lab", "Lynas USA", "Ames National Laboratory", "Li-Cycle"],
    "KR": ["POSCO Holdings", "LG Energy Solution", "Samsung SDI", "SK Innovation", "KIGAM", "Korea Zinc"],
    "EP": ["Umicore", "BASF", "Fraunhofer Institute", "Aurubis", "Solvay", "Imerys"],
    "DE": ["BASF", "Fraunhofer Institute", "Aurubis", "Siemens", "Karlsruhe Institute of Technology"],
    "IN": ["CSIR-National Metallurgical Laboratory", "CSIR-Institute of Minerals & Materials Technology",
           "CSIR-National Chemical Laboratory", "Bhabha Atomic Research Centre", "IREL (India) Ltd",
           "IIT Bombay", "IIT Madras", "JNARDDC Nagpur", "ARCI Hyderabad", "Hindustan Zinc", "Tata Steel"],
    "AU": ["CSIRO", "Lynas Rare Earths", "IGO Ltd", "Australian National University", "Univ. of Queensland"],
    "CA": ["Li-Cycle", "Neo Performance Materials", "University of Toronto", "Vale Base Metals"],
    "FR": ["Orano", "Solvay", "CNRS", "Eramet"],
    "WO": ["Umicore", "BASF", "Albemarle", "CATL", "Sumitomo Metal Mining"],
}

_PROCESS_VERB = {
    "Exploration & Prospecting": ["Geophysical survey method for", "Machine-learning prospectivity mapping of",
                                  "Remote-sensing detection of", "Resource estimation method for"],
    "Mining & Extraction": ["Direct extraction of", "In-situ leaching process for", "Brine extraction of",
                            "Selective extraction of"],
    "Mineral Processing & Beneficiation": ["Froth flotation beneficiation of", "Magnetic separation of",
                                           "Gravity concentration of", "Ore-upgrading process for"],
    "Extractive Metallurgy": ["Hydrometallurgical recovery of", "Roasting-leaching process for",
                              "Electrowinning of", "Pyrometallurgical smelting of", "Bioleaching of"],
    "Separation & Refining": ["Solvent-extraction separation of", "Ion-exchange purification of",
                              "High-purity production of", "Selective precipitation of"],
    "Recycling & Urban Mining": ["Recycling of", "Recovery of", "Closed-loop reclamation of",
                                 "Hydrometallurgical recovery from black mass of"],
    "Substitution & Materials": ["Reduced-content substitute for", "Cobalt-free cathode using",
                                 "Rare-earth-lean magnet based on", "Alternative material replacing"],
    "Environment & Decarbonization": ["Tailings valorization for", "Low-carbon production route for",
                                      "Effluent treatment in processing of", "Circular process for"],
}

_SOURCE_OBJECT = {
    "Recycling & Urban Mining": ["from spent lithium-ion batteries", "from end-of-life electronic waste",
                                 "from spent catalysts", "from smelter slag", "from process tailings"],
    "Extractive Metallurgy": ["from low-grade ore", "from concentrate", "from leach liquor"],
    "Separation & Refining": ["from mixed rare-earth chloride", "from pregnant leach solution", "to battery grade"],
    "_default": ["from ore", "for clean-energy applications", "with improved recovery", "at reduced energy cost"],
}

# --------------------------------------------------------------------------- #
# Curated highlight records (specific, credible; still flagged sample)
# --------------------------------------------------------------------------- #
_CURATED = [
    # (record_type, title, minerals, domains, org, country, year, status)
    ("Patent", "Hydrometallurgical process for recovering lithium, nickel and cobalt from spent lithium-ion batteries",
     ["Lithium", "Nickel", "Cobalt"], ["Recycling & Urban Mining", "Extractive Metallurgy"], "Umicore", "EP", 2023, "Granted"),
    ("Patent", "Solvent-extraction separation of neodymium and dysprosium from mixed rare-earth solution",
     ["REE"], ["Separation & Refining"], "GRINM Group", "CN", 2022, "Granted"),
    ("Patent", "Direct lithium extraction from geothermal brine using selective sorbent",
     ["Lithium"], ["Mining & Extraction"], "Albemarle", "US", 2024, "Application"),
    ("Patent", "Rare-earth-lean NdFeB permanent magnet with grain-boundary diffusion",
     ["REE"], ["Substitution & Materials"], "Proterial (Hitachi Metals)", "JP", 2021, "Granted"),
    ("Patent", "Closed-loop recovery of graphite anode material from black mass",
     ["Graphite", "Lithium"], ["Recycling & Urban Mining"], "Redwood Materials", "US", 2024, "Application"),
    ("Patent", "Process for producing battery-grade nickel sulphate from laterite ore",
     ["Nickel"], ["Extractive Metallurgy", "Separation & Refining"], "Sumitomo Metal Mining", "JP", 2022, "Granted"),
    ("Patent", "Vanadium recovery from steel-plant slag for redox-flow-battery electrolyte",
     ["Vanadium"], ["Recycling & Urban Mining", "Separation & Refining"], "CSIR-National Metallurgical Laboratory", "IN", 2023, "Application"),
    ("Patent", "Beneficiation of low-grade Indian ilmenite for titanium feedstock",
     ["Titanium"], ["Mineral Processing & Beneficiation"], "IREL (India) Ltd", "IN", 2022, "Granted"),
    ("Patent", "Recovery of rare-earth elements from monazite via alkaline decomposition",
     ["REE", "Phosphorous"], ["Extractive Metallurgy", "Separation & Refining"], "Bhabha Atomic Research Centre", "IN", 2021, "Granted"),
    ("Patent", "Cobalt-free lithium iron phosphate cathode with enhanced rate capability",
     ["Phosphorous", "Lithium"], ["Substitution & Materials"], "CATL", "CN", 2023, "Granted"),
    ("Patent", "Selective recovery of gallium from Bayer-process liquor",
     ["Gallium"], ["Separation & Refining", "Recycling & Urban Mining"], "JNARDDC Nagpur", "IN", 2024, "Application"),
    ("Patent", "Electrowinning of tungsten from ammonium paratungstate",
     ["Tungsten"], ["Extractive Metallurgy"], "Central South University", "CN", 2020, "Granted"),
    ("Research", "Machine-learning prospectivity mapping for lithium pegmatites",
     ["Lithium"], ["Exploration & Prospecting"], "CSIRO", "AU", 2024, "Open Access"),
    ("Research", "Bioleaching of cobalt and nickel from spent Li-ion batteries: a review",
     ["Cobalt", "Nickel"], ["Recycling & Urban Mining", "Extractive Metallurgy"], "IIT Bombay", "IN", 2023, "Open Access"),
    ("Research", "Techno-economics of rare-earth separation by solvent extraction",
     ["REE"], ["Separation & Refining"], "CSIR-Institute of Minerals & Materials Technology", "IN", 2022, "Open Access"),
    ("Research", "Direct lithium extraction technologies: a comparative review",
     ["Lithium"], ["Mining & Extraction"], "University of Queensland", "AU", 2024, "Open Access"),
    ("Research", "Recovery of critical metals from copper anode slime",
     ["Copper", "Selenium", "Tellurium", "PGE"], ["Recycling & Urban Mining", "Separation & Refining"], "Aurubis", "DE", 2023, "Closed"),
    ("Research", "Graphite purification for anode-grade material from Indian flake graphite",
     ["Graphite"], ["Separation & Refining", "Mineral Processing & Beneficiation"], "CSIR-National Metallurgical Laboratory", "IN", 2023, "Open Access"),
]


def _weighted(rng: random.Random, weights: dict) -> str:
    items, w = zip(*weights.items())
    return rng.choices(items, weights=w, k=1)[0]


def _google_patents_url(title: str) -> str:
    return f"https://patents.google.com/?q={quote_plus(title)}"


def _scholar_url(title: str) -> str:
    return f"https://scholar.google.com/scholar?q={quote_plus(title)}"


def _year_weight(year: int, domain: str, mineral: str) -> float:
    """Growth trend: everything grows to ~2024; recycling + battery minerals grow faster recently."""
    base = 1.0 + 0.16 * (year - 2015)               # steady growth
    if domain == "Recycling & Urban Mining" and year >= 2018:
        base *= 1.0 + 0.28 * (year - 2018)          # recycling surge
    if mineral in ("Lithium", "Nickel", "Cobalt", "Graphite") and year >= 2019:
        base *= 1.0 + 0.18 * (year - 2019)          # battery surge
    if year == 2025:                                 # partial year
        base *= 0.45
    return base


def build_corpus(n_patents: int = 340, n_research: int = 160, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    years = list(range(2015, 2026))
    records: list[dict] = []

    # 1. curated highlights
    for rt, title, minerals, domains, org, country, year, status in _CURATED:
        url = _google_patents_url(title) if rt == "Patent" else _scholar_url(title)
        records.append(make_record(
            id=f"SAMPLE-{'P' if rt=='Patent' else 'R'}-C{len(records):04d}",
            record_type=rt, source_db="Sample", data_kind="sample",
            title=title, abstract=title + ".", minerals=minerals, domains=domains,
            org=org, orgs=[org], people=[], country=country, year=year,
            date=f"{year}-06-15", citations=rng.randint(3, 90),
            status=status, codes=[], url=url,
        ))

    # 2. synthetic bulk
    def _make(rt: str, idx: int):
        mineral = _weighted(rng, _MINERAL_WEIGHT)
        domain = _weighted(rng, _DOMAIN_WEIGHT)
        # re-sample year using trend weights
        yw = [_year_weight(y, domain, mineral) for y in years]
        year = rng.choices(years, weights=yw, k=1)[0]
        # jurisdiction: nudge REE/magnets toward CN, batteries toward CN/KR/JP
        jw = dict(_JURISDICTIONS)
        if mineral == "REE":
            jw["CN"] *= 2.0; jw["IN"] *= 1.3
        if mineral in ("Lithium", "Nickel", "Cobalt", "Graphite"):
            jw["CN"] *= 1.3; jw["KR"] *= 1.6; jw["JP"] *= 1.3
        if mineral in ("Titanium", "Vanadium", "Graphite", "REE"):
            jw["IN"] *= 1.4
        country = _weighted(rng, jw)
        org = rng.choice(_ORGS[country])

        verb = rng.choice(_PROCESS_VERB[domain])
        obj_pool = _SOURCE_OBJECT.get(domain, _SOURCE_OBJECT["_default"])
        obj = rng.choice(obj_pool)
        mineral_disp = "rare-earth elements" if mineral == "REE" else mineral.lower()
        title = f"{verb} {mineral_disp} {obj}".strip()
        title = title[0].upper() + title[1:]

        status = (rng.choices(["Granted", "Application"], weights=[0.55, 0.45])[0]
                  if rt == "Patent" else
                  rng.choices(["Open Access", "Closed"], weights=[0.62, 0.38])[0])
        cites = int(abs(rng.gauss(12, 18))) + (2025 - year)
        url = _google_patents_url(title) if rt == "Patent" else _scholar_url(title)

        return make_record(
            id=f"SAMPLE-{'P' if rt=='Patent' else 'R'}-{idx:05d}",
            record_type=rt, source_db="Sample", data_kind="sample",
            title=title, abstract=title + ".", minerals=[mineral], domains=[domain],
            org=org, orgs=[org], people=[], country=country, year=year,
            date=f"{year}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            citations=cites, status=status, codes=[], url=url,
        )

    for i in range(n_patents):
        records.append(_make("Patent", i))
    for i in range(n_research):
        records.append(_make("Research", i))

    return records
