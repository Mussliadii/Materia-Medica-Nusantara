"""
Parse the raw PROSEA wikitext pages (data/raw/prosea_pages.json) into structured
fields, then filter down to species that are explicitly documented as used in
Indonesia (i.e. have an "Indonesia:" line under Vernacular names) -- this is
what grounds the "jamu plant" claim in a real source rather than a guess.

Output: data/processed/prosea_parsed.csv (all parsed species, flagged)
        data/processed/plants_seed.csv   (Indonesia-flagged subset = our seed list)
"""
import json
import re
from pathlib import Path

import pandas as pd

RAW_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "prosea_pages.json"
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

SECTION_RE = re.compile(r"^==\s*(.+?)\s*==\s*$", re.MULTILINE)


def get_section(wikitext: str, *names: str) -> str:
    """Return the text of the first matching '== Name ==' section (heading spacing
    varies across PROSEA pages), up to the next '==...==' heading. Accepts several
    alternate heading spellings and returns the first one found."""
    for name in names:
        pattern = re.compile(
            rf"==\s*{re.escape(name)}\s*==\s*\n(.*?)(?=\n\s*==[^=]|\Z)", re.DOTALL | re.IGNORECASE
        )
        m = pattern.search(wikitext)
        if m:
            return m.group(1).strip()
    return ""


def clean_wikitext(text: str) -> str:
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)  # [[link|label]] -> label
    text = re.sub(r"'{2,}", "", text)  # '' italics / ''' bold markers
    text = re.sub(r"<[^>]+>", "", text)  # stray html tags
    text = re.sub(r"\{\{[^}]*\}\}", "", text)  # templates
    return text.strip()


def parse_title(title: str):
    name = title.replace("(PROSEA Medicinals)", "").replace("(PROSEA)", "").strip()
    parts = name.split()
    genus = parts[0] if parts else ""
    species = parts[1] if len(parts) > 1 else ""
    return genus, species


def extract_country_line(vernacular_section: str, country_prefix: str) -> str:
    for line in vernacular_section.splitlines():
        line = line.strip().lstrip("*").strip()
        if line.lower().startswith(country_prefix.lower() + ":"):
            return clean_wikitext(line.split(":", 1)[1].strip())
    return ""


def main():
    pages = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    print(f"Loaded {len(pages)} raw PROSEA pages")

    rows = []
    for p in pages:
        genus, species = parse_title(p["title"])
        if not genus or not species:
            continue
        wt = p["wikitext"]

        family_m = re.search(r":Family:\s*(.+)", wt)
        family = clean_wikitext(family_m.group(1)) if family_m else ""

        vernacular = get_section(wt, "Vernacular names")
        indo_names = extract_country_line(vernacular, "Indonesia")

        uses_text = clean_wikitext(get_section(wt, "Uses"))
        distribution_text = clean_wikitext(
            get_section(wt, "Origin and geographic distribution", "Distribution")
        )

        wiki_slug = p["title"].replace(" ", "_")
        rows.append(
            {
                "GENUS": genus,
                "SPECIES": species,
                "FAMILY": family,
                "LOCAL_NAMES_INDONESIA": indo_names,
                "USES_TEXT": uses_text,
                "DISTRIBUTION_TEXT": distribution_text,
                "SOURCE_URL": f"https://plantuse.plantnet.org/en/{wiki_slug}",
                "has_indonesia_name": bool(indo_names),
                "mentions_indonesia_in_distribution": "indonesia" in distribution_text.lower()
                or "java" in distribution_text.lower()
                or "sumatra" in distribution_text.lower()
                or "kalimantan" in distribution_text.lower()
                or "sulawesi" in distribution_text.lower(),
            }
        )

    df = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "prosea_parsed.csv", index=False)
    print(f"Parsed {len(df)} species total")
    print(f"  with an explicit 'Indonesia:' vernacular-name line: {df['has_indonesia_name'].sum()}")
    print(f"  distribution text mentions Indonesia/Java/Sumatra/etc: {df['mentions_indonesia_in_distribution'].sum()}")

    seed = df[df["has_indonesia_name"]].copy()
    seed.to_csv(OUT_DIR / "plants_seed_candidates.csv", index=False)
    print(f"Candidate list (Indonesia-flagged): {len(seed)} species -> data/processed/plants_seed_candidates.csv")
    print("Run select_seed.py next to rank and cut this down to the final ~300 species.")


if __name__ == "__main__":
    main()
