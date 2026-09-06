"""
Critical Minerals — Smart Technology & Patent Tracker
=====================================================

CMiH 2026 · Problem Statement 2 (JNARDDC, Ministry of Mines)
An intuitive, web-based system to track R&D and patents across the critical-
minerals ecosystem, in support of India's National Critical Mineral Mission.

Run:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from cmtracker import analytics as A
from cmtracker import connectors as C
from cmtracker import store as S
from cmtracker.taxonomy import (
    ALL_DOMAINS,
    ALL_MINERALS,
    CRITICAL_MINERALS,
    TECH_DOMAINS,
)

# --------------------------------------------------------------------------- #
# Page config + light theming
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Critical Minerals · Tech & Patent Tracker",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)

PALETTE = ["#1b5e57", "#c8963e", "#3a6ea5", "#a4443b", "#5c8a3a", "#7a5195",
           "#d17a22", "#4c6472", "#946b2d", "#2f8f83"]
PLOT_KW = dict(template="plotly_white")
STRETCH = dict(width="stretch")

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
      div[data-testid="stMetric"] {background:#f6f4ef; border:1px solid #e7e2d6;
          border-radius:12px; padding:12px 14px;}
      div[data-testid="stMetricValue"] {font-size:1.5rem;}
      .hero {background:linear-gradient(90deg,#12433d 0%,#1b5e57 60%,#2f8f83 100%);
          color:#fff; padding:18px 22px; border-radius:14px; margin-bottom:8px;}
      .hero h1 {margin:0; font-size:1.55rem;}
      .hero p {margin:.35rem 0 0 0; opacity:.92; font-size:.92rem;}
      .pill {display:inline-block; background:#eef4f3; color:#12433d; border:1px solid #cfe3df;
          border-radius:999px; padding:2px 10px; margin:2px 4px 2px 0; font-size:.78rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def _sample_df() -> pd.DataFrame:
    return S.load_sample_df()


@st.cache_data(show_spinner=True, ttl=3600)
def _live_df(queries: tuple[str, ...], oa_mail: str, pv_key: str) -> tuple[pd.DataFrame, list[str]]:
    records, messages = C.fetch_live(list(queries), oa_key=oa_mail or None,
                                     pv_key=pv_key or None, per_source=60)
    return S.records_to_df(records), messages


def get_dataframe():
    """Resolve the active dataset from sidebar controls; returns (df, meta)."""
    meta = {"mode": "sample", "messages": []}
    mode = st.session_state.get("data_mode", "Sample corpus (offline demo)")
    if mode.startswith("Live"):
        sel = st.session_state.get("f_minerals") or ["Lithium", "REE", "Cobalt", "Nickel", "Graphite"]
        queries = tuple(
            f"{'rare earth' if m == 'REE' else m} recovery recycling extraction separation critical mineral"
            for m in sel[:6]
        )
        oa_mail = st.secrets.get("OPENALEX_MAILTO", "") if hasattr(st, "secrets") else ""
        pv_key = st.secrets.get("PATENTSVIEW_API_KEY", "") if hasattr(st, "secrets") else ""
        oa_mail = st.session_state.get("oa_mail", oa_mail)
        pv_key = st.session_state.get("pv_key", pv_key)
        df, messages = _live_df(queries, oa_mail, pv_key)
        meta["messages"] = messages
        if df.empty:
            meta["mode"] = "sample-fallback"
            return _sample_df(), meta
        meta["mode"] = "live"
        return df, meta
    return _sample_df(), meta


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def sidebar() -> dict:
    st.sidebar.markdown("### ⛏️ Critical Minerals Tracker")
    st.sidebar.caption("CMiH 2026 · PS-2 · JNARDDC / Ministry of Mines")

    st.sidebar.radio(
        "Data source",
        ["Sample corpus (offline demo)", "Live APIs (OpenAlex + PatentsView)"],
        key="data_mode",
        help="The sample corpus runs instantly with no keys. Live mode queries "
             "OpenAlex (free) and USPTO PatentsView (needs an API key).",
    )
    if st.session_state.get("data_mode", "").startswith("Live"):
        with st.sidebar.expander("Live API settings", expanded=False):
            st.text_input("OpenAlex contact email (polite pool)", key="oa_mail",
                          placeholder="you@org.in")
            st.text_input("PatentsView API key", key="pv_key", type="password",
                          help="Request free at patentsview.org. Without it, only "
                               "OpenAlex research records are fetched.")
            st.caption("Keys can also be set in `.streamlit/secrets.toml`.")

    st.sidebar.divider()
    st.sidebar.markdown("**Filters**")
    minerals = st.sidebar.multiselect("Critical minerals", ALL_MINERALS, key="f_minerals",
                                      help="India's 30 critical minerals (2023).")
    domains = st.sidebar.multiselect("Technology domains", ALL_DOMAINS, key="f_domains")
    rtypes = st.sidebar.multiselect("Record type", ["Patent", "Research"], key="f_types")
    yr = st.sidebar.slider("Year range", 2015, 2025, (2015, 2025), key="f_years")
    text = st.sidebar.text_input("Keyword search", key="f_text",
                                 placeholder="e.g. black mass, solvent extraction")

    st.sidebar.divider()
    st.sidebar.caption("Built for the Critical Minerals Innovation Hackathon 2026. "
                       "Sample-mode figures are illustrative, not official statistics.")
    return dict(minerals=minerals, domains=domains, record_types=rtypes,
                year_range=yr, text=text)


# --------------------------------------------------------------------------- #
# Reusable chart helpers
# --------------------------------------------------------------------------- #
def bar(df, x, y, title, color=None, horizontal=False, height=340):
    if df.empty:
        st.info("No data for the current filters.")
        return
    if horizontal:
        fig = px.bar(df, x=y, y=x, orientation="h", title=title,
                     color=color, color_discrete_sequence=PALETTE, **PLOT_KW)
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
    else:
        fig = px.bar(df, x=x, y=y, title=title, color=color,
                     color_discrete_sequence=PALETTE, **PLOT_KW)
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=48, b=10),
                      legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, **STRETCH)


# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
def tab_overview(df, meta):
    st.markdown(
        '<div class="hero"><h1>Smart Technology &amp; Patent Tracker for Critical Minerals</h1>'
        '<p>Tracking global R&amp;D and patents across India\'s 30 critical minerals — '
        'exploration to recycling — in support of the National Critical Mineral Mission.</p></div>',
        unsafe_allow_html=True,
    )

    if meta["mode"] == "live":
        st.success("Live mode — records fetched from OpenAlex / PatentsView.")
    elif meta["mode"] == "sample-fallback":
        st.warning("Live fetch returned nothing (check keys/network) — showing the bundled sample corpus.")
    else:
        st.info("Demo mode — bundled **illustrative** sample corpus. Switch to *Live APIs* in the sidebar for real records.", icon="🧪")

    h = A.headline(df)
    c = st.columns(5)
    c[0].metric("Records", f"{h['total']:,}")
    c[1].metric("Patents", f"{h['patents']:,}")
    c[2].metric("R&D papers", f"{h['research']:,}")
    c[3].metric("Jurisdictions", h["countries"])
    c[4].metric("India share", f"{h['india_share']}%")

    left, right = st.columns([3, 2])
    with left:
        ts = A.filings_by_year(df, split="record_type")
        if not ts.empty:
            fig = px.area(ts, x="year", y="count", color="record_type",
                          title="Activity over time (patents vs research)",
                          color_discrete_sequence=PALETTE, **PLOT_KW)
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=48, b=10),
                              legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig, **STRETCH)
        g = A.cagr(df, 2016, 2024)
        if g is not None:
            st.caption(f"Overall filing CAGR 2016→2024 ≈ **{g}%/yr** (current filters).")
    with right:
        bar(A.top_counts(df, "country", n=10), "country", "count",
            "Top jurisdictions", horizontal=True, height=360)

    st.markdown("#### Where the activity concentrates")
    a, b = st.columns(2)
    with a:
        bar(A.top_counts(df, "minerals", n=12, explode_list=True), "minerals", "count",
            "Most-active minerals", horizontal=True, height=380)
    with b:
        bar(A.top_counts(df, "domains", n=8, explode_list=True), "domains", "count",
            "Most-active technology domains", horizontal=True, height=380)


def tab_explorer(df, record_type: str):
    st.subheader(f"{record_type} explorer")
    d = df[df["record_type"] == record_type]
    st.caption(f"{len(d):,} {record_type.lower()} records match the current filters. "
               "Use the sidebar to narrow by mineral, domain, jurisdiction, year or keyword.")

    sort_col = st.selectbox("Sort by", ["year", "citations"], index=0,
                            key=f"sort_{record_type}")
    d = d.sort_values(sort_col, ascending=False)

    show = d.copy()
    show["minerals"] = show["minerals"].apply(lambda x: ", ".join(x))
    show["domains"] = show["domains"].apply(lambda x: ", ".join(x))
    cols = ["year", "record_type", "title", "minerals", "domains", "org", "country",
            "status", "citations", "source_db", "url"]
    st.dataframe(
        show[cols], hide_index=True, height=460, **STRETCH,
        column_config={
            "url": st.column_config.LinkColumn("link", display_text="open"),
            "title": st.column_config.TextColumn("title", width="large"),
            "citations": st.column_config.NumberColumn("cited"),
        },
    )
    st.download_button(
        f"⬇️ Download these {record_type.lower()} records (CSV)",
        data=S.to_csv_bytes(d), file_name=f"cm_{record_type.lower()}.csv",
        mime="text/csv",
    )


def tab_landscape(df):
    st.subheader("Technology landscape")
    st.caption("Cross-tabulation of critical minerals against value-chain technology "
               "domains — the intensity map of where innovation is happening.")

    mat = A.mineral_domain_matrix(df)
    if mat.empty:
        st.info("No data for the current filters.")
    else:
        # keep the most active minerals for readability
        mat = mat.loc[mat.sum(axis=1).sort_values(ascending=False).head(18).index]
        fig = go.Figure(data=go.Heatmap(
            z=mat.values, x=list(mat.columns), y=list(mat.index),
            colorscale="Tealgrn", colorbar=dict(title="records"),
            hovertemplate="%{y} · %{x}<br>%{z} records<extra></extra>",
        ))
        fig.update_layout(title="Mineral × technology-domain intensity",
                          height=560, margin=dict(l=10, r=10, t=48, b=10),
                          **PLOT_KW)
        st.plotly_chart(fig, **STRETCH)

    a, b = st.columns(2)
    with a:
        bar(A.top_counts(df, "org", n=14), "org", "count",
            "Top organizations (assignees / affiliations)", horizontal=True, height=460)
    with b:
        sun = A.explode(A.explode(df, "minerals"), "domains")
        if not sun.empty:
            grp = sun.groupby(["domains", "minerals"]).size().reset_index(name="count")
            fig = px.sunburst(grp, path=["domains", "minerals"], values="count",
                              color="domains", color_discrete_sequence=PALETTE,
                              title="Domain → mineral composition", **PLOT_KW)
            fig.update_layout(height=460, margin=dict(l=6, r=6, t=48, b=6))
            st.plotly_chart(fig, **STRETCH)


def tab_signals(df):
    st.subheader("Trends & emerging signals")
    st.caption("Momentum = activity in the last 3 complete years vs the prior 3. "
               "High growth flags where technology attention is shifting.")

    dim = st.radio("Analyze momentum by", ["domains", "minerals"], horizontal=True, key="sig_dim")
    ly = A.headline(df)["latest_year"]
    em = A.emerging(df, dimension=dim, latest_year=ly)
    if em.empty:
        st.info("Not enough dated records to compute momentum.")
        return

    top = em.head(12)
    fig = px.bar(top, x="growth_pct", y=dim, orientation="h",
                 color="growth_pct", color_continuous_scale="Tealgrn",
                 title=f"Fastest-growing {dim} (recent vs prior 3 yrs)", **PLOT_KW)
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=48, b=10),
                      yaxis={"categoryorder": "total ascending"},
                      coloraxis_showscale=False)
    st.plotly_chart(fig, **STRETCH)

    st.markdown("##### Momentum table")
    st.dataframe(
        em.rename(columns={dim: dim.rstrip("s").title(),
                           "growth_pct": "growth %", "recent_share": "recent share %"}),
        hide_index=True, **STRETCH,
    )

    st.markdown("##### Filing trajectory")
    pick = st.multiselect(f"Overlay specific {dim}", list(em[dim]),
                          default=list(top[dim].head(4)), key="sig_pick")
    if pick:
        d = A.explode(df.dropna(subset=["year"]), dim)
        d = d[d[dim].isin(pick)]
        ts = d.groupby(["year", dim]).size().reset_index(name="count").sort_values("year")
        fig = px.line(ts, x="year", y="count", color=dim, markers=True,
                      color_discrete_sequence=PALETTE, **PLOT_KW)
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10),
                          legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig, **STRETCH)


def tab_india(df):
    st.subheader("🇮🇳 India focus — self-reliance & IP gaps")
    st.caption("Aligns the IP landscape with policy: for each critical mineral we "
               "combine import-dependency with India's share of records to surface "
               "**priority gaps** — strategically vital minerals where domestic IP is thin.")

    gap = A.india_gap(df)
    hi = gap.head(10)
    fig = px.bar(hi, x="priority_gap", y="mineral", orientation="h",
                 color="dependency",
                 category_orders={"dependency": ["Very High", "High", "Moderate", "Low"]},
                 color_discrete_map={"Very High": "#a4443b", "High": "#d17a22",
                                     "Moderate": "#c8963e", "Low": "#5c8a3a"},
                 hover_data=["world", "india", "india_share", "note"],
                 title="Top priority gaps (dependency × low domestic IP share)", **PLOT_KW)
    fig.update_layout(height=440, margin=dict(l=10, r=10, t=48, b=10),
                      yaxis={"categoryorder": "total ascending"},
                      legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, **STRETCH)

    a, b = st.columns([3, 2])
    with a:
        st.markdown("##### Mineral-by-mineral")
        st.dataframe(
            gap[["mineral", "group", "dependency", "world", "india",
                 "india_share", "priority_gap", "note"]]
            .rename(columns={"india_share": "India %", "priority_gap": "gap"}),
            hide_index=True, height=420, **STRETCH,
            column_config={"note": st.column_config.TextColumn("policy note", width="large")},
        )
    with b:
        st.markdown("##### Most active Indian organizations")
        io = A.india_orgs(df, n=12)
        bar(io, "org", "count", "Indian assignees / institutions",
            horizontal=True, height=420)

    st.info(
        "**Reading the gap score** — a high score means the mineral is both "
        "import-critical for India *and* under-represented in Indian patents/research. "
        "These are natural targets for focused R&D missions, KABIL sourcing, and "
        "indigenous process development.",
        icon="🎯",
    )


def tab_watchlist(df):
    st.subheader("Watchlist & alerts")
    st.caption("Save technology/mineral watches and surface the newest activity — the "
               "monitoring layer a ministry or company would run continuously.")

    st.session_state.setdefault("watchlist", [])
    with st.form("add_watch", clear_on_submit=True):
        c = st.columns([2, 2, 1])
        wm = c[0].multiselect("Minerals", ALL_MINERALS, default=["Lithium"])
        wd = c[1].multiselect("Domains", ALL_DOMAINS, default=["Recycling & Urban Mining"])
        add = c[2].form_submit_button("➕ Add watch")
        if add and (wm or wd):
            label = f"{', '.join(wm) or 'any mineral'} · {', '.join(d for d in wd) or 'any domain'}"
            st.session_state["watchlist"].append({"minerals": wm, "domains": wd, "label": label})

    cutoff = st.slider("Flag records from year ≥", 2015, 2025, 2023, key="watch_cutoff")

    if not st.session_state["watchlist"]:
        st.info("No watches yet. Add one above (e.g. *Gallium · Separation & Refining*).")
        return

    for i, w in enumerate(list(st.session_state["watchlist"])):
        d = S.apply_filters(df, minerals=w["minerals"] or None, domains=w["domains"] or None)
        newest = S.new_since(d, cutoff)
        head = st.columns([6, 1])
        head[0].markdown(f"**🔔 {w['label']}** — {len(d)} total · "
                         f"**{len(newest)} new** since {cutoff}")
        if head[1].button("remove", key=f"rm_{i}"):
            st.session_state["watchlist"].pop(i)
            st.rerun()
        if not newest.empty:
            show = newest.head(8).copy()
            show["minerals"] = show["minerals"].apply(lambda x: ", ".join(x))
            st.dataframe(
                show[["year", "record_type", "title", "org", "country", "status", "url"]],
                hide_index=True, **STRETCH,
                column_config={"url": st.column_config.LinkColumn("link", display_text="open")},
            )
        st.divider()


def tab_about(df, meta):
    st.subheader("About this system")
    st.markdown(
        """
This tool answers **Problem Statement 2** of the **Critical Minerals Innovation
Hackathon 2026 (CMiH 2026)** — an intuitive, web-based system to track R&D and
patents relevant to the critical-minerals ecosystem, supporting India's
**National Critical Mineral Mission**.

**What it does**
- Unifies **patents** (USPTO PatentsView) and **research** (OpenAlex) into one
  normalized, searchable corpus.
- Auto-classifies every record against two controlled vocabularies: India's
  **30 critical minerals** and the **8-stage value chain** (exploration →
  mining → beneficiation → metallurgy → separation → recycling → substitution →
  environment).
- Delivers a **landscape** (mineral × domain heatmap, top players),
  **trend/emerging-signal** detection, and an **India self-reliance gap**
  analysis that ties IP density to import-dependency.
- Adds a **watchlist / alert** layer for continuous monitoring, plus CSV export.

**Architecture**
`connectors` (live APIs, graceful fallback) → `schema` (one record shape) →
`taxonomy` (minerals + domains + keyword classifier) → `store` (DataFrame,
filters) → `analytics` (pure, testable) → this Streamlit UI.

**Extending to production**
Add Espacenet/OPS and Lens.org connectors, WIPO PATENTSCOPE for Indian
applications, embeddings-based semantic search & clustering, and a scheduled
crawler writing to a database so alerts fire on genuinely new filings.
        """
    )
    st.markdown("**Technology domains**")
    st.markdown(
        " ".join(f'<span class="pill">{TECH_DOMAINS[d]["short"]} · {d}</span>'
                 for d in ALL_DOMAINS),
        unsafe_allow_html=True,
    )
    if meta.get("messages"):
        with st.expander("Live connector log"):
            for m in meta["messages"]:
                st.write("•", m)
    st.caption("Sample-mode figures are illustrative and generated to mirror real "
               "landscape patterns; they are not official statistics.")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    filt = sidebar()
    df_all, meta = get_dataframe()
    df = S.apply_filters(
        df_all,
        minerals=filt["minerals"] or None,
        domains=filt["domains"] or None,
        record_types=filt["record_types"] or None,
        year_range=filt["year_range"],
        text=filt["text"] or None,
    )

    tabs = st.tabs([
        "📊 Overview", "📄 Patents", "🔬 R&D", "🗺️ Landscape",
        "📈 Trends & Signals", "🇮🇳 India Focus", "🔔 Watchlist", "ℹ️ About",
    ])
    with tabs[0]:
        tab_overview(df, meta)
    with tabs[1]:
        tab_explorer(df, "Patent")
    with tabs[2]:
        tab_explorer(df, "Research")
    with tabs[3]:
        tab_landscape(df)
    with tabs[4]:
        tab_signals(df)
    with tabs[5]:
        tab_india(df)
    with tabs[6]:
        tab_watchlist(df)
    with tabs[7]:
        tab_about(df, meta)


if __name__ == "__main__":
    main()
