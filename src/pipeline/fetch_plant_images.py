"""
Fetch a representative photo per plant (for the gallery view) from Wikipedia's
REST summary API, keyed by scientific name (Genus_species). Wikipedia articles
pull their images from Wikimedia Commons, which are themselves under various
open licences (mostly CC-BY-SA or public domain) with per-file attribution --
we store the Wikipedia article URL per plant so the dashboard can link to it
for full credit/licence info rather than asserting a single blanket licence.

Output:
  data/processed/images/<genus>_<species>.jpg   (downloaded thumbnails)
  data/processed/plant_images.csv                (GENUS, SPECIES, image_path,
                                                    wikipedia_url, found)
"""
import time
from pathlib import Path

import pandas as pd
import requests

PROC = Path(__file__).resolve().parents[2] / "data" / "processed"
IMG_DIR = PROC / "images"
REST_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
HEADERS = {"User-Agent": "EthnoHack2026-research-prototype/0.1 (jamu-pharmacology-mapping)"}
SLEEP = 0.15


def fetch_summary(title_underscored: str) -> dict | None:
    resp = requests.get(REST_SUMMARY.format(title_underscored), headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def download_image(url: str) -> bytes | None:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
        return resp.content
    return None


def main():
    plants = pd.read_csv(PROC / "plants_seed.csv", dtype=str, keep_default_na=False)
    plants = plants.drop_duplicates(subset=["GENUS", "SPECIES"])
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for i, (_, row) in enumerate(plants.iterrows(), 1):
        genus, species = row["GENUS"], row["SPECIES"]
        title = f"{genus}_{species}"
        slug = f"{genus.lower()}_{species.lower()}"

        summary = fetch_summary(title)
        time.sleep(SLEEP)

        found = False
        image_path = ""
        wiki_url = ""
        if summary:
            wiki_url = summary.get("content_urls", {}).get("desktop", {}).get("page", "")
            thumb = summary.get("thumbnail", {}).get("source", "")
            if thumb:
                img_bytes = download_image(thumb)
                time.sleep(SLEEP)
                if img_bytes:
                    ext = ".jpg" if "jpg" in thumb.lower() or "jpeg" in thumb.lower() else ".png"
                    out_path = IMG_DIR / f"{slug}{ext}"
                    out_path.write_bytes(img_bytes)
                    image_path = f"images/{slug}{ext}"
                    found = True

        rows.append(
            {
                "GENUS": genus,
                "SPECIES": species,
                "found": found,
                "image_path": image_path,
                "wikipedia_url": wiki_url,
            }
        )
        if i % 25 == 0:
            n_found = sum(r["found"] for r in rows)
            print(f"  [{i}/{len(plants)}] found so far: {n_found}")

    out = pd.DataFrame(rows)
    out.to_csv(PROC / "plant_images.csv", index=False)
    print(f"Saved {len(out)} rows ({int(out['found'].sum())} with image) -> data/processed/plant_images.csv")


if __name__ == "__main__":
    main()
