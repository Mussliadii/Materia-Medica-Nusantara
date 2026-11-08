"""
parse_duke.py outputs Dr. Duke's tables for its *entire* global database (tens
of thousands of species worldwide), because that's simplest to parse from the
raw CSV dump. But the dashboard only ever looks up rows for our 663-species
seed list -- so shipping the full global tables in the repo would mean
committing ~46 MB of data for species we never show.

This filters those three tables down to just our seed species (and, for the
activities table, just the chemicals those species actually contain) and
writes the smaller files the dashboard actually reads.

Input:  data/processed/duke_traditional_uses.csv   (global, gitignored)
        data/processed/duke_plant_chemicals.csv    (global, gitignored)
        data/processed/duke_chemical_activities.csv (global, gitignored)
Output: data/processed/duke_traditional_uses_seed.csv
        data/processed/duke_plant_chemicals_seed.csv
        data/processed/duke_chemical_activities_seed.csv
"""
from pathlib import Path

import pandas as pd

PROC = Path(__file__).resolve().parents[2] / "data" / "processed"


def main():
    seed = pd.read_csv(PROC / "plants_seed.csv", dtype=str, keep_default_na=False)
    seed_pairs = set(zip(seed["GENUS"].str.lower(), seed["SPECIES"].str.lower()))

    def in_seed(df):
        return df[[(g, s) in seed_pairs for g, s in zip(df["GENUS"].str.lower(), df["SPECIES"].str.lower())]]

    trad = pd.read_csv(PROC / "duke_traditional_uses.csv", dtype=str, keep_default_na=False)
    trad_f = in_seed(trad)
    trad_f.to_csv(PROC / "duke_traditional_uses_seed.csv", index=False)
    print(f"traditional uses: {len(trad)} -> {len(trad_f)} rows")

    chems = pd.read_csv(PROC / "duke_plant_chemicals.csv", dtype=str, keep_default_na=False)
    chems_f = in_seed(chems)
    chems_f.to_csv(PROC / "duke_plant_chemicals_seed.csv", index=False)
    print(f"plant chemicals: {len(chems)} -> {len(chems_f)} rows")

    acts = pd.read_csv(PROC / "duke_chemical_activities.csv", dtype=str, keep_default_na=False)
    chem_set = set(chems_f["CHEM"].str.lower())
    acts_f = acts[acts["CHEM"].str.lower().isin(chem_set)]
    acts_f.to_csv(PROC / "duke_chemical_activities_seed.csv", index=False)
    print(f"chemical activities: {len(acts)} -> {len(acts_f)} rows")


if __name__ == "__main__":
    main()
