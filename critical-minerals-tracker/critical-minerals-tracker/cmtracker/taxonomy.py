"""
Domain taxonomy for the Critical Minerals Smart Technology & Patent Tracker.

Two controlled vocabularies drive the whole system:

1. CRITICAL_MINERALS  - India's official list of 30 critical minerals
                        (Ministry of Mines, June 2023), with policy context
                        used for the self-reliance / gap analysis.
2. TECH_DOMAINS       - the critical-minerals value chain, from exploration to
                        recycling & substitution. Every patent / paper is
                        auto-classified into one or more of these.

The `*_KEYWORDS` maps let us tag *live* records (from OpenAlex / PatentsView)
that arrive without our labels, using simple, transparent keyword matching.
This table is meant to be edited by domain experts - it is the single source
of truth for the taxonomy.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# 1. India's 30 critical minerals (Ministry of Mines, 2023)
#    dependency  : qualitative India import-dependency / supply-risk level
#                  {"Very High", "High", "Moderate", "Low"}  (editable heuristic)
#    domestic    : whether India has a meaningful domestic resource base
#    note        : one-line policy / supply-chain context
# --------------------------------------------------------------------------- #
CRITICAL_MINERALS: dict[str, dict] = {
    "Lithium":     {"group": "Battery",       "dependency": "Very High", "domestic": False, "note": "Battery cathode/anode; near-total import reliance; J&K & Karnataka finds early-stage."},
    "Cobalt":      {"group": "Battery",       "dependency": "Very High", "domestic": False, "note": "Li-ion cathodes & superalloys; supply concentrated in DRC + China refining."},
    "Nickel":      {"group": "Battery",       "dependency": "High",      "domestic": False, "note": "High-Ni cathodes & stainless; limited domestic sulphide/laterite processing."},
    "Graphite":    {"group": "Battery",       "dependency": "High",      "domestic": True,  "note": "Anode material; India has flake resources but spherical/coated graphite gap."},
    "Copper":      {"group": "Base/Energy",   "dependency": "High",      "domestic": True,  "note": "Grid & EV wiring; concentrate import-heavy after smelter closures."},
    "REE":         {"group": "Magnet/REE",    "dependency": "High",      "domestic": True,  "note": "Rare earths for NdFeB magnets; India has monazite but separation/magnet gap."},
    "Vanadium":    {"group": "Energy/Steel",  "dependency": "High",      "domestic": True,  "note": "VRFB flow batteries & HSLA steel; recoverable from steel slag & Ti-magnetite."},
    "Tungsten":    {"group": "Refractory",    "dependency": "Very High", "domestic": False, "note": "Cutting tools & alloys; scheelite/wolframite processing largely imported."},
    "Titanium":    {"group": "Structural",    "dependency": "Moderate",  "domestic": True,  "note": "India resource-rich in ilmenite/rutile; gap is Ti sponge & metal, not feedstock."},
    "Molybdenum":  {"group": "Refractory",    "dependency": "High",      "domestic": False, "note": "Steel alloying & catalysts; largely a byproduct import."},
    "Silicon":     {"group": "Semiconductor", "dependency": "Moderate",  "domestic": True,  "note": "PV & electronics; quartz abundant but polysilicon/wafer capacity limited."},
    "Gallium":     {"group": "Semiconductor", "dependency": "Very High", "domestic": False, "note": "GaN/GaAs power & RF chips; byproduct of alumina, China-dominated, export-controlled."},
    "Germanium":   {"group": "Semiconductor", "dependency": "Very High", "domestic": False, "note": "Fibre optics & IR optics; scarce byproduct, export-controlled by China."},
    "Indium":      {"group": "Semiconductor", "dependency": "Very High", "domestic": False, "note": "ITO for displays & PV; zinc-refining byproduct, highly import-dependent."},
    "Tantalum":    {"group": "Electronics",   "dependency": "Very High", "domestic": False, "note": "Capacitors; from columbite-tantalite, no domestic primary supply."},
    "Niobium":     {"group": "Steel/Alloy",   "dependency": "Very High", "domestic": False, "note": "Microalloyed steel & superconductors; supply concentrated in Brazil."},
    "PGE":         {"group": "Catalyst",      "dependency": "Very High", "domestic": False, "note": "Platinum-group for catalysts, fuel cells, H2; almost entirely imported."},
    "Antimony":    {"group": "Flame/Alloy",   "dependency": "Very High", "domestic": False, "note": "Flame retardants & lead-acid alloys; China-dominated, export-controlled."},
    "Bismuth":     {"group": "Alloy/Pharma",  "dependency": "High",      "domestic": False, "note": "Low-melt alloys, pharma; lead/tungsten smelting byproduct."},
    "Beryllium":   {"group": "Alloy/Defence", "dependency": "Very High", "domestic": False, "note": "Aerospace & defence alloys; strategic, no domestic production."},
    "Rhenium":     {"group": "Superalloy",    "dependency": "Very High", "domestic": False, "note": "Jet-engine superalloys; ultra-scarce Mo-roasting byproduct."},
    "Strontium":   {"group": "Industrial",    "dependency": "High",      "domestic": False, "note": "Ferrite magnets, pyrotechnics, glass; celestite import-dependent."},
    "Tellurium":   {"group": "Semiconductor", "dependency": "Very High", "domestic": False, "note": "CdTe thin-film PV & thermoelectrics; copper-refining byproduct."},
    "Tin":         {"group": "Solder",        "dependency": "High",      "domestic": True,  "note": "Solders & coatings; limited cassiterite mining in central India."},
    "Zirconium":   {"group": "Nuclear",       "dependency": "Moderate",  "domestic": True,  "note": "Nuclear cladding & ceramics; India has beach-sand zircon, cladding is strategic."},
    "Hafnium":     {"group": "Nuclear",       "dependency": "Very High", "domestic": False, "note": "Control rods & superalloys; co-produced with Zr, highly strategic."},
    "Selenium":    {"group": "Industrial",    "dependency": "High",      "domestic": False, "note": "Glass, PV, alloys; copper-refining byproduct."},
    "Cadmium":     {"group": "Battery/PV",    "dependency": "Moderate",  "domestic": True,  "note": "CdTe PV & NiCd; zinc-refining byproduct, recoverable domestically."},
    "Phosphorous": {"group": "Agri/Battery",  "dependency": "High",      "domestic": True,  "note": "Fertiliser & LFP cathodes; phosphate rock partly imported."},
    "Potash":      {"group": "Agri",          "dependency": "Very High", "domestic": False, "note": "Fertiliser (MOP/SOP); India imports nearly all potash."},
}

DEPENDENCY_SCORE = {"Very High": 4, "High": 3, "Moderate": 2, "Low": 1}

# Search / matching synonyms for each mineral. Keys must match CRITICAL_MINERALS.
MINERAL_KEYWORDS: dict[str, list[str]] = {
    "Lithium":     ["lithium", "li-ion", "lithium-ion", "spodumene", "lepidolite", "lifepo4", "lfp", "lco", "nmc"],
    "Cobalt":      ["cobalt", "cobaltite", "licoo2", "lco"],
    "Nickel":      ["nickel", "laterite", "sulphide nickel", "ni-rich", "nca", "nmc"],
    "Graphite":    ["graphite", "graphitic", "anode graphite", "spherical graphite", "graphene"],
    "Copper":      ["copper", "chalcopyrite", "cu concentrate", "cathode copper", "copper anode slime"],
    "REE":         ["rare earth", "rare-earth", "ree", "neodymium", "praseodymium", "dysprosium", "terbium",
                     "lanthanum", "cerium", "samarium", "yttrium", "europium", "gadolinium", "ndfeb", "monazite", "bastnasite", "bastnaesite"],
    "Vanadium":    ["vanadium", "vanadate", "vrfb", "vanadium redox", "ferrovanadium"],
    "Tungsten":    ["tungsten", "wolframite", "scheelite", "tungsten carbide", "ammonium paratungstate"],
    "Titanium":    ["titanium", "ilmenite", "rutile", "ti sponge", "titanium dioxide", "tio2", "titania", "kroll"],
    "Molybdenum":  ["molybdenum", "molybdenite", "ferromolybdenum", "moo3"],
    "Silicon":     ["silicon", "polysilicon", "metallurgical silicon", "silicon wafer", "silane", "ferrosilicon"],
    "Gallium":     ["gallium", "gan", "gaas", "gallium nitride", "gallium arsenide"],
    "Germanium":   ["germanium", "geo2", "germanium tetrachloride"],
    "Indium":      ["indium", "ito", "indium tin oxide", "indium phosphide"],
    "Tantalum":    ["tantalum", "tantalite", "tantalum capacitor", "ta2o5"],
    "Niobium":     ["niobium", "columbite", "ferroniobium", "nb2o5", "niobate"],
    "PGE":         ["platinum", "palladium", "rhodium", "iridium", "ruthenium", "osmium", "platinum group", "pgm", "pge"],
    "Antimony":    ["antimony", "stibnite", "antimony trioxide", "sb2o3"],
    "Bismuth":     ["bismuth", "bismuthinite"],
    "Beryllium":   ["beryllium", "beryl", "bertrandite"],
    "Rhenium":     ["rhenium", "ammonium perrhenate"],
    "Strontium":   ["strontium", "celestite", "celestine", "strontium carbonate"],
    "Tellurium":   ["tellurium", "cdte", "telluride"],
    "Tin":         ["tin", "cassiterite", "stannous", "stannic", "tin solder"],
    "Zirconium":   ["zirconium", "zircon", "zirconia", "zro2", "zircaloy"],
    "Hafnium":     ["hafnium", "hafnia", "hfo2"],
    "Selenium":    ["selenium", "selenide"],
    "Cadmium":     ["cadmium", "cdte", "nickel-cadmium", "nicd"],
    "Phosphorous": ["phosphorus", "phosphorous", "phosphate", "phosphoric", "apatite", "lfp", "lifepo4"],
    "Potash":      ["potash", "potassium chloride", "muriate of potash", "sylvite", "sulphate of potash"],
}

# --------------------------------------------------------------------------- #
# 2. Critical-minerals value chain (technology domains)
# --------------------------------------------------------------------------- #
TECH_DOMAINS: dict[str, dict] = {
    "Exploration & Prospecting": {
        "short": "Explore",
        "desc": "Geophysical/geochemical surveys, remote sensing, AI-driven prospectivity, drilling & resource estimation.",
    },
    "Mining & Extraction": {
        "short": "Mine",
        "desc": "Ore extraction, in-situ leaching, brine & seawater extraction, DLE (direct lithium extraction).",
    },
    "Mineral Processing & Beneficiation": {
        "short": "Beneficiate",
        "desc": "Comminution, flotation, gravity & magnetic separation, ore upgrading and concentration.",
    },
    "Extractive Metallurgy": {
        "short": "Metallurgy",
        "desc": "Hydro-, pyro- and electro-metallurgical winning: roasting, smelting, leaching, electrowinning.",
    },
    "Separation & Refining": {
        "short": "Refine",
        "desc": "Solvent extraction, ion exchange, precipitation, REE separation, high-purity metal/salt production.",
    },
    "Recycling & Urban Mining": {
        "short": "Recycle",
        "desc": "Recovery from spent batteries, e-waste, catalysts, slags & tailings; secondary raw materials.",
    },
    "Substitution & Materials": {
        "short": "Substitute",
        "desc": "Reduced-critical-content materials, magnet & catalyst substitutes, alternative chemistries.",
    },
    "Environment & Decarbonization": {
        "short": "Green",
        "desc": "Tailings valorization, emissions/effluent control, water & energy efficiency, low-carbon routes.",
    },
}

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "Exploration & Prospecting":          ["exploration", "prospect", "geophys", "geochem", "remote sensing",
                                            "drilling", "resource estimat", "ore deposit", "survey", "reconnaissance"],
    "Mining & Extraction":                ["mining", "in-situ", "in situ leach", "brine", "seawater", "direct lithium",
                                            "dle", "extraction of ore", "open pit", "underground mine", "well field"],
    "Mineral Processing & Beneficiation": ["beneficiation", "flotation", "froth", "comminution", "grinding", "crushing",
                                            "magnetic separation", "gravity separation", "concentrat", "upgrading ore", "milling"],
    "Extractive Metallurgy":              ["smelting", "roasting", "leaching", "hydrometallurg", "pyrometallurg",
                                            "electrowinning", "electrolysis", "reduction", "calcination", "furnace", "bioleach"],
    "Separation & Refining":              ["solvent extraction", "ion exchange", "precipitation", "purification",
                                            "refining", "separation of rare", "high purity", "electrorefin", "crystalliz", "sx"],
    "Recycling & Urban Mining":           ["recycl", "spent batter", "spent lithium", "e-waste", "electronic waste",
                                            "secondary", "urban mining", "spent catalyst", "black mass", "reclaim", "recover from waste"],
    "Substitution & Materials":           ["substitut", "alternative", "reduced cobalt", "cobalt-free", "rare-earth-free",
                                            "dysprosium-free", "replacement material", "novel cathode", "solid-state electrolyte", "magnet material"],
    "Environment & Decarbonization":      ["tailings", "slag valoriz", "effluent", "emission", "decarboniz",
                                            "carbon footprint", "waste water", "wastewater", "sustainab", "green hydrogen", "circular"],
}

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def minerals_by_group() -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for m, meta in CRITICAL_MINERALS.items():
        groups.setdefault(meta["group"], []).append(m)
    return groups


def classify_text(text: str) -> tuple[list[str], list[str]]:
    """Return (minerals, domains) matched in a free-text string via keywords."""
    t = (text or "").lower()
    minerals = [m for m, kws in MINERAL_KEYWORDS.items() if any(k in t for k in kws)]
    domains = [d for d, kws in DOMAIN_KEYWORDS.items() if any(k in t for k in kws)]
    return minerals, domains


ALL_MINERALS = list(CRITICAL_MINERALS.keys())
ALL_DOMAINS = list(TECH_DOMAINS.keys())
