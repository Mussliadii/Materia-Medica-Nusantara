"""
Rank the PROSEA candidates explicitly documented as used in Indonesia
(data/processed/plants_seed_candidates.csv), score them by how much downstream
data actually exists for each, and keep the top N as our final working seed
list -- so the species chosen are the best-documented ones, not an arbitrary cut.

TARGET_N defaults to "all of them": every one of the 663 candidates already has
a confirmed Indonesian vernacular name in PROSEA, so there is no reason to
throw away two-thirds of a real, citable list just to round down to 300.

Score = (has Duke chemical data) + (has Duke traditional-use data)
      + log-scaled count of Duke chemicals/uses + length of the PROSEA "Uses" text.

Output: data/processed/plants_seed.csv
"""
import math
from pathlib import Path

import pandas as pd

PROC = Path(__file__).resolve().parents[2] / "data" / "processed"
TARGET_N = 10_000  # effectively "no cap" -- keep every real candidate


def main():
    seed = pd.read_csv(PROC / "plants_seed_candidates.csv", dtype=str, keep_default_na=False)
    chems = pd.read_csv(PROC / "duke_plant_chemicals.csv", dtype=str, keep_default_na=False)
    trad = pd.read_csv(PROC / "duke_traditional_uses.csv", dtype=str, keep_default_na=False)

    chem_counts = chems.groupby([chems["GENUS"].str.lower(), chems["SPECIES"].str.lower()]).size()
    trad_counts = trad.groupby([trad["GENUS"].str.lower(), trad["SPECIES"].str.lower()]).size()

    def score(row):
        key = (row["GENUS"].lower(), row["SPECIES"].lower())
        n_chem = chem_counts.get(key, 0)
        n_trad = trad_counts.get(key, 0)
        s = 0.0
        s += 2.0 if n_chem > 0 else 0.0
        s += 2.0 if n_trad > 0 else 0.0
        s += math.log1p(n_chem)
        s += math.log1p(n_trad)
        s += math.log1p(len(row.get("USES_TEXT", ""))) * 0.3
        return s, n_chem, n_trad

    scored = seed.apply(score, axis=1, result_type="expand")
    scored.columns = ["score", "n_duke_chemicals", "n_duke_traditional_uses"]
    seed = pd.concat([seed, scored], axis=1)

    seed_sorted = seed.sort_values("score", ascending=False)
    final = seed_sorted.head(TARGET_N).copy()

    print(f"Candidates: {len(seed)} -> selected top {len(final)} by data-richness score")
    print(f"  of those, {int((final['n_duke_chemicals'] > 0).sum())} have Duke chemical data")
    print(f"  of those, {int((final['n_duke_traditional_uses'] > 0).sum())} have Duke traditional-use data")

    final.to_csv(PROC / "plants_seed.csv", index=False)
    print(f"Saved final seed list -> {PROC / 'plants_seed.csv'}")


if __name__ == "__main__":
    main()
