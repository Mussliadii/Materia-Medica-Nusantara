"""
Cheminformatics similarity model (RDKit): for each phytochemical we already
resolved on PubChem (data/processed/pubchem_compounds.csv, from the flagship
plants), compare it against a curated list of well-known approved/reference
drugs using Morgan fingerprints + Tanimoto similarity.

This gives two kinds of finding, both legitimate and worth separating clearly:
  1. "identical_to_known_drug"   -- the phytochemical IS (same PubChem CID as)
     an approved drug. E.g. levodopa in Mucuna pruriens, atropine/scopolamine
     in Datura metel, reserpine in Catharanthus roseus. This is a real,
     already-established fact, not a prediction.
  2. "structural_analog"         -- the phytochemical is NOT the same molecule,
     but its Morgan fingerprint is similar (Tanimoto >= SIMILARITY_THRESHOLD)
     to a known drug -- a classic ligand-based virtual-screening signal that
     such a compound *might* be worth investigating further. This is a
     computational hint, not a claim of efficacy.

Output: data/processed/chem_similarity.csv
"""
import time
from pathlib import Path

import pandas as pd
import requests
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, DataStructs

RDLogger.DisableLog("rdApp.*")

PROC = Path(__file__).resolve().parents[2] / "data" / "processed"
PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
SLEEP = 0.25
SIMILARITY_THRESHOLD = 0.4
FP_RADIUS = 2
FP_NBITS = 2048

# Well-known approved / classic drugs to compare our phytochemicals against.
# Deliberately includes several natural-product-derived drugs (quinine,
# morphine, paclitaxel, vincristine, reserpine, atropine, scopolamine,
# levodopa, curcumin) since that's exactly the traditional-medicine ->
# modern-pharmacology bridge this project is about.
REFERENCE_DRUGS = [
    "Aspirin", "Acetaminophen", "Ibuprofen", "Metformin", "Caffeine",
    "Morphine", "Codeine", "Quinine", "Chloroquine", "Artemisinin",
    "Paclitaxel", "Vincristine", "Vinblastine", "Reserpine", "Atropine",
    "Scopolamine", "Levodopa", "Curcumin", "Digoxin", "Warfarin",
    "Metronidazole", "Simvastatin", "Colchicine", "Ephedrine", "Capsaicin",
    "Galantamine", "Physostigmine", "Pilocarpine", "Theophylline", "Nicotine",
    "Berberine", "Digitoxin", "Emetine", "Strychnine", "Camptothecin",
    "Podophyllotoxin", "Papaverine", "Cocaine", "Mitragynine", "Hyoscyamine",
]


def fetch_properties(name: str) -> dict | None:
    url = f"{PUG}/compound/name/{requests.utils.quote(name)}/property/MolecularFormula,MolecularWeight,SMILES,Title/JSON"
    resp = requests.get(url, timeout=20)
    if resp.status_code != 200:
        return None
    try:
        return resp.json()["PropertyTable"]["Properties"][0]
    except (KeyError, IndexError, ValueError):
        return None


def get_reference_drugs() -> pd.DataFrame:
    cache_path = PROC / "reference_drugs.csv"
    if cache_path.exists():
        return pd.read_csv(cache_path, dtype=str, keep_default_na=False)

    rows = []
    for name in REFERENCE_DRUGS:
        props = fetch_properties(name)
        time.sleep(SLEEP)
        if props:
            rows.append(
                {
                    "drug_name": name,
                    "cid": str(props.get("CID", "")),
                    "title": props.get("Title", name),
                    "smiles": props.get("SMILES", ""),
                }
            )
        else:
            print(f"  reference drug not found on PubChem: {name}")
    df = pd.DataFrame(rows)
    df.to_csv(cache_path, index=False)
    return df


def normalize_cid(cid) -> str:
    """CIDs land as '6047', '6047.0', or '' depending on which CSV wrote them."""
    cid = str(cid).strip()
    if not cid:
        return ""
    try:
        return str(int(float(cid)))
    except ValueError:
        return cid


def morgan_fp(smiles: str):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return AllChem.GetMorganFingerprintAsBitVect(mol, FP_RADIUS, nBits=FP_NBITS)


def main():
    phyto = pd.read_csv(PROC / "pubchem_compounds.csv", dtype=str, keep_default_na=False)
    phyto = phyto[phyto["found"] == "True"].copy()
    print(f"Phytochemicals with SMILES: {len(phyto)}")

    drugs = get_reference_drugs()
    print(f"Reference drugs resolved: {len(drugs)}")

    drugs["fp"] = drugs["smiles"].apply(morgan_fp)
    drugs = drugs[drugs["fp"].notna()]
    drugs["cid_norm"] = drugs["cid"].apply(normalize_cid)

    rows = []
    for _, prow in phyto.iterrows():
        fp = morgan_fp(prow["smiles"])
        if fp is None:
            continue

        prow_cid_norm = normalize_cid(prow["cid"])
        same_cid = drugs[drugs["cid_norm"] == prow_cid_norm] if prow_cid_norm else drugs.iloc[0:0]

        best_score, best_drug, best_cid = 0.0, None, None
        for _, drow in drugs.iterrows():
            sim = DataStructs.TanimotoSimilarity(fp, drow["fp"])
            if sim > best_score:
                best_score, best_drug, best_cid = sim, drow["drug_name"], drow["cid"]

        if len(same_cid) or best_score >= 0.999:
            match = same_cid.iloc[0] if len(same_cid) else None
            rows.append(
                {
                    "CHEM": prow["CHEM"],
                    "title": prow["title"],
                    "cid": prow["cid"],
                    "match_type": "identical_to_known_drug",
                    "matched_drug": match["drug_name"] if match is not None else best_drug,
                    "matched_drug_cid": match["cid"] if match is not None else best_cid,
                    "tanimoto_similarity": 1.0,
                }
            )
            continue

        if best_score >= SIMILARITY_THRESHOLD:
            rows.append(
                {
                    "CHEM": prow["CHEM"],
                    "title": prow["title"],
                    "cid": prow["cid"],
                    "match_type": "structural_analog",
                    "matched_drug": best_drug,
                    "matched_drug_cid": best_cid,
                    "tanimoto_similarity": round(best_score, 3),
                }
            )
        else:
            rows.append(
                {
                    "CHEM": prow["CHEM"],
                    "title": prow["title"],
                    "cid": prow["cid"],
                    "match_type": "no_close_match",
                    "matched_drug": best_drug,
                    "matched_drug_cid": best_cid,
                    "tanimoto_similarity": round(best_score, 3),
                }
            )

    out = pd.DataFrame(rows)
    out.to_csv(PROC / "chem_similarity.csv", index=False)
    print(f"Saved {len(out)} rows -> data/processed/chem_similarity.csv")
    print(out["match_type"].value_counts())
    print("\nIdentical-to-known-drug matches:")
    print(out[out["match_type"] == "identical_to_known_drug"][["CHEM", "matched_drug"]].to_string(index=False))
    print("\nTop structural analogs:")
    print(
        out[out["match_type"] == "structural_analog"]
        .sort_values("tanimoto_similarity", ascending=False)
        .head(10)[["CHEM", "matched_drug", "tanimoto_similarity"]]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
