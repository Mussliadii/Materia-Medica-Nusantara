"""
Map plant names across eras: parse the "==Synonyms==" section of each PROSEA
page (already fetched in data/raw/prosea_pages.json, but never used) into a
timeline of historical scientific names with the year each was published.

Example source text for Curcuma longa:
  "*''Amomum curcuma'' Jacq. (1776),
   *''Curcuma domestica'' Valeton (1918)"
-> two historical names, 1776 and 1918, before the name used today.

Output: data/processed/historical_synonyms.csv
  (GENUS, SPECIES, synonym_name, synonym_author, year, source_url)
"""
import json
import re
from pathlib import Path

import pandas as pd

RAW_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "prosea_pages.json"
PROC = Path(__file__).resolve().parents[2] / "data" / "processed"

ITALIC_NAME = re.compile(r"''([^']+)''")
YEAR = re.compile(r"\((\d{4})\)")


def get_section(wikitext: str, name: str) -> str:
    pattern = re.compile(rf"==\s*{re.escape(name)}\s*==\s*\n(.*?)(?=\n\s*==[^=]|\Z)", re.DOTALL | re.IGNORECASE)
    m = pattern.search(wikitext)
    return m.group(1).strip() if m else ""


def clean(text: str) -> str:
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"[*\n]", " ", text)
    return re.sub(r"\s+", " ", text).strip(" ,.;")


def parse_synonyms(wikitext: str):
    section = get_section(wikitext, "Synonyms")
    if not section:
        return []

    matches = list(ITALIC_NAME.finditer(section))
    results = []
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        seg_end = matches[i + 1].start() if i + 1 < len(matches) else len(section)
        segment = section[m.end() : seg_end]
        year_m = YEAR.search(segment)
        if not year_m:
            continue  # skip entries with no attached publication year
        year = int(year_m.group(1))
        author = clean(segment[: year_m.start()])
        if len(name.split()) < 2:
            continue  # skip bare genus mentions, keep binomials only
        results.append({"synonym_name": name, "synonym_author": author, "year": year})
    return results


def parse_title(title: str):
    name = title.replace("(PROSEA Medicinals)", "").replace("(PROSEA)", "").strip().split()
    return (name[0], name[1]) if len(name) > 1 else (None, None)


def main():
    pages = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    rows = []
    for p in pages:
        genus, species = parse_title(p["title"])
        if not genus:
            continue
        for syn in parse_synonyms(p["wikitext"]):
            rows.append(
                {
                    "GENUS": genus,
                    "SPECIES": species,
                    **syn,
                    "source_url": f"https://plantuse.plantnet.org/en/{p['title'].replace(' ', '_')}",
                }
            )

    df = pd.DataFrame(rows)
    df.to_csv(PROC / "historical_synonyms.csv", index=False)
    print(f"Parsed {len(df)} dated historical names across {df[['GENUS','SPECIES']].drop_duplicates().shape[0]} species")
    print(f"Earliest year found: {df['year'].min()}, latest: {df['year'].max()}")
    print(f"Saved -> {PROC / 'historical_synonyms.csv'}")


if __name__ == "__main__":
    main()
