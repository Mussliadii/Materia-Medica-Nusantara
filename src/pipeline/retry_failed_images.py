"""
Retry image fetch only for species that failed in the previous run of
fetch_plant_images.py (likely a transient rate-limit/network issue, not
genuinely missing Wikipedia articles -- spot checks showed the same species
resolve fine on retry). Merges successes back into plant_images.csv.
"""
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_plant_images import fetch_summary, download_image, IMG_DIR, PROC, SLEEP  # noqa: E402

MAX_RETRIES = 3


def try_fetch_one(genus, species):
    title = f"{genus}_{species}"
    slug = f"{genus.lower()}_{species.lower()}"
    for attempt in range(MAX_RETRIES):
        summary = fetch_summary(title)
        if summary:
            break
        time.sleep(1.0 * (attempt + 1))
    else:
        return None

    wiki_url = summary.get("content_urls", {}).get("desktop", {}).get("page", "")
    thumb = summary.get("thumbnail", {}).get("source", "")
    if not thumb:
        return {"found": False, "image_path": "", "wikipedia_url": wiki_url}

    img_bytes = None
    for attempt in range(MAX_RETRIES):
        img_bytes = download_image(thumb)
        if img_bytes:
            break
        time.sleep(1.0 * (attempt + 1))

    if not img_bytes:
        return {"found": False, "image_path": "", "wikipedia_url": wiki_url}

    ext = ".jpg" if "jpg" in thumb.lower() or "jpeg" in thumb.lower() else ".png"
    out_path = IMG_DIR / f"{slug}{ext}"
    out_path.write_bytes(img_bytes)
    return {"found": True, "image_path": f"images/{slug}{ext}", "wikipedia_url": wiki_url}


def main():
    df = pd.read_csv(PROC / "plant_images.csv", dtype=str, keep_default_na=False)
    df["found"] = df["found"].astype(str) == "True"
    failed = df[~df["found"]]
    print(f"Retrying {len(failed)} previously-failed species...")

    n_recovered = 0
    for i, (idx, row) in enumerate(failed.iterrows(), 1):
        result = try_fetch_one(row["GENUS"], row["SPECIES"])
        time.sleep(SLEEP)
        if result and result["found"]:
            df.loc[idx, "found"] = True
            df.loc[idx, "image_path"] = result["image_path"]
            df.loc[idx, "wikipedia_url"] = result["wikipedia_url"]
            n_recovered += 1
        elif result:
            df.loc[idx, "wikipedia_url"] = result["wikipedia_url"]
        if i % 25 == 0:
            print(f"  [{i}/{len(failed)}] recovered so far: {n_recovered}")

    df.to_csv(PROC / "plant_images.csv", index=False)
    total_found = int(df["found"].sum())
    print(f"Recovered {n_recovered} more. Total with image now: {total_found}/{len(df)}")


if __name__ == "__main__":
    main()
