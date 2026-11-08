"""
Evidence-linking layer: for each plant (Latin binomial), query PubMed via NCBI
E-utilities to get a transparent, reproducible signal of how much *modern*
pharmacological literature exists, and at what evidence tier.

This does NOT try to read/understand abstracts (that would need a heavier NLP
model and manual spot-checking at this scale). It only counts hits for a few
precise, documented queries and assigns an evidence tier from those counts.
The raw counts and exact query strings are kept in the output so the method
is auditable -- this is meant to flag "worth a closer look" vs "traditional
use only, no modern study found", never to assert efficacy.

Input:  data/processed/plants_seed.csv  (must have GENUS, SPECIES columns)
Output: data/processed/pubmed_evidence.csv
"""
import csv
import time
from pathlib import Path

import pandas as pd
import requests

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
TOOL_NAME = "ethnohack2026_jamu_pharmacology_prototype"
SLEEP_BETWEEN_CALLS = 0.34  # NCBI allows 3 req/sec without an API key

IN_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "plants_seed.csv"
OUT_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "pubmed_evidence.csv"


def esearch_count(term: str) -> int:
    params = {"db": "pubmed", "term": term, "retmode": "json", "retmax": 0, "tool": TOOL_NAME}
    resp = requests.get(EUTILS, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return int(data.get("esearchresult", {}).get("count", 0))


def queries_for(genus: str, species: str) -> dict:
    binomial = f'"{genus} {species}"[Title/Abstract]'
    return {
        "general_query": f"{binomial} AND (pharmacolog*[Title/Abstract] OR extract[Title/Abstract] OR bioactiv*[Title/Abstract] OR activity[Title/Abstract])",
        "clinical_query": f'{binomial} AND ("clinical trial"[Publication Type] OR "randomized controlled trial"[Publication Type])',
        "review_query": f'{binomial} AND "review"[Publication Type]',
    }


def evidence_tier(general: int, clinical: int, review: int) -> str:
    if clinical > 0:
        return "clinical_evidence"
    if general > 0 or review > 0:
        return "preclinical_or_review_evidence"
    return "traditional_only_no_modern_lit_found"


def main():
    plants = pd.read_csv(IN_PATH, dtype=str, keep_default_na=False)
    plants = plants[(plants["GENUS"] != "") & (plants["SPECIES"] != "")].drop_duplicates(
        subset=["GENUS", "SPECIES"]
    )
    print(f"Querying PubMed for {len(plants)} species...")

    rows = []
    for i, (_, row) in enumerate(plants.iterrows(), 1):
        genus, species = row["GENUS"], row["SPECIES"]
        q = queries_for(genus, species)
        try:
            general = esearch_count(q["general_query"])
            time.sleep(SLEEP_BETWEEN_CALLS)
            clinical = esearch_count(q["clinical_query"])
            time.sleep(SLEEP_BETWEEN_CALLS)
            review = esearch_count(q["review_query"])
            time.sleep(SLEEP_BETWEEN_CALLS)
        except requests.RequestException as e:
            print(f"  [{i}/{len(plants)}] FAILED {genus} {species}: {e}")
            continue

        rows.append(
            {
                "GENUS": genus,
                "SPECIES": species,
                "general_hits": general,
                "clinical_trial_hits": clinical,
                "review_hits": review,
                "evidence_tier": evidence_tier(general, clinical, review),
                "general_query": q["general_query"],
                "clinical_query": q["clinical_query"],
            }
        )
        if i % 20 == 0:
            print(f"  [{i}/{len(plants)}] {genus} {species}: tier={rows[-1]['evidence_tier']}")

    out_df = pd.DataFrame(rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_PATH, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f"Saved {len(out_df)} rows to {OUT_PATH}")
    print(out_df["evidence_tier"].value_counts())


if __name__ == "__main__":
    main()
