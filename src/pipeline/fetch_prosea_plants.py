"""
Fetch the full "Medicinal plants (PROSEA)" category from Pl@ntUse (plantuse.plantnet.org),
a MediaWiki-based mirror of PROSEA (Plant Resources of South-East Asia).

Output: data/raw/prosea_pages.json
  List of {pageid, title, wikitext} for every species-level page in the category
  (genus index pages and the "Introduction/Literature on Medicinals" pages are skipped).

Source: https://plantuse.plantnet.org/en/Category:Medicinal_plants_(PROSEA)
Attribution: PROSEA Foundation / Pl@ntUse. Verify licence on Pl@ntUse:Copyrights
before any redistribution beyond this research prototype.
"""
import json
import time
from pathlib import Path

import requests

API = "https://plantuse.plantnet.org/en/api.php"
CATEGORY = "Category:Medicinal_plants_(PROSEA)"
OUT_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "prosea_pages.json"
HEADERS = {"User-Agent": "EthnoHack2026-research-prototype/0.1 (jamu-pharmacology-mapping)"}


def list_category_members():
    titles = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": CATEGORY,
        "cmlimit": "500",
        "format": "json",
    }
    cmcontinue = None
    while True:
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        resp = requests.get(API, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for member in data["query"]["categorymembers"]:
            titles.append(member["title"])
        cont = data.get("continue", {}).get("cmcontinue")
        if not cont:
            break
        cmcontinue = cont
        time.sleep(0.2)
    return titles


def is_species_page(title: str) -> bool:
    """Keep pages that look like '<Genus> <species> (PROSEA)'; drop genus-only
    index pages and the Introduction/Literature overview pages."""
    if "Introduction to Medicinals" in title or "Literature on Medicinals" in title:
        return False
    if not title.endswith("(PROSEA)"):
        return False
    name_part = title.replace("(PROSEA)", "").replace("(PROSEA Medicinals)", "").strip()
    # a species binomial has at least two space-separated words before the "(PROSEA)" tag
    return len(name_part.split()) >= 2


def fetch_wikitext(title: str) -> str:
    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext",
        "format": "json",
    }
    resp = requests.get(API, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("parse", {}).get("wikitext", {}).get("*", "")


def main():
    print("Listing category members...")
    all_titles = list_category_members()
    print(f"Total pages in category: {len(all_titles)}")

    species_titles = [t for t in all_titles if is_species_page(t)]
    print(f"Species-level pages: {len(species_titles)}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for i, title in enumerate(species_titles, 1):
        try:
            wikitext = fetch_wikitext(title)
        except requests.RequestException as e:
            print(f"  [{i}/{len(species_titles)}] FAILED {title}: {e}")
            continue
        results.append({"title": title, "wikitext": wikitext})
        if i % 25 == 0:
            print(f"  [{i}/{len(species_titles)}] fetched {title}")
        time.sleep(0.15)  # be polite to the wiki

    OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved {len(results)} pages to {OUT_PATH}")


if __name__ == "__main__":
    main()
