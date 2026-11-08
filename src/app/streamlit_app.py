"""
Materia Medica Nusantara
EthnoHack 2026 - Traditional Knowledge track

Streamlit dashboard over the knowledge graph built in src/pipeline/:
  Plant (PROSEA, Indonesia-documented) --TRADITIONAL_USE--> TraditionalUse (Dr. Duke's ETHNOBOT)
  Plant --CONTAINS--> Chemical (Dr. Duke's FARMACY)
  Chemical --HAS_ACTIVITY--> Activity (Dr. Duke's AGGREGAC)
  Plant.evidence_tier <- PubMed evidence-linking (NCBI E-utilities)
  Plant photo <- Wikipedia REST summary API (data/processed/plant_images.csv)

Visual layer (design tokens, CSS, header/footer, cards, pills) lives in styles.py.
This file holds data loading, graph-building, search logic, and page composition.
"""
import re
from pathlib import Path

import altair as alt
import networkx as nx
import pandas as pd
import streamlit as st
from pyvis.network import Network

from styles import (
    _html,
    card_thumb_html,
    hero_img_html,
    timeline_html,
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_PRIMARY,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SECONDARY,
    EVIDENCE_STYLES,
    GRAPH_NODE_COLORS,
    featured_pill_html,
    info_panel,
    inject_global_css,
    kpi_card,
    match_pill_html,
    prose,
    render_badges,
    render_footer,
    render_header,
    section_title,
    status_pill_html,
    thumb_html,
)

PROC = Path(__file__).resolve().parents[2] / "data" / "processed"
GALLERY_PAGE_SIZE = 20
GALLERY_COLS = 5


# ---------------------------------------------------------------------------
# Data loading (unchanged logic -- see src/pipeline/ for how these are built)
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    plants = pd.read_csv(PROC / "plants_seed.csv", dtype=str, keep_default_na=False)
    trad = pd.read_csv(PROC / "duke_traditional_uses_seed.csv", dtype=str, keep_default_na=False)
    chems = pd.read_csv(PROC / "duke_plant_chemicals_seed.csv", dtype=str, keep_default_na=False)
    acts = pd.read_csv(PROC / "duke_chemical_activities_seed.csv", dtype=str, keep_default_na=False)
    try:
        evidence = pd.read_csv(PROC / "pubmed_evidence.csv", dtype=str, keep_default_na=False)
    except FileNotFoundError:
        evidence = pd.DataFrame(
            columns=["GENUS", "SPECIES", "general_hits", "clinical_trial_hits", "review_hits", "evidence_tier"]
        )
    try:
        images = pd.read_csv(PROC / "plant_images.csv", dtype=str, keep_default_na=False)
    except FileNotFoundError:
        images = pd.DataFrame(columns=["GENUS", "SPECIES", "found", "image_path", "wikipedia_url"])

    plants["latin_name"] = plants["GENUS"] + " " + plants["SPECIES"]
    plants = plants.merge(evidence, on=["GENUS", "SPECIES"], how="left")
    plants = plants.merge(images, on=["GENUS", "SPECIES"], how="left", suffixes=("", "_img"))
    plants["evidence_tier"] = plants["evidence_tier"].fillna("not_queried")
    plants["image_path"] = plants["image_path"].fillna("")
    plants["wikipedia_url"] = plants["wikipedia_url"].fillna("")
    return plants, trad, chems, acts


@st.cache_data
def load_flagship_data():
    try:
        flagship = pd.read_csv(PROC / "flagship_plants.csv", dtype=str, keep_default_na=False)
        pubchem = pd.read_csv(PROC / "pubchem_compounds.csv", dtype=str, keep_default_na=False)
    except FileNotFoundError:
        return pd.DataFrame(columns=["GENUS", "SPECIES", "latin_name", "reason", "top_chemicals"]), pd.DataFrame()
    try:
        similarity = pd.read_csv(PROC / "chem_similarity.csv", dtype=str, keep_default_na=False)
    except FileNotFoundError:
        similarity = pd.DataFrame(columns=["CHEM", "match_type", "matched_drug", "tanimoto_similarity"])
    return flagship, pubchem, similarity


@st.cache_data
def load_historical_names():
    try:
        syn = pd.read_csv(PROC / "historical_synonyms.csv", dtype=str, keep_default_na=False)
    except FileNotFoundError:
        return pd.DataFrame(columns=["GENUS", "SPECIES", "synonym_name", "synonym_author", "year", "source_url"])
    syn["year"] = pd.to_numeric(syn["year"], errors="coerce")
    return syn.dropna(subset=["year"])


@st.cache_data
def load_nlp_conditions():
    try:
        df = pd.read_csv(PROC / "nlp_conditions.csv", dtype=str, keep_default_na=False)
    except FileNotFoundError:
        return pd.DataFrame(columns=["GENUS", "SPECIES", "category", "matched_terms", "n_mentions"])
    return df


@st.cache_data(show_spinner=False)
def load_dataset_stats():
    """Descriptive counts for the Overview tab (read-only, derived from the same files)."""
    seed = pd.read_csv(PROC / "plants_seed.csv", usecols=["GENUS", "SPECIES", "FAMILY"], dtype=str, keep_default_na=False)
    chems = pd.read_csv(PROC / "duke_plant_chemicals_seed.csv", usecols=["GENUS", "SPECIES", "CHEM"], dtype=str, keep_default_na=False)
    acts = pd.read_csv(PROC / "duke_chemical_activities_seed.csv", usecols=["CHEM", "ACTIVITY"], dtype=str, keep_default_na=False)
    trad = pd.read_csv(
        PROC / "duke_traditional_uses_seed.csv", usecols=["GENUS", "SPECIES", "TRADITIONAL_USE"], dtype=str, keep_default_na=False
    )

    pairs = set(zip(seed["GENUS"].str.lower(), seed["SPECIES"].str.lower()))
    chems_in = chems[[(g, s) in pairs for g, s in zip(chems["GENUS"].str.lower(), chems["SPECIES"].str.lower())]]
    trad_in = trad[[(g, s) in pairs for g, s in zip(trad["GENUS"].str.lower(), trad["SPECIES"].str.lower())]]
    compounds = set(chems_in["CHEM"])
    acts_in = acts[acts["CHEM"].isin(compounds)]

    families = seed.loc[seed["FAMILY"] != "", "FAMILY"]
    top_families = families.value_counts().head(8).rename_axis("family").reset_index(name="count")

    return {
        "species": len(seed),
        "families": int(families.nunique()),
        "compounds": len(compounds),
        "activities": int(acts_in["ACTIVITY"].nunique()),
        "trad_records": len(trad_in),
        "trad_unique": int(trad_in["TRADITIONAL_USE"].nunique()),
        "top_families": top_families,
    }


_REGISTRY_CODE = re.compile(r"^(npc\d+|[a-z]{0,4}\d{4,})$", re.IGNORECASE)


def display_compound_name(chem: str, pubchem_title: str) -> str:
    """Pick the most readable name for a compound.

    PubChem record titles are sometimes a registry code ("Npc209773"), a trade
    name ("Boro-Scopol") or a full systematic name, none of which read well on
    a card. Prefer the title when it clearly refers to the same common name as
    the source database entry; otherwise fall back to the source name, unless
    that one is itself a systematic string.
    """
    title = (pubchem_title or "").strip()
    common = chem.replace("-", " ").title()
    if not title or _REGISTRY_CODE.match(title) or len(title) > 38:
        return common

    norm_title = re.sub(r"[^a-z0-9]", "", title.lower())
    norm_chem = re.sub(r"[^a-z0-9]", "", chem.lower())
    if norm_title and norm_chem and (norm_title in norm_chem or norm_chem in norm_title):
        return title

    # Names disagree: keep the source name only if it is a clean common name.
    if re.fullmatch(r"[A-Za-z][A-Za-z\- ]*", chem):
        return common
    return title


SIMILARITY_LABELS = {
    "identical_to_known_drug": "Identical to approved drug",
    "structural_analog": "Structural analogue",
    "no_close_match": "No significant similarity",
}


# ---------------------------------------------------------------------------
# Graph building (unchanged logic, restyled rendering only)
# ---------------------------------------------------------------------------
def build_ego_graph(plant_row, trad, chems, acts, max_chems=12, max_acts_per_chem=6):
    g, s = plant_row["GENUS"], plant_row["SPECIES"]
    G = nx.Graph()
    plant_node = f"{g} {s}"
    G.add_node(plant_node, node_type="Plant")

    p_trad = trad[(trad["GENUS"].str.lower() == g.lower()) & (trad["SPECIES"].str.lower() == s.lower())]
    for use in p_trad["TRADITIONAL_USE"].drop_duplicates().head(15):
        G.add_node(use, node_type="TraditionalUse")
        G.add_edge(plant_node, use)

    p_chems = chems[(chems["GENUS"].str.lower() == g.lower()) & (chems["SPECIES"].str.lower() == s.lower())]
    chem_names = p_chems["CHEM"].drop_duplicates().head(max_chems)
    for chem in chem_names:
        G.add_node(chem, node_type="Chemical")
        G.add_edge(plant_node, chem)
        chem_acts = acts[acts["CHEM"] == chem]["ACTIVITY"].drop_duplicates().head(max_acts_per_chem)
        for act in chem_acts:
            G.add_node(act, node_type="Activity")
            G.add_edge(chem, act)

    return G


def render_pyvis(G: nx.Graph, height="550px"):
    net = Network(height=height, width="100%", bgcolor="#FFFFFF", font_color=COLOR_TEXT)
    for node, data in G.nodes(data=True):
        color = GRAPH_NODE_COLORS.get(data.get("node_type"), "#888888")
        net.add_node(
            node, label=node, color=color, title=data.get("node_type", ""),
            font={"face": "Inter, sans-serif", "size": 14, "color": COLOR_TEXT},
        )
    for u, v in G.edges():
        net.add_edge(u, v, color="#CBD2D9")
    net.set_options("""
    var options = {
      "physics": {"forceAtlas2Based": {"gravitationalConstant": -60}, "solver": "forceAtlas2Based"}
    }
    """)
    out_path = Path("/tmp") / "ego_graph.html"
    net.write_html(str(out_path), open_browser=False, notebook=False)
    html = out_path.read_text(encoding="utf-8")
    st.iframe(html, height=int(height.replace("px", "")) + 20)


def render_graph_legend():
    items = [
        ("Plant", GRAPH_NODE_COLORS["Plant"]),
        ("Traditional use", GRAPH_NODE_COLORS["TraditionalUse"]),
        ("Compound", GRAPH_NODE_COLORS["Chemical"]),
        ("Pharmacological activity", GRAPH_NODE_COLORS["Activity"]),
    ]
    dots = "".join(
        f"<span style='display:inline-flex;align-items:center;margin-right:18px;'>"
        f"<span style='width:9px;height:9px;border-radius:50%;background:{color};"
        f"display:inline-block;margin-right:6px;'></span>"
        f"<span style='font-size:12.5px;color:{COLOR_TEXT_MUTED};'>{label}</span></span>"
        for label, color in items
    )
    st.markdown(f"<div style='padding:2px 4px 2px 4px;'>{dots}</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def evidence_bar_chart(plants):
    counts = plants["evidence_tier"].value_counts().rename_axis("tier").reset_index(name="count")
    counts["label"] = counts["tier"].map(lambda k: EVIDENCE_STYLES.get(k, {}).get("label", k))
    counts["color"] = counts["tier"].map(lambda k: EVIDENCE_STYLES.get(k, {}).get("fg", COLOR_ACCENT))

    base = alt.Chart(counts).encode(
        y=alt.Y(
            "label:N", sort="-x", title=None,
            axis=alt.Axis(labelFontSize=13, labelColor=COLOR_TEXT_SECONDARY, domain=False, ticks=False,
                          labelPadding=6, labelLimit=240),
        ),
        x=alt.X("count:Q", title=None, axis=None, scale=alt.Scale(nice=False, padding=0)),
    )
    bars = base.mark_bar(size=20, cornerRadiusEnd=3).encode(
        color=alt.Color("color:N", scale=None, legend=None),
        tooltip=[alt.Tooltip("label:N", title="Evidence level"), alt.Tooltip("count:Q", title="Plants")],
    )
    labels = base.mark_text(align="left", dx=6, fontSize=13, fontWeight=600, color=COLOR_TEXT_SECONDARY).encode(
        text="count:Q"
    )
    return (bars + labels).properties(height=28 * len(counts) + 20).configure_view(stroke=None).configure(background="transparent")


def family_bar_chart(top_families):
    base = alt.Chart(top_families).encode(
        y=alt.Y(
            "family:N", sort="-x", title=None,
            axis=alt.Axis(labelFontSize=13, labelColor=COLOR_TEXT_SECONDARY, domain=False, ticks=False,
                          labelPadding=6, labelLimit=240),
        ),
        x=alt.X("count:Q", title=None, axis=None, scale=alt.Scale(nice=False, padding=0)),
    )
    bars = base.mark_bar(size=16, cornerRadiusEnd=3, color=COLOR_ACCENT).encode(
        tooltip=[alt.Tooltip("family:N", title="Family"), alt.Tooltip("count:Q", title="Species")]
    )
    labels = base.mark_text(align="left", dx=6, fontSize=12.5, fontWeight=600, color=COLOR_TEXT_SECONDARY).encode(
        text="count:Q"
    )
    return (bars + labels).properties(height=24 * len(top_families) + 20).configure_view(stroke=None).configure(background="transparent")


# ---------------------------------------------------------------------------
# Plant Library: cards, gallery, detail view
# ---------------------------------------------------------------------------
def plant_thumb_path(row):
    return (PROC / row["image_path"]) if row["image_path"] else None


def plant_card(row, flagship_keys, col):
    with col:
        with st.container(key=f"pcard_{row['GENUS']}_{row['SPECIES']}", gap=None):
            is_featured = (row["GENUS"], row["SPECIES"]) in flagship_keys
            local_first = row["LOCAL_NAMES_INDONESIA"].split(",")[0].strip()
            meta = " · ".join([p for p in (local_first, row["FAMILY"]) if p]) or "—"
            st.markdown(
                _html(f"""<div class="jpe-card">
                      {card_thumb_html(plant_thumb_path(row), featured=is_featured)}
                      <div class="jpe-card-body">
                        <span class="jpe-name">{row['latin_name']}</span>
                        <div class="jpe-meta">{meta}</div>
                        <div class="jpe-pill-row">{status_pill_html(row['evidence_tier'], size='small')}</div>
                      </div>
                    </div>"""),
                unsafe_allow_html=True,
            )
            if st.button("View details", key=f"detail_btn_{row['GENUS']}_{row['SPECIES']}", width="stretch"):
                st.session_state["selected_plant"] = row["latin_name"]
                st.rerun()


def featured_showcase_card(frow, plants, col):
    match = plants[(plants["GENUS"] == frow["GENUS"]) & (plants["SPECIES"] == frow["SPECIES"])]
    if not len(match):
        return
    row = match.iloc[0]
    with col:
        st.markdown(
            _html(f"""<div class="jpe-card">
                  {card_thumb_html(plant_thumb_path(row), featured=True)}
                  <div class="jpe-card-body" style="min-height:0;">
                    <span class="jpe-name">{row['latin_name']}</span>
                    <div class="jpe-meta">{row['LOCAL_NAMES_INDONESIA'].split(',')[0].strip() or row['FAMILY']}</div>
                  </div>
                </div>"""),
            unsafe_allow_html=True,
        )


def compound_card(crow, similarity, col):
    with col:
        png_rel = crow.get("structure_png", "")
        with st.container(border=True):
            if png_rel and (PROC / png_rel).exists():
                st.image(str(PROC / png_rel), width="stretch")
            st.markdown(f"**{display_compound_name(crow['CHEM'], crow['title'])}**")
            st.caption(f"CID {crow['cid']} · {crow['molecular_formula']} · MW {crow['molecular_weight']}")
            sim_row = similarity[similarity["CHEM"] == crow["CHEM"]]
            if len(sim_row):
                srow = sim_row.iloc[0]
                if srow["match_type"] in ("identical_to_known_drug", "structural_analog"):
                    exact = srow["match_type"] == "identical_to_known_drug"
                    label = f"{srow['matched_drug']} · {float(srow['tanimoto_similarity']):.2f}"
                    st.markdown(match_pill_html(label, exact=exact), unsafe_allow_html=True)
            st.markdown(
                f"<a href='{crow['pubchem_url']}' target='_blank' "
                f"style='font-size:12.5px;color:{COLOR_ACCENT};text-decoration:none;'>View on PubChem →</a>",
                unsafe_allow_html=True,
            )


def render_plant_detail(row, trad, chems, acts, flagship, flagship_keys, pubchem, similarity, historical_names, nlp_conditions):
    if st.button("← Back to library", type="tertiary", key="back_to_library"):
        st.session_state["selected_plant"] = None
        st.rerun()

    col_img, col_info = st.columns([1, 2], gap="large")
    with col_img:
        st.markdown(
            f"<div class='jpe-card'>{hero_img_html(plant_thumb_path(row))}</div>", unsafe_allow_html=True
        )
        if row["wikipedia_url"]:
            st.caption(f"Photo via [Wikipedia]({row['wikipedia_url']}) · see page for credit and licence")
    with col_info:
        is_featured = (row["GENUS"], row["SPECIES"]) in flagship_keys
        st.markdown(
            f"<div style='font-size:26px;font-weight:700;font-style:italic;color:{COLOR_TEXT};"
            f"letter-spacing:-0.01em;'>{row['latin_name']}{featured_pill_html() if is_featured else ''}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='font-size:13.5px;color:{COLOR_TEXT_MUTED};margin:2px 0 12px;'>"
            f"{row['FAMILY'] or '—'}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='font-size:14px;color:{COLOR_TEXT_SECONDARY};margin-bottom:10px;'>"
            f"<strong style='color:{COLOR_TEXT};'>Local names</strong> &nbsp;"
            f"{row['LOCAL_NAMES_INDONESIA'] or '—'}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(status_pill_html(row["evidence_tier"]), unsafe_allow_html=True)
        tier = row["evidence_tier"]
        if tier != "not_queried":
            st.caption(
                f"PubMed: {row.get('general_hits','–')} general · "
                f"{row.get('clinical_trial_hits','–')} clinical trials · "
                f"{row.get('review_hits','–')} reviews"
            )
        st.markdown(
            f"<div style='font-size:12.5px;margin-top:8px;'>"
            f"<a href='{row['SOURCE_URL']}' target='_blank' style='color:{COLOR_ACCENT};text-decoration:none;'>"
            f"Source: PROSEA / Pl@ntUse →</a></div>",
            unsafe_allow_html=True,
        )

    g, s = row["GENUS"], row["SPECIES"]
    p_trad = trad[(trad["GENUS"].str.lower() == g.lower()) & (trad["SPECIES"].str.lower() == s.lower())]
    p_chems = chems[(chems["GENUS"].str.lower() == g.lower()) & (chems["SPECIES"].str.lower() == s.lower())]
    p_chem_names = p_chems["CHEM"].drop_duplicates().tolist()
    n_activities = acts[acts["CHEM"].isin(p_chem_names)]["ACTIVITY"].nunique() if p_chem_names else 0

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    col_desc, col_facts = st.columns([3, 2], gap="large")
    with col_desc:
        section_title("Description and uses", eyebrow="PROSEA")
        prose(row["USES_TEXT"] or "No description available.")

        plant_conditions = nlp_conditions[
            (nlp_conditions["GENUS"] == row["GENUS"]) & (nlp_conditions["SPECIES"] == row["SPECIES"])
        ]
        if len(plant_conditions):
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            section_title(
                "Conditions mentioned in text",
                eyebrow="NLP extraction (spaCy) — matched directly from the paragraph above",
            )
            for _, crow in plant_conditions.sort_values("n_mentions", ascending=False).iterrows():
                st.markdown(
                    f"<span style='font-size:12.5px;color:{COLOR_TEXT_SECONDARY};font-weight:600;'>"
                    f"{crow['category']}</span>",
                    unsafe_allow_html=True,
                )
                render_badges(crow["matched_terms"].split("; "), kind="condition")
    with col_facts:
        section_title("At a glance")
        facts = [
            ("Traditional uses recorded", f"{p_trad['TRADITIONAL_USE'].nunique():,}"),
            ("Compounds recorded", f"{len(p_chem_names):,}"),
            ("Reported activities", f"{n_activities:,}"),
            ("PubMed publications", f"{row.get('general_hits', '–')}"),
            ("Clinical-trial publications", f"{row.get('clinical_trial_hits', '–')}"),
            ("Botanical family", row["FAMILY"] or "—"),
        ]
        rows_html = "".join(
            f"<div class='jpe-fact'><span class='jpe-fact-label'>{label}</span>"
            f"<span class='jpe-fact-value'>{value}</span></div>"
            for label, value in facts
        )
        st.markdown(
            _html(f"<div class='jpe-card' style='padding:6px 16px;'>{rows_html}</div>"),
            unsafe_allow_html=True,
        )

        hist = historical_names[
            (historical_names["GENUS"].str.lower() == g.lower()) & (historical_names["SPECIES"].str.lower() == s.lower())
        ]
        if len(hist):
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            section_title("Name history", eyebrow="Across eras — PROSEA synonymy")
            entries = list(zip(hist["year"].astype(int), hist["synonym_name"], hist["synonym_author"]))
            st.markdown(
                _html(f"<div class='jpe-card' style='padding:14px 16px 2px;'>"
                      f"{timeline_html(entries, row['latin_name'])}</div>"),
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    col_a, col_b = st.columns(2, gap="large")
    with col_a:
        section_title("Traditional uses", eyebrow="Dr. Duke's ethnobotanical records")
        if len(p_trad):
            uses = p_trad["TRADITIONAL_USE"].drop_duplicates().tolist()
            render_badges(sorted(uses)[:40], kind="use")
            if len(uses) > 40:
                st.caption(f"+{len(uses) - 40} more")
            countries = sorted({c for c in p_trad["COUNTRY"].dropna() if c})
            if countries:
                st.caption(f"Documented in: {', '.join(countries)}")
        else:
            st.caption("No records for this species.")

    with col_b:
        section_title("Compounds and activities", eyebrow="Dr. Duke's phytochemical records")
        if len(p_chems):
            chem_list = p_chems["CHEM"].drop_duplicates().tolist()
            chem_acts = acts[acts["CHEM"].isin(chem_list)][["CHEM", "ACTIVITY"]].drop_duplicates()
            n_acts_per_chem = chem_acts.groupby("CHEM").size().sort_values(ascending=False)
            for chem in n_acts_per_chem.head(8).index:
                acts_for_chem = sorted(chem_acts[chem_acts["CHEM"] == chem]["ACTIVITY"].tolist())
                st.markdown(
                    f"<div style='font-weight:600;font-size:13.5px;color:{COLOR_PRIMARY};margin-top:6px;'>"
                    f"{chem}</div>",
                    unsafe_allow_html=True,
                )
                render_badges(acts_for_chem[:12], kind="activity")
            if len(n_acts_per_chem) > 8:
                with st.expander(f"Show all {len(n_acts_per_chem)} compounds"):
                    for chem in n_acts_per_chem.index[8:]:
                        acts_for_chem = sorted(chem_acts[chem_acts["CHEM"] == chem]["ACTIVITY"].tolist())
                        st.markdown(f"**{chem}**")
                        render_badges(acts_for_chem[:12], kind="activity")
        else:
            st.caption("No compound data for this species.")

    if (row["GENUS"], row["SPECIES"]) in flagship_keys:
        frow = flagship[(flagship["GENUS"] == row["GENUS"]) & (flagship["SPECIES"] == row["SPECIES"])].iloc[0]
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        section_title("Key compounds", frow["reason"], eyebrow="PubChem structures")
        top_chem_names = [c.strip() for c in frow["top_chemicals"].split(";") if c.strip()]
        matches = pubchem[pubchem["CHEM"].isin(top_chem_names) & (pubchem["found"] == "True")]
        if len(matches):
            cols = st.columns(4, gap="medium")
            for i, (_, crow) in enumerate(matches.iterrows()):
                compound_card(crow, similarity, cols[i % 4])
        else:
            st.caption("No PubChem match found for this plant's compounds.")

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    section_title("Compound–activity network")
    with st.container(border=True):
        render_pyvis(build_ego_graph(row, trad, chems, acts))
        render_graph_legend()


def render_gallery(plants, flagship_keys):
    with st.container(border=True):
        search = st.text_input(
            "Search", key="gallery_search", placeholder="Latin or local name — e.g. Curcuma longa, kunyit",
            label_visibility="collapsed",
        )
        col_f1, col_f2 = st.columns(2)
        family_filter = col_f1.multiselect("Plant family", sorted(plants["FAMILY"].unique()), key="family_filter")
        tier_filter = col_f2.multiselect(
            "Evidence level",
            options=list(EVIDENCE_STYLES.keys()),
            format_func=lambda k: EVIDENCE_STYLES[k]["label"],
            key="tier_filter",
        )

    view = plants.copy()
    if family_filter:
        view = view[view["FAMILY"].isin(family_filter)]
    if tier_filter:
        view = view[view["evidence_tier"].isin(tier_filter)]
    if search:
        mask = view["latin_name"].str.contains(search, case=False) | view[
            "LOCAL_NAMES_INDONESIA"
        ].str.contains(search, case=False)
        view = view[mask]

    # Plants with a photo are shown on the first pages (reads better in a live demo);
    # within each group, the original data-richness ranking is preserved.
    view = view.assign(_has_image=(view["image_path"] != "")).sort_values(
        "_has_image", ascending=False, kind="stable"
    )

    n_pages = max(1, -(-len(view) // GALLERY_PAGE_SIZE))
    page = min(st.session_state.get("gallery_page", 0), n_pages - 1)
    start, end = page * GALLERY_PAGE_SIZE, min((page + 1) * GALLERY_PAGE_SIZE, len(view))

    st.markdown(
        f"<div style='font-size:13px;color:{COLOR_TEXT_MUTED};margin:14px 0 10px;'>"
        + (f"Showing {start + 1}–{end} of {len(view)} plants" if len(view) else "No plants match your filters")
        + "</div>",
        unsafe_allow_html=True,
    )

    page_rows = view.iloc[start:end]
    for row_start in range(0, len(page_rows), GALLERY_COLS):
        cols = st.columns(GALLERY_COLS, gap="medium")
        chunk = page_rows.iloc[row_start : row_start + GALLERY_COLS]
        for col, (_, prow) in zip(cols, chunk.iterrows()):
            plant_card(prow, flagship_keys, col)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    nav1, nav2, nav3 = st.columns([1, 2, 1])
    with nav1:
        if st.button("Previous", disabled=page <= 0, key="gallery_prev", width="stretch"):
            st.session_state["gallery_page"] = page - 1
            st.rerun()
    with nav2:
        st.markdown(
            f"<div style='text-align:center;color:{COLOR_TEXT_MUTED};font-size:13px;padding-top:8px;'>"
            f"Page {page + 1} of {n_pages}</div>",
            unsafe_allow_html=True,
        )
    with nav3:
        if st.button("Next", disabled=page >= n_pages - 1, key="gallery_next", width="stretch"):
            st.session_state["gallery_page"] = page + 1
            st.rerun()

    with st.expander("View as data table"):
        table_view = view[
            ["latin_name", "FAMILY", "LOCAL_NAMES_INDONESIA", "n_duke_chemicals", "n_duke_traditional_uses", "evidence_tier"]
        ].rename(
            columns={
                "latin_name": "Latin name",
                "FAMILY": "Family",
                "LOCAL_NAMES_INDONESIA": "Local names (Indonesia)",
                "n_duke_chemicals": "Compounds",
                "n_duke_traditional_uses": "Traditional uses",
                "evidence_tier": "Evidence level",
            }
        )
        table_view["Compounds"] = pd.to_numeric(table_view["Compounds"], errors="coerce").fillna(0)
        table_view["Traditional uses"] = pd.to_numeric(table_view["Traditional uses"], errors="coerce").fillna(0)
        table_view["Evidence level"] = table_view["Evidence level"].map(
            lambda k: EVIDENCE_STYLES.get(k, {}).get("label", k)
        )
        st.dataframe(
            table_view,
            width="stretch",
            height=420,
            hide_index=True,
            column_config={
                "Compounds": st.column_config.ProgressColumn(
                    "Compounds", min_value=0, max_value=max(1, int(table_view["Compounds"].max())), format="%d"
                ),
                "Traditional uses": st.column_config.ProgressColumn(
                    "Traditional uses",
                    min_value=0,
                    max_value=max(1, int(table_view["Traditional uses"].max())),
                    format="%d",
                ),
            },
        )


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
def render_overview(plants, flagship, stats):
    st.markdown(
        _html(f"""
        <div style="margin:0 0 18px 0;font-size:13.5px;color:{COLOR_TEXT_MUTED};line-height:1.6;">
          Built from PROSEA species records, Dr. Duke's phytochemical and ethnobotanical databases,
          PubMed literature, and PubChem structures. Evidence levels are automated literature
          screening, not clinical assessment — see <em>Methodology and limitations</em> below.
        </div>
        """),
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4, gap="medium")
    with c1:
        kpi_card("Plant species", f"{stats['species']:,}", f"{stats['families']} botanical families")
    with c2:
        kpi_card("Distinct compounds", f"{stats['compounds']:,}", "Dr. Duke's phytochemical records")
    with c3:
        kpi_card("Reported activities", f"{stats['activities']:,}", "Compound–activity relationships")
    with c4:
        kpi_card(
            "Species with clinical literature",
            f"{int((plants['evidence_tier'] == 'clinical_evidence').sum()):,}",
            "PubMed clinical-trial publication type",
        )

    st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
    col_left, col_right = st.columns([3, 2], gap="large")
    with col_left:
        section_title("Evidence distribution", "Modern pharmacological evidence level across all species")
        with st.container(border=True):
            st.altair_chart(evidence_bar_chart(plants), width="stretch")
    with col_right:
        section_title("Largest families", "Species count by botanical family")
        with st.container(border=True):
            st.altair_chart(family_bar_chart(stats["top_families"]), width="stretch")

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    section_title(
        "Featured species",
        f"{len(flagship)} plants profiled in depth with PubChem structures and structural-similarity "
        "screening — showing 12",
    )
    show = flagship.head(12)
    for row_start in range(0, len(show), 6):
        cols = st.columns(6, gap="medium")
        chunk = show.iloc[row_start : row_start + 6]
        for col, (_, frow) in zip(cols, chunk.iterrows()):
            featured_showcase_card(frow, plants, col)

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
    with st.expander("Methodology and limitations"):
        st.markdown(
            _html(f"""
            <div class='jpe-prose'>
            <strong>Evidence levels.</strong> Each species is queried against PubMed via NCBI E-utilities.
            <em>Clinical evidence</em> means publications with a clinical-trial or RCT publication type were
            found; <em>preclinical or review</em> means pharmacology, bioactivity or review publications were
            found; <em>no evidence found</em> means our automated query returned nothing — which is not
            evidence that a plant is inactive.<br><br>
            <strong>Species selection.</strong> {stats['species']} species were selected from 663 PROSEA
            candidates with documented Indonesian vernacular names, ranked by how complete the downstream
            data was. This is neither a random sample nor an exhaustive list of jamu plants.<br><br>
            <strong>Name matching.</strong> Sources are joined on genus and species strings and have not been
            reconciled against a taxonomic authority, so synonyms may cause missed matches. Dr. Duke's
            database was last updated around 2015–2016.
            </div>
            """),
            unsafe_allow_html=True,
        )


def render_similarity(flagship, similarity):
    n_drugs = similarity["matched_drug"].nunique() if len(similarity) else 0
    section_title(
        "Structural similarity screening",
        f"Morgan fingerprints (RDKit, radius 2, 2048 bits) compared by Tanimoto similarity against "
        f"{n_drugs} reference drugs, across {len(flagship)} featured species",
    )
    info_panel(
        "Structural similarity is a computational screening signal, not evidence of biological activity "
        "or clinical efficacy. 2D fingerprints also cannot distinguish stereoisomers, so molecules that "
        "differ only in 3D configuration can show up as an exact match.",
        kind="warning",
    )

    if not len(similarity):
        st.info("Run src/pipeline/chem_similarity.py to generate this data.")
        return

    chem_to_plants = {}
    for _, frow in flagship.iterrows():
        for c in frow["top_chemicals"].split(";"):
            c = c.strip()
            if c:
                chem_to_plants.setdefault(c, []).append(frow["latin_name"])

    sim_view = similarity.copy()
    sim_view["tanimoto_similarity"] = pd.to_numeric(sim_view["tanimoto_similarity"], errors="coerce")
    sim_view["source_plants"] = sim_view["CHEM"].map(lambda c: ", ".join(chem_to_plants.get(c, [])))

    identical = sim_view[sim_view["match_type"] == "identical_to_known_drug"]
    section_title(
        "Compounds identical to approved drugs",
        f"{len(identical)} compounds in the featured species are the same molecule as an established drug",
    )
    cols = st.columns(4, gap="medium")
    for i, (_, irow) in enumerate(identical.iterrows()):
        with cols[i % 4]:
            st.markdown(
                _html(f"""<div class="jpe-card jpe-cmp-card" style="padding:14px 16px;">
                      <div class="jpe-cmp-name">{display_compound_name(irow['CHEM'], irow['title'])}</div>
                      <div style="margin:6px 0 8px;">{match_pill_html('Exact match', exact=True)}</div>
                      <div style="font-size:12.5px;color:{COLOR_TEXT_SECONDARY};">
                        Drug: <strong>{irow['matched_drug']}</strong></div>
                      <div style="font-size:12.5px;color:{COLOR_TEXT_MUTED};font-style:italic;margin-top:2px;">
                        {irow['source_plants']}</div>
                    </div>"""),
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
    analog = sim_view[sim_view["match_type"] == "structural_analog"].sort_values(
        "tanimoto_similarity", ascending=False
    )
    section_title("Structural analogues", "Different molecules with similar fingerprints — candidates for review")
    analog = analog.assign(
        display_name=[display_compound_name(c, t) for c, t in zip(analog["CHEM"], analog["title"])]
    )
    st.dataframe(
        analog[["display_name", "CHEM", "matched_drug", "tanimoto_similarity", "source_plants"]].rename(
            columns={
                "display_name": "Compound",
                "CHEM": "Source database name",
                "matched_drug": "Similar to",
                "tanimoto_similarity": "Tanimoto",
                "source_plants": "Source species",
            }
        ),
        width="stretch",
        hide_index=True,
        column_config={
            "Tanimoto": st.column_config.ProgressColumn("Tanimoto", min_value=0.0, max_value=1.0, format="%.2f"),
        },
    )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Materia Medica Nusantara", layout="wide", initial_sidebar_state="collapsed")
    inject_global_css()
    render_header()

    plants, trad, chems, acts = load_data()
    flagship, pubchem, similarity = load_flagship_data()
    historical_names = load_historical_names()
    nlp_conditions = load_nlp_conditions()
    stats = load_dataset_stats()
    flagship_keys = set(zip(flagship["GENUS"], flagship["SPECIES"])) if len(flagship) else set()

    st.session_state.setdefault("selected_plant", None)
    st.session_state.setdefault("gallery_page", 0)

    tab_overview, tab_gallery, tab_graph, tab_disease, tab_similarity = st.tabs(
        ["Overview", "Plant Library", "Network Explorer", "Search by Activity", "Structural Similarity"]
    )

    with tab_overview:
        render_overview(plants, flagship, stats)

    with tab_gallery:
        if st.session_state["selected_plant"]:
            sel_row = plants[plants["latin_name"] == st.session_state["selected_plant"]]
            if len(sel_row):
                render_plant_detail(sel_row.iloc[0], trad, chems, acts, flagship, flagship_keys, pubchem, similarity, historical_names, nlp_conditions)
            else:
                st.session_state["selected_plant"] = None
                st.rerun()
        else:
            render_gallery(plants, flagship_keys)

    with tab_graph:
        section_title("Network explorer", "One plant's local subgraph at a time — the full graph is too dense to read")
        chosen2 = st.selectbox("Select a plant", plants["latin_name"].tolist(), key="graph_select")
        row2 = plants[plants["latin_name"] == chosen2].iloc[0]
        G2 = build_ego_graph(row2, trad, chems, acts, max_chems=20, max_acts_per_chem=8)
        st.caption(f"{G2.number_of_nodes()} nodes · {G2.number_of_edges()} edges")
        with st.container(border=True):
            render_pyvis(G2, height="650px")
            render_graph_legend()

    with tab_disease:
        section_title(
            "Search by activity", "Reverse search: find species containing compounds reported for an activity"
        )
        all_activities = sorted(acts["ACTIVITY"].dropna().unique())
        # The alphabetically-first entry ("'Smart-Drug'") matches nothing, which would
        # make this tab open on an empty result; start on a well-populated activity instead.
        preferred = next(
            (a for a in ("Antiinflammatory", "Antioxidant", "Antibacterial", "Analgesic", "Antitumor")
             if a in all_activities),
            all_activities[0] if all_activities else None,
        )
        chosen_act = st.selectbox(
            "Pharmacological activity",
            all_activities,
            index=all_activities.index(preferred) if preferred in all_activities else 0,
            key="activity_select",
        )

        chem_for_act = acts[acts["ACTIVITY"] == chosen_act]["CHEM"].drop_duplicates()
        plant_hits = chems[chems["CHEM"].isin(chem_for_act)][["GENUS", "SPECIES", "CHEM"]].drop_duplicates()
        plant_hits["latin_name"] = plant_hits["GENUS"] + " " + plant_hits["SPECIES"]
        plant_hits = plant_hits[plant_hits["latin_name"].isin(plants["latin_name"])]

        grouped = plant_hits.groupby("latin_name")["CHEM"].apply(lambda s: sorted(set(s))).reset_index()
        grouped["n_chem"] = grouped["CHEM"].apply(len)
        grouped = grouped.sort_values("n_chem", ascending=False)

        st.markdown(
            f"<div style='font-size:14px;color:{COLOR_TEXT_SECONDARY};margin:10px 0 18px;'>"
            f"<strong style='color:{COLOR_TEXT};font-size:20px;'>{len(grouped)}</strong> of "
            f"{stats['species']} species contain compounds reported for "
            f"<em>{chosen_act}</em></div>",
            unsafe_allow_html=True,
        )

        if not len(grouped):
            info_panel(
                f"No species in this dataset contain a compound recorded with <em>{chosen_act}</em> "
                "activity. Try another activity — some entries in the source database are rare or "
                "apply only to species outside this collection.",
                kind="info",
            )

        if len(grouped):
            col_chart, col_list = st.columns([2, 3], gap="large")
            with col_chart:
                section_title("Top species", "By number of related compounds")
                top = grouped.head(15)
                base = alt.Chart(top).encode(
                    y=alt.Y(
                        "latin_name:N", sort="-x", title=None,
                        axis=alt.Axis(
                            labelFontSize=12.5, labelColor=COLOR_TEXT_SECONDARY, labelFontStyle="italic",
                            domain=False, ticks=False, labelPadding=6, labelLimit=240,
                        ),
                    ),
                    x=alt.X("n_chem:Q", title=None, axis=None, scale=alt.Scale(nice=False, padding=0)),
                )
                bars = base.mark_bar(size=14, cornerRadiusEnd=3, color=COLOR_ACCENT).encode(
                    tooltip=[alt.Tooltip("latin_name:N", title="Species"), alt.Tooltip("n_chem:Q", title="Compounds")]
                )
                labels = base.mark_text(
                    align="left", dx=5, fontSize=12, fontWeight=600, color=COLOR_TEXT_SECONDARY
                ).encode(text="n_chem:Q")
                st.altair_chart((bars + labels).properties(height=22 * len(top) + 20).configure_view(stroke=None).configure(background="transparent"), width="stretch")
            with col_list:
                section_title("Compounds by species")
                for _, grow in grouped.head(20).iterrows():
                    st.markdown(
                        f"<div style='font-style:italic;font-weight:600;font-size:13.5px;color:{COLOR_TEXT};"
                        f"margin-top:8px;'>{grow['latin_name']} "
                        f"<span style='font-style:normal;font-weight:400;color:{COLOR_TEXT_MUTED};'>"
                        f"· {grow['n_chem']}</span></div>",
                        unsafe_allow_html=True,
                    )
                    render_badges(grow["CHEM"], kind="chem")
                if len(grouped) > 20:
                    with st.expander(f"View all {len(grouped)} species"):
                        st.dataframe(
                            grouped.assign(CHEM=grouped["CHEM"].apply(lambda c: ", ".join(c))).rename(
                                columns={"latin_name": "Species", "CHEM": "Related compounds", "n_chem": "Compounds"}
                            ),
                            width="stretch",
                            hide_index=True,
                        )

    with tab_similarity:
        render_similarity(flagship, similarity)

    render_footer()


if __name__ == "__main__":
    main()
