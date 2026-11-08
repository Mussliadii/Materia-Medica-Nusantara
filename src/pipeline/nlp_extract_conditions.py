"""
Extract structured medical/pharmacological concepts from the free-text PROSEA
"Uses" descriptions using real NLP tooling (spaCy tokenization + PhraseMatcher)
against a curated controlled vocabulary -- instead of only relying on Dr.
Duke's pre-tagged ETHNOBOT activity labels the way the rest of the pipeline
does.

This matters because the PROSEA prose is the closest thing in this project to
the "historical / ethnobotanical text" the EthnoHack brief asks to mine with
NLP: Duke's ETHNOBOT entries are already hand-curated keywords, but the
PROSEA "Uses" paragraph is unstructured natural language written in archaic
pharmacological register ("stomachic", "emmenagogue", "febrifuge") that a
generic modern biomedical NER model would mostly fail to recognise -- so a
small curated lexicon, matched with a real tokenizer rather than naive
substring search, is actually the right tool here, not a shortcut.

Output: data/processed/nlp_conditions.csv
  (GENUS, SPECIES, category, matched_terms, n_mentions)
"""
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd
import spacy
from spacy.matcher import PhraseMatcher

PROC = Path(__file__).resolve().parents[2] / "data" / "processed"

# A small controlled vocabulary for traditional/ethnopharmacological text.
# Keys are human-readable condition categories; values are the surface forms
# (including archaic pharmacological terms) that indicate that category in
# 19th/20th-century botanical prose such as PROSEA's.
LEXICON = {
    "Digestive": [
        "stomachic", "carminative", "dyspeptic", "dyspepsia", "diarrhoea", "diarrhea",
        "dysentery", "constipation", "laxative", "purgative", "demulcent", "indigestion",
        "flatulence", "worms", "anthelmintic", "vomiting", "nausea", "stomach ache",
        "abdominal pain", "intestinal", "gastric",
    ],
    "Respiratory": [
        "cough", "asthma", "bronchitis", "tuberculosis", "catarrh", "cold", "colds",
        "expectorant", "whooping cough", "chest pain", "pneumonia",
    ],
    "Skin and wounds": [
        "wound", "wounds", "ulcer", "ulcers", "skin eruption", "dermatitis", "burn",
        "burns", "cut", "cuts", "bruise", "bruises", "itch", "eczema", "smallpox",
        "boil", "boils", "abscess", "poultice", "skin infection", "scabies", "sore",
    ],
    "Fever and infection": [
        "fever", "malaria", "infection", "antiseptic", "febrifuge", "antimalarial",
        "antibacterial", "antiviral", "antifungal",
    ],
    "Pain and inflammation": [
        "rheumatism", "inflammation", "headache", "toothache", "analgesic", "anodyne",
        "swelling", "oedema", "edema", "arthritis", "neuralgia", "migraine", "pains",
    ],
    "Women's health": [
        "menstruation", "menstrual", "childbirth", "parturition", "lactation",
        "uterine", "gynaecological", "gynecological", "contraceptive", "irregular menstruation",
        "emmenagogue", "abortifacient",
    ],
    "Cardiovascular and metabolic": [
        "blood pressure", "hypertension", "cholesterol", "diabetes", "heart disease",
        "circulation", "diabetic", "blood sugar",
    ],
    "Urinary and kidney": [
        "urinary", "kidney", "diuretic", "venereal", "gonorrhea", "gonorrhoea",
        "kidney stone", "bladder",
    ],
    "Nervous system": [
        "sedative", "narcotic", "epilepsy", "convulsion", "anticonvulsant", "insomnia",
        "nerve tonic", "spasm", "antispasmodic", "soporific", "tetanus",
    ],
    "Cancer and tumour": [
        "cancer", "tumour", "tumor", "antitumor", "carcinoma", "cancerous",
    ],
    "Liver": [
        "liver", "jaundice", "hepatic", "liver trouble",
    ],
    "General tonic and vitality": [
        "tonic", "stimulant", "aphrodisiac", "impotence", "stamina", "tonic for",
    ],
    "Eye and ENT": [
        "eye disease", "ophthalmia", "earache", "eye irritation", "conjunctivitis",
    ],
    "Parasites and bites": [
        "insecticidal", "nematicidal", "fungicidal", "pesticide", "insect bite",
        "insect bites", "snakebite", "snake bite", "antidote", "poison",
    ],
}


def build_matcher(nlp):
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    term_to_category = {}
    for category, terms in LEXICON.items():
        patterns = [nlp.make_doc(t) for t in terms]
        matcher.add(category, patterns)
        for t in terms:
            term_to_category[t] = category
    return matcher


def main():
    seed = pd.read_csv(PROC / "plants_seed.csv", dtype=str, keep_default_na=False)
    nlp = spacy.blank("en")
    matcher = build_matcher(nlp)

    rows = []
    n_with_hits = 0
    for _, row in seed.iterrows():
        text = row.get("USES_TEXT", "")
        if not text:
            continue
        doc = nlp(text.lower())
        matches = matcher(doc)
        if not matches:
            continue
        n_with_hits += 1

        by_category = defaultdict(list)
        for match_id, start, end in matches:
            category = nlp.vocab.strings[match_id]
            by_category[category].append(doc[start:end].text)

        for category, terms in by_category.items():
            rows.append(
                {
                    "GENUS": row["GENUS"],
                    "SPECIES": row["SPECIES"],
                    "category": category,
                    "matched_terms": "; ".join(sorted(set(terms))),
                    "n_mentions": len(terms),
                }
            )

    out = pd.DataFrame(rows)
    out.to_csv(PROC / "nlp_conditions.csv", index=False)
    print(f"Species with >=1 NLP match: {n_with_hits}/{len(seed)}")
    print(f"Total (species, category) rows: {len(out)}")
    print(f"Distinct categories found: {out['category'].nunique()}")
    print(out["category"].value_counts())
    print(f"Saved -> {PROC / 'nlp_conditions.csv'}")


if __name__ == "__main__":
    main()
