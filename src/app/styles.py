"""
Design system and reusable presentational components for the dashboard.

Visual layer only: colors, typography, CSS injection, and small stateless
rendering helpers. No data loading, processing, graph-building, or search
logic lives here -- see streamlit_app.py for that.
"""
import base64
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
COLOR_PRIMARY = "#0B3C5D"       # deep navy
COLOR_ACCENT = "#1A7F8E"        # clinical teal
COLOR_BG = "#F7F9FB"
COLOR_SURFACE = "#FFFFFF"
COLOR_TEXT = "#1F2933"
COLOR_TEXT_SECONDARY = "#52606D"
COLOR_TEXT_MUTED = "#7B8794"
COLOR_BORDER = "#E4E7EB"

EVIDENCE_STYLES = {
    "clinical_evidence": {"label": "Clinical evidence", "fg": "#2E7D32", "bg": "#E8F5E9"},
    "preclinical_or_review_evidence": {"label": "Preclinical or review", "fg": "#B7791F", "bg": "#FFF8E1"},
    "traditional_only_no_modern_lit_found": {"label": "No evidence found", "fg": "#616E7C", "bg": "#F0F2F5"},
    "not_queried": {"label": "Not yet assessed", "fg": "#3E4C59", "bg": "#E4E7EB"},
}

BADGE_STYLES = {
    "use": {"fg": "#7C5E10", "bg": "#FBF3E0"},       # traditional use: warm sand
    "chem": {"fg": "#0B3C5D", "bg": "#E6EEF5"},      # compound: navy-blue
    "activity": {"fg": "#9B2C2C", "bg": "#FCEDED"},  # pharmacological activity: muted rose
    "condition": {"fg": "#0F5C5C", "bg": "#E3F3F3"}, # NLP-extracted condition: teal
}

GRAPH_NODE_COLORS = {
    "Plant": COLOR_PRIMARY,
    "TraditionalUse": "#B7791F",
    "Chemical": COLOR_ACCENT,
    "Activity": "#9B2C2C",
}

_LEAF_SVG = (
    f"<svg width='32' height='32' viewBox='0 0 24 24' fill='none' stroke='#9AA5B1' stroke-width='1.3'>"
    f"<path d='M12 2C7 2 3 6 3 12c0 5 4 9 9 9 0-7 3-10 9-10 0-5-4-9-9-9z'/><path d='M12 21V8'/></svg>"
)


def _html(markup: str) -> str:
    """Flatten indentation before handing markup to st.markdown.

    Streamlit runs the string through a Markdown parser first, and lines
    indented by four or more spaces are treated as a code block -- which makes
    a <style> block render as visible text on the page instead of applying.
    """
    return "\n".join(line.strip() for line in markup.splitlines() if line.strip())


def inject_global_css():
    st.markdown(
        _html(f"""
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
        html, body, [class*="css"], .stMarkdown, .stText {{
            font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
        }}
        .stApp {{ background-color: {COLOR_BG}; }}
        #MainMenu, footer, [data-testid="stDecoration"], [data-testid="stToolbar"] {{ visibility: hidden; }}
        header[data-testid="stHeader"] {{ display: none; }}
        .block-container {{ max-width: 1280px; padding-top: 2.25rem; padding-bottom: 2rem; }}

        h1, h2, h3, h4 {{ color: {COLOR_TEXT}; letter-spacing: -0.01em; }}
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{
            color: {COLOR_TEXT_MUTED} !important; font-size: 13px !important;
        }}

        /* Tabs as a clean top navigation bar */
        div[data-baseweb="tab-list"] {{ gap: 4px; }}
        button[data-baseweb="tab"] {{
            font-weight: 500; font-size: 15px; color: {COLOR_TEXT_SECONDARY};
            padding-left: 14px; padding-right: 14px;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{ color: {COLOR_PRIMARY}; }}
        div[data-baseweb="tab-highlight"] {{ background-color: {COLOR_ACCENT}; height: 2px; }}
        div[data-baseweb="tab-border"] {{ background-color: {COLOR_BORDER}; }}

        /* Buttons */
        .stButton > button {{
            border-radius: 8px; font-weight: 500; font-size: 14px;
            border: 1px solid {COLOR_BORDER}; color: {COLOR_PRIMARY};
            transition: border-color .15s ease, background .15s ease;
        }}
        .stButton > button:hover {{ border-color: {COLOR_ACCENT}; color: {COLOR_ACCENT}; }}
        .stButton > button[kind="primary"] {{
            background-color: {COLOR_PRIMARY}; border-color: {COLOR_PRIMARY}; color: #fff;
        }}
        .stButton > button[kind="tertiary"] {{
            border: none; color: {COLOR_PRIMARY}; font-weight: 600; padding-left: 0;
        }}

        /* Bordered containers used as cards */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: {COLOR_SURFACE}; border-radius: 10px;
            box-shadow: 0 1px 3px rgba(16,24,40,0.06);
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] > div {{
            border-radius: 10px !important; border-color: {COLOR_BORDER} !important;
        }}

        /* Inputs */
        div[data-baseweb="select"] > div, .stTextInput > div > div {{ border-radius: 8px; }}
        .stTextInput label, div[data-testid="stMultiSelect"] label, .stSelectbox label {{
            font-size: 13px !important; font-weight: 500 !important; color: {COLOR_TEXT_SECONDARY} !important;
        }}

        /* Dataframes & expanders */
        [data-testid="stDataFrame"] {{ border: 1px solid {COLOR_BORDER}; border-radius: 10px; }}
        details[data-testid="stExpander"] {{
            border: 1px solid {COLOR_BORDER} !important; border-radius: 10px !important;
            background: {COLOR_SURFACE};
        }}

        /* Reusable primitives */
        .jpe-card {{
            background: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; border-radius: 10px;
            overflow: hidden; box-shadow: 0 1px 3px rgba(16,24,40,0.06);
            transition: box-shadow .18s ease, transform .18s ease;
        }}
        .jpe-card:hover {{ box-shadow: 0 4px 12px rgba(16,24,40,0.10); }}
        .jpe-thumb {{
            width: 100%; height: 150px; object-fit: cover; display: block;
            background: #EEF2F5;
        }}
        .jpe-thumb-empty {{
            width: 100%; height: 150px; display: flex; align-items: center;
            justify-content: center; background: #EEF2F5;
        }}
        .jpe-thumb-wrap {{ position: relative; line-height: 0; }}
        .jpe-hero-img {{
            width: 100%; height: 260px; object-fit: cover; display: block; background: #EEF2F5;
        }}
        .jpe-hero-empty {{
            width: 100%; height: 260px; display: flex; align-items: center;
            justify-content: center; background: #EEF2F5;
        }}
        .jpe-cmp-card {{ min-height: 132px; display: flex; flex-direction: column; }}
        .jpe-cmp-name {{
            font-weight: 600; font-size: 14.5px; color: {COLOR_TEXT}; line-height: 1.35;
            display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
            overflow: hidden;
        }}
        .jpe-timeline {{ position: relative; padding-left: 22px; }}
        .jpe-timeline::before {{
            content: ""; position: absolute; left: 5px; top: 6px; bottom: 6px;
            width: 2px; background: {COLOR_BORDER};
        }}
        .jpe-tl-item {{ position: relative; padding-bottom: 14px; }}
        .jpe-tl-item::before {{
            content: ""; position: absolute; left: -22px; top: 3px;
            width: 10px; height: 10px; border-radius: 50%; background: {COLOR_BORDER};
            border: 2px solid {COLOR_SURFACE};
        }}
        .jpe-tl-item.jpe-tl-current::before {{ background: {COLOR_ACCENT}; }}
        .jpe-tl-year {{ font-size: 11.5px; font-weight: 700; color: {COLOR_ACCENT}; letter-spacing: .03em; }}
        .jpe-tl-name {{ font-style: italic; font-weight: 600; font-size: 14px; color: {COLOR_TEXT}; }}
        .jpe-tl-author {{ font-size: 12px; color: {COLOR_TEXT_MUTED}; }}
        .jpe-fact {{
            display: flex; justify-content: space-between; align-items: baseline;
            padding: 7px 0; border-bottom: 1px solid {COLOR_BORDER}; font-size: 13.5px;
        }}
        .jpe-fact:last-child {{ border-bottom: none; }}
        .jpe-fact-label {{ color: {COLOR_TEXT_MUTED}; }}
        .jpe-fact-value {{ color: {COLOR_TEXT}; font-weight: 600; }}
        .jpe-featured {{
            position: absolute; top: 8px; right: 8px;
            background: rgba(255,255,255,0.94); color: {COLOR_PRIMARY};
            border-radius: 999px; padding: 2px 9px; font-size: 10.5px; font-weight: 600;
            letter-spacing: .02em; line-height: 1.6; box-shadow: 0 1px 2px rgba(16,24,40,.12);
        }}
        .jpe-card-body {{
            padding: 10px 12px 12px 12px; min-height: 96px;
            display: flex; flex-direction: column;
        }}
        .jpe-pill-row {{ margin-top: auto; padding-top: 8px; }}
        .jpe-name {{
            font-style: italic; font-weight: 600; font-size: 14.5px; color: {COLOR_TEXT};
            line-height: 1.35; display: block;
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }}
        .jpe-meta {{
            font-size: 12.5px; color: {COLOR_TEXT_MUTED}; margin-top: 2px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }}
        .jpe-prose {{ max-width: 68ch; font-size: 15px; line-height: 1.65; color: {COLOR_TEXT_SECONDARY}; }}

        /* Plant card: HTML card + Streamlit button read as one unit */
        [class*="st-key-pcard_"] .jpe-card {{
            border-bottom-left-radius: 0; border-bottom-right-radius: 0; border-bottom: none;
        }}
        [class*="st-key-pcard_"] .stButton > button {{
            border-top-left-radius: 0; border-top-right-radius: 0;
            border-top: 1px solid {COLOR_BORDER};
            background: {COLOR_SURFACE};
            color: {COLOR_TEXT_SECONDARY};
            font-size: 13px;
            box-shadow: 0 1px 3px rgba(16,24,40,0.06);
        }}
        [class*="st-key-pcard_"] .stButton > button:hover {{
            background: #F3F7F8; color: {COLOR_ACCENT}; border-color: {COLOR_BORDER};
            border-top-color: {COLOR_BORDER};
        }}
        .jpe-eyebrow {{
            font-size: 11.5px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
            color: {COLOR_ACCENT};
        }}
        </style>
        """),
        unsafe_allow_html=True,
    )


def render_header():
    st.markdown(
        _html(f"""
        <div style="padding:2px 0 14px 0;border-bottom:1px solid {COLOR_BORDER};margin-bottom:22px;
                    display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:8px;">
          <div>
            <div style="font-size:26px;font-weight:700;color:{COLOR_PRIMARY};letter-spacing:-0.02em;">
              Materia Medica Nusantara
            </div>
            <div style="font-size:14px;color:{COLOR_TEXT_SECONDARY};margin-top:1px;">
              Mapping Indonesian jamu species to modern pharmacological evidence
            </div>
          </div>
          <div style="font-size:12.5px;color:{COLOR_TEXT_MUTED};">
            Research prototype &middot; EthnoHack 2026
          </div>
        </div>
        """),
        unsafe_allow_html=True,
    )


def render_footer():
    st.markdown(
        _html(f"""
        <div style="margin-top:40px;padding:14px 0 4px 0;border-top:1px solid {COLOR_BORDER};
                    font-size:12.5px;color:{COLOR_TEXT_MUTED};line-height:1.65;">
          <strong style="color:{COLOR_TEXT_SECONDARY};">Data sources</strong>
          &nbsp;Dr. Duke's Phytochemical and Ethnobotanical Databases (USDA, CC0) &middot;
          PROSEA / Pl@ntUse &middot; PubMed (NCBI E-utilities) &middot; PubChem &middot;
          Wikipedia / Wikimedia Commons<br>
          For research and educational purposes only. This tool does not provide medical advice.
          Structural similarity and literature counts are screening signals, not evidence of
          clinical efficacy or safety.
        </div>
        """),
        unsafe_allow_html=True,
    )


def section_title(title, subtitle=None, eyebrow=None):
    html = ""
    if eyebrow:
        html += f"<div class='jpe-eyebrow'>{eyebrow}</div>"
    html += f"<div style='font-size:19px;font-weight:600;color:{COLOR_TEXT};margin:2px 0 2px;'>{title}</div>"
    if subtitle:
        html += f"<div style='font-size:13.5px;color:{COLOR_TEXT_MUTED};margin-bottom:12px;'>{subtitle}</div>"
    else:
        html += "<div style='margin-bottom:10px;'></div>"
    st.markdown(html, unsafe_allow_html=True)


def info_panel(text, kind="info"):
    palette = {
        "info": ("#EEF3F7", COLOR_ACCENT),
        "warning": ("#FFF8E1", "#B7791F"),
    }
    bg, border = palette.get(kind, palette["info"])
    st.markdown(
        f"""<div style="background:{bg};border-left:3px solid {border};border-radius:6px;
                 padding:10px 14px;font-size:13.5px;color:{COLOR_TEXT_SECONDARY};
                 margin:4px 0 16px 0;line-height:1.55;">{text}</div>""",
        unsafe_allow_html=True,
    )


def kpi_card(label, value, caption=None):
    extra = f"<div style='font-size:11.5px;color:{COLOR_TEXT_MUTED};margin-top:3px;'>{caption}</div>" if caption else ""
    st.markdown(
        f"""<div class="jpe-card" style="padding:14px 16px;">
                 <div style="font-size:12.5px;color:{COLOR_TEXT_MUTED};font-weight:500;">{label}</div>
                 <div style="font-size:27px;font-weight:700;color:{COLOR_PRIMARY};line-height:1.25;">{value}</div>
                 {extra}</div>""",
        unsafe_allow_html=True,
    )


def status_pill_html(tier_key, size="normal"):
    style = EVIDENCE_STYLES.get(tier_key, EVIDENCE_STYLES["not_queried"])
    pad = "2px 9px" if size == "small" else "4px 12px"
    font = "11.5px" if size == "small" else "12.5px"
    return (
        f"<span style='display:inline-block;background:{style['bg']};color:{style['fg']};"
        f"border-radius:999px;padding:{pad};font-size:{font};font-weight:500;white-space:nowrap;'>"
        f"{style['label']}</span>"
    )


def featured_pill_html():
    return (
        f"<span style='display:inline-block;background:#E6EEF5;color:{COLOR_PRIMARY};"
        f"border-radius:999px;padding:2px 9px;font-size:11px;font-weight:600;"
        f"margin-left:6px;vertical-align:middle;font-style:normal;'>Featured</span>"
    )


def match_pill_html(label, exact=True):
    fg, bg = ("#2E7D32", "#E8F5E9") if exact else ("#B7791F", "#FFF8E1")
    return (
        f"<span style='display:inline-block;background:{bg};color:{fg};border-radius:999px;"
        f"padding:2px 9px;font-size:11.5px;font-weight:500;'>{label}</span>"
    )


def timeline_html(entries, current_name: str) -> str:
    """entries: list of (year:int, name:str, author:str), any order."""
    items = sorted(entries, key=lambda e: e[0])
    rows = "".join(
        f"<div class='jpe-tl-item'><div class='jpe-tl-year'>{year}</div>"
        f"<div class='jpe-tl-name'>{name}</div>"
        f"<div class='jpe-tl-author'>{author}</div></div>"
        for year, name, author in items
    )
    rows += (
        "<div class='jpe-tl-item jpe-tl-current'><div class='jpe-tl-year'>TODAY</div>"
        f"<div class='jpe-tl-name'>{current_name}</div>"
        "<div class='jpe-tl-author'>Current accepted name (PROSEA)</div></div>"
    )
    return f"<div class='jpe-timeline'>{rows}</div>"


def render_badges(items, kind="use"):
    """Render a flex-wrapped row of small rounded pill badges."""
    if not items:
        return
    style = BADGE_STYLES.get(kind, {"fg": "#333", "bg": "#eee"})
    pills = "".join(
        f"<span style='display:inline-block;background:{style['bg']};color:{style['fg']};"
        f"border-radius:999px;padding:3px 10px;margin:2px;font-size:12.5px;'>{item}</span>"
        for item in items
    )
    st.markdown(f"<div style='line-height:2.1;margin-bottom:6px;'>{pills}</div>", unsafe_allow_html=True)


def prose(text):
    st.markdown(f"<div class='jpe-prose'>{text}</div>", unsafe_allow_html=True)


STATIC_THUMB_DIR = Path(__file__).resolve().parent / "static" / "plant_thumbs"


@st.cache_data(show_spinner=False)
def image_data_uri(path_str: str) -> str:
    """Base64 data URI for a local image, so cards can use CSS object-fit."""
    path = Path(path_str)
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def hero_img_html(image_full_path: Path | None) -> str:
    """Larger header image for the plant detail view."""
    if image_full_path is not None:
        static_thumb = STATIC_THUMB_DIR / f"{image_full_path.stem}.jpg"
        if static_thumb.exists():
            return f"<img class='jpe-hero-img' src='app/static/plant_thumbs/{static_thumb.name}' alt=''>"
        if image_full_path.exists():
            return f"<img class='jpe-hero-img' src='{image_data_uri(str(image_full_path))}' alt=''>"
    return f"<div class='jpe-hero-empty'>{_LEAF_SVG}</div>"


def card_thumb_html(image_full_path: Path | None, featured: bool = False) -> str:
    """Card thumbnail with an optional 'Featured' badge overlaid on the image,
    so a badge never changes the card's text height and rows stay aligned."""
    badge = "<span class='jpe-featured'>Featured</span>" if featured else ""
    return f"<div class='jpe-thumb-wrap'>{thumb_html(image_full_path)}{badge}</div>"


def thumb_html(image_full_path: Path | None) -> str:
    """Fixed-height, cover-cropped thumbnail, or a neutral leaf placeholder.

    Prefers the pre-generated static thumbnail (browser-cacheable, ~25 KB) made
    by src/pipeline/make_thumbnails.py; falls back to inlining the full-size
    photo so the gallery still works if that step has not been run.
    """
    if image_full_path is None:
        return f"<div class='jpe-thumb-empty'>{_LEAF_SVG}</div>"

    static_thumb = STATIC_THUMB_DIR / f"{image_full_path.stem}.jpg"
    if static_thumb.exists():
        return f"<img class='jpe-thumb' src='app/static/plant_thumbs/{static_thumb.name}' alt='' loading='lazy'>"
    if image_full_path.exists():
        return f"<img class='jpe-thumb' src='{image_data_uri(str(image_full_path))}' alt=''>"
    return f"<div class='jpe-thumb-empty'>{_LEAF_SVG}</div>"
