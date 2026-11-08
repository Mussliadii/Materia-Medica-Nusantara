"""
Parse Dr. Duke's Phytochemical and Ethnobotanical Databases (USDA/ARS, CC0) raw
CSV dump into three tidy tables that map cleanly onto our knowledge-graph schema:

  Plant --[traditional use]--> TraditionalActivity   (from ETHNOBOT.csv)
  Plant --[contains]--> Chemical                      (from FARMACY_NEW.csv)
  Chemical --[has reported activity]--> Activity       (from AGGREGAC.csv)

Source: https://dx.doi.org/10.15482/USDA.ADC/1239279 (Duke-Source-CSV.zip, CC0)
"""
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parents[2] / "data" / "raw" / "duke" / "extracted"
OUT = Path(__file__).resolve().parents[2] / "data" / "processed"


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW / f"{name}.csv", dtype=str, keep_default_na=False, encoding="latin-1")


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    fnftax = load("FNFTAX")[["FNFNUM", "GENUS", "SPECIES", "FAMILY", "TAXON"]]

    # --- Traditional / ethnobotanical uses -------------------------------
    ethnobot = load("ETHNOBOT")[
        ["GENUS", "SPECIES", "FAMILY", "ACTIVITY", "COUNTRY", "REFERENCE", "LONGREF"]
    ].copy()
    ethnobot = ethnobot[(ethnobot["GENUS"] != "") & (ethnobot["SPECIES"] != "")]
    ethnobot = ethnobot.rename(columns={"ACTIVITY": "TRADITIONAL_USE"})
    ethnobot.to_csv(OUT / "duke_traditional_uses.csv", index=False)
    print(f"traditional uses: {len(ethnobot)} rows, "
          f"{ethnobot[['GENUS','SPECIES']].drop_duplicates().shape[0]} unique species")

    # --- Plant -> chemical content ----------------------------------------
    farmacy = load("FARMACY_NEW")[["FNFNUM", "CHEM", "PLCO", "REFERENCE"]]
    farmacy = farmacy.merge(fnftax, on="FNFNUM", how="inner")
    farmacy = farmacy[(farmacy["GENUS"] != "") & (farmacy["SPECIES"] != "") & (farmacy["CHEM"] != "")]
    farmacy_out = farmacy[["GENUS", "SPECIES", "FAMILY", "CHEM", "REFERENCE"]].drop_duplicates()
    farmacy_out.to_csv(OUT / "duke_plant_chemicals.csv", index=False)
    print(f"plant-chemical links: {len(farmacy_out)} rows, "
          f"{farmacy_out[['GENUS','SPECIES']].drop_duplicates().shape[0]} unique species, "
          f"{farmacy_out['CHEM'].nunique()} unique chemicals")

    # --- Chemical -> reported pharmacological activity ---------------------
    aggregac = load("AGGREGAC")[["CHEM", "ACTIVITY", "REFERENCE"]]
    superact = load("SUPERACT")
    references = load("REFERENCES")[["REFERENCE", "LONGREF"]]

    chem_act = aggregac.merge(superact, on="ACTIVITY", how="left")
    chem_act = chem_act.merge(references, on="REFERENCE", how="left")
    chem_act = chem_act[chem_act["CHEM"] != ""]
    chem_act.to_csv(OUT / "duke_chemical_activities.csv", index=False)
    print(f"chemical activities: {len(chem_act)} rows, "
          f"{chem_act['CHEM'].nunique()} unique chemicals, "
          f"{chem_act['ACTIVITY'].nunique()} unique activities")


if __name__ == "__main__":
    main()
