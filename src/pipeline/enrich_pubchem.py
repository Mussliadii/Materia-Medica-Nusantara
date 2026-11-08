"""
Enrich a curated set of "flagship" jamu plants with real compound structures
from PubChem (PUG REST API) -- for the pitch deck / detail page, going one
level deeper than the Duke's chemical-name-only data.

For each flagship plant we take its top chemicals from Dr. Duke's data
(ranked by how many reported pharmacological activities they have, i.e. the
most "interesting" ones), look each unique name up on PubChem, and save:
  CID, canonical title, molecular formula, molecular weight, SMILES, IUPAC name,
  and a 2D structure PNG.

Generic compositional categories (e.g. "TANNIN", "PROTEIN", "FIBER") are not
single molecules and are skipped rather than queried.

Output:
  data/processed/flagship_plants.csv
  data/processed/pubchem_compounds.csv
  data/processed/structures/<cid>.png
"""
import time
from pathlib import Path

import pandas as pd
import requests

PROC = Path(__file__).resolve().parents[2] / "data" / "processed"
STRUCT_DIR = PROC / "structures"
PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
SLEEP = 0.25  # stay well under PubChem's 5 req/sec limit
TOP_N_PER_PLANT = 15

# (genus, species, one-line reason this plant was picked as a flagship example)
FLAGSHIP = [
    ("Curcuma", "longa", "Kunyit - ikon jamu, curcumin diteliti luas secara klinis"),
    ("Centella", "asiatica", "Pegagan - jamu populer, diteliti untuk penyembuhan luka & kognisi"),
    ("Morinda", "citrifolia", "Mengkudu - jamu klasik Nusantara"),
    ("Alpinia", "galanga", "Laos/langkuas - rempah-jamu umum"),
    ("Hibiscus", "sabdariffa", "Rosela - herbal populer modern, diteliti untuk tekanan darah"),
    ("Phyllanthus", "emblica", "Malaka/kemloko - sumber antioksidan tradisional"),
    ("Aloe", "vera", "Lidah buaya - dikenal global, dipakai topikal & oral"),
    ("Cyperus", "rotundus", "Teki - jamu tradisional kesehatan wanita"),
    ("Acorus", "calamus", "Dringo - bahan jamu klasik"),
    ("Momordica", "charantia", "Pare - pangan+jamu, banyak diteliti untuk diabetes"),
    ("Catharanthus", "roseus", "Tapak dara - sumber alkaloid vinca (dasar obat kanker modern)"),
    ("Mucuna", "pruriens", "Kara benguk - sumber L-DOPA alami, relevan untuk riset Parkinson"),
    ("Datura", "metel", "Kecubung - tradisional tapi toksik/psikoaktif; contoh kasus kehati-hatian"),
    ("Plantago", "major", "Daun sendok - jamu luka & saluran kemih, data Duke's sangat kaya"),
    ("Morus", "alba", "Murbei - jamu diabetes & kolesterol tradisional"),
    ("Jatropha", "curcas", "Jarak pagar - jamu luka & pencahar, juga tanaman biodiesel"),
    ("Artemisia", "vulgaris", "Baru cina - jamu haid & anthelmintik tradisional"),
    ("Kaempferia", "galanga", "Kencur - rempah-jamu klasik, batuk & stamina"),
    ("Curcuma", "xanthorrhiza", "Temulawak - jamu liver khas Indonesia"),
    ("Curcuma", "zedoaria", "Temu putih - jamu pencernaan & antikanker tradisional"),
    ("Phyllanthus", "amarus", "Meniran - jamu imunomodulator populer"),
    ("Andrographis", "paniculata", "Sambiloto - jamu pahit untuk demam & antiinflamasi"),
    ("Rauvolfia", "serpentina", "Pule pandak - sumber reserpine, obat hipertensi modern pertama"),
    ("Mitragyna", "speciosa", "Kratom - alkaloid opioid-like, topik riset & regulasi aktif"),
    ("Physalis", "angulata", "Ceplukan - jamu tradisional, diteliti untuk aktivitas antikanker"),
    ("Mimosa", "pudica", "Putri malu - jamu tidur & luka tradisional"),
    ("Justicia", "gendarussa", "Gandarusa - diteliti sebagai kandidat kontrasepsi pria"),
    ("Alstonia", "scholaris", "Pulai - sumber alkaloid antimalaria tradisional"),
    ("Sida", "rhombifolia", "Sidaguri - jamu asam urat & antiinflamasi tradisional"),
    ("Hibiscus", "rosa-sinensis", "Kembang sepatu - jamu rambut & haid tradisional"),
]

GENERIC_CATEGORY_BLOCKLIST = {
    "TANNIN", "TANNINS", "POLYPHENOLS", "FIBER", "CRUDE-FIBER", "PROTEIN", "CRUDE-PROTEIN",
    "FAT", "CRUDE-FAT", "CARBOHYDRATE", "CARBOHYDRATES", "ASH", "ESSENTIAL-OIL", "RESIN",
    "MUCILAGE", "STARCH", "GUM", "PECTIN", "LIGNIN", "SAPONIN", "SAPONINS", "ALKALOIDS",
    "FLAVONOIDS", "WATER", "MOISTURE", "ENERGY", "CALORIES", "NDF", "ADF",
    "COUMARINS", "PROANTHOCYANIDINS", "ANTHOCYANINS", "CAROTENOIDS", "TERPENOIDS",
    "GLYCOSIDES", "PHENOLICS", "STEROLS",
}


# Compounds that are scientifically significant for a given plant but don't
# rank in the top N by Duke's activity-record count alone -- curated by hand
# because they're the compound the flagship story is actually about.
MUST_INCLUDE = {
    ("Mucuna", "pruriens"): ["DOPA"],  # L-DOPA, the Parkinson's-relevant alkaloid
}


def top_chemicals_for(genus, species, chems, act_counts):
    sub = chems[(chems["GENUS"] == genus) & (chems["SPECIES"] == species)]["CHEM"].drop_duplicates()
    sub = [c for c in sub if c.upper() not in GENERIC_CATEGORY_BLOCKLIST]
    ranked = sorted(sub, key=lambda c: -act_counts.get(c, 0))
    must = [c for c in MUST_INCLUDE.get((genus, species), []) if c in ranked]
    rest = [c for c in ranked if c not in must]
    return (must + rest)[:TOP_N_PER_PLANT]


def fetch_pubchem_properties(name: str) -> dict | None:
    url = f"{PUG}/compound/name/{requests.utils.quote(name)}/property/MolecularFormula,MolecularWeight,SMILES,IUPACName,Title/JSON"
    resp = requests.get(url, timeout=20)
    if resp.status_code != 200:
        return None
    try:
        props = resp.json()["PropertyTable"]["Properties"][0]
    except (KeyError, IndexError, ValueError):
        return None
    return props


def fetch_structure_png(cid: int) -> bytes | None:
    url = f"{PUG}/compound/cid/{cid}/PNG"
    resp = requests.get(url, timeout=20)
    if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
        return resp.content
    return None


def main():
    chems = pd.read_csv(PROC / "duke_plant_chemicals.csv", dtype=str, keep_default_na=False)
    acts = pd.read_csv(PROC / "duke_chemical_activities.csv", dtype=str, keep_default_na=False)
    act_counts = acts.groupby("CHEM").size().to_dict()

    flagship_rows = []
    plant_to_chems = {}
    for genus, species, reason in FLAGSHIP:
        top_chems = top_chemicals_for(genus, species, chems, act_counts)
        plant_to_chems[(genus, species)] = top_chems
        flagship_rows.append(
            {
                "GENUS": genus,
                "SPECIES": species,
                "latin_name": f"{genus} {species}",
                "reason": reason,
                "n_top_chemicals": len(top_chems),
                "top_chemicals": "; ".join(top_chems),
            }
        )
    flagship_df = pd.DataFrame(flagship_rows)
    flagship_df.to_csv(PROC / "flagship_plants.csv", index=False)
    print(f"Flagship plants: {len(flagship_df)} -> data/processed/flagship_plants.csv")

    unique_chems = sorted({c for chems_list in plant_to_chems.values() for c in chems_list})
    print(f"Unique chemicals to look up on PubChem: {len(unique_chems)}")

    STRUCT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, chem in enumerate(unique_chems, 1):
        props = fetch_pubchem_properties(chem)
        time.sleep(SLEEP)
        if not props:
            rows.append({"CHEM": chem, "found": False})
            print(f"  [{i}/{len(unique_chems)}] NOT FOUND: {chem}")
            continue

        cid = props.get("CID")
        png = fetch_structure_png(cid) if cid else None
        time.sleep(SLEEP)
        if png:
            (STRUCT_DIR / f"{cid}.png").write_bytes(png)

        rows.append(
            {
                "CHEM": chem,
                "found": True,
                "cid": cid,
                "title": props.get("Title", ""),
                "molecular_formula": props.get("MolecularFormula", ""),
                "molecular_weight": props.get("MolecularWeight", ""),
                "smiles": props.get("SMILES", ""),
                "iupac_name": props.get("IUPACName", ""),
                "pubchem_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}" if cid else "",
                "structure_png": f"structures/{cid}.png" if png else "",
            }
        )
        if i % 10 == 0:
            print(f"  [{i}/{len(unique_chems)}] {chem} -> CID {cid}")

    out = pd.DataFrame(rows)
    out.to_csv(PROC / "pubchem_compounds.csv", index=False)
    found = int(out["found"].sum()) if "found" in out else 0
    print(f"Saved {len(out)} rows ({found} found) -> data/processed/pubchem_compounds.csv")


if __name__ == "__main__":
    main()
