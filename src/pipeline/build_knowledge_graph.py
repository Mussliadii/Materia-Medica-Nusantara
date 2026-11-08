"""
Assemble the final knowledge graph from the processed tables:

  Plant   --TRADITIONAL_USE-->  TraditionalUse   (data/processed/duke_traditional_uses_seed.csv,
                                                   filtered to our seed species)
  Plant   --CONTAINS-->         Chemical         (data/processed/duke_plant_chemicals_seed.csv)
  Chemical--HAS_ACTIVITY-->     Activity         (data/processed/duke_chemical_activities_seed.csv)

Plant nodes also carry local/Indonesian names (from PROSEA) and a modern-evidence
tier (from PubMed evidence linking) as attributes, so the dashboard can filter/
color by them without a graph traversal.

Output:
  data/processed/knowledge_graph.graphml  (full graph, for Gephi/other tools)
  data/processed/knowledge_graph.json     (node-link JSON, for the Streamlit app)
"""
import json
from pathlib import Path

import networkx as nx
import pandas as pd

PROC = Path(__file__).resolve().parents[2] / "data" / "processed"


def plant_id(genus: str, species: str) -> str:
    return f"plant:{genus.strip().lower()}_{species.strip().lower()}"


def use_id(label: str) -> str:
    return f"use:{label.strip().lower()}"


def chem_id(label: str) -> str:
    return f"chem:{label.strip().lower()}"


def activity_id(label: str) -> str:
    return f"activity:{label.strip().lower()}"


def main():
    seed = pd.read_csv(PROC / "plants_seed.csv", dtype=str, keep_default_na=False)
    seed_pairs = set(zip(seed["GENUS"].str.lower(), seed["SPECIES"].str.lower()))

    trad = pd.read_csv(PROC / "duke_traditional_uses_seed.csv", dtype=str, keep_default_na=False)
    chems = pd.read_csv(PROC / "duke_plant_chemicals_seed.csv", dtype=str, keep_default_na=False)
    acts = pd.read_csv(PROC / "duke_chemical_activities_seed.csv", dtype=str, keep_default_na=False)
    try:
        evidence = pd.read_csv(PROC / "pubmed_evidence.csv", dtype=str, keep_default_na=False)
        evidence_lookup = {
            (r["GENUS"].lower(), r["SPECIES"].lower()): r for _, r in evidence.iterrows()
        }
    except FileNotFoundError:
        evidence_lookup = {}

    seed_lookup = {
        (r["GENUS"].lower(), r["SPECIES"].lower()): r for _, r in seed.iterrows()
    }

    G = nx.MultiDiGraph()

    # Plant nodes (only our curated seed species)
    for (g, s), row in seed_lookup.items():
        pid = plant_id(g, s)
        ev = evidence_lookup.get((g, s), {})
        G.add_node(
            pid,
            node_type="Plant",
            genus=row["GENUS"],
            species=row["SPECIES"],
            latin_name=f"{row['GENUS']} {row['SPECIES']}",
            family=row.get("FAMILY", ""),
            local_names=row.get("LOCAL_NAMES", ""),
            source_url=row.get("SOURCE_URL", ""),
            evidence_tier=ev.get("evidence_tier", "not_queried"),
            pubmed_general_hits=ev.get("general_hits", ""),
            pubmed_clinical_hits=ev.get("clinical_trial_hits", ""),
        )

    # Plant -> TraditionalUse
    trad = trad[trad.apply(lambda r: (r["GENUS"].lower(), r["SPECIES"].lower()) in seed_pairs, axis=1)]
    for _, r in trad.iterrows():
        pid = plant_id(r["GENUS"], r["SPECIES"])
        uid = use_id(r["TRADITIONAL_USE"])
        G.add_node(uid, node_type="TraditionalUse", label=r["TRADITIONAL_USE"])
        G.add_edge(pid, uid, edge_type="TRADITIONAL_USE", country=r.get("COUNTRY", ""), reference=r.get("REFERENCE", ""))

    # Plant -> Chemical
    chems = chems[chems.apply(lambda r: (r["GENUS"].lower(), r["SPECIES"].lower()) in seed_pairs, axis=1)]
    plant_chems = set()
    for _, r in chems.iterrows():
        pid = plant_id(r["GENUS"], r["SPECIES"])
        cid = chem_id(r["CHEM"])
        G.add_node(cid, node_type="Chemical", label=r["CHEM"])
        G.add_edge(pid, cid, edge_type="CONTAINS", reference=r.get("REFERENCE", ""))
        plant_chems.add(r["CHEM"].lower())

    # Chemical -> Activity (only for chemicals actually present in our plants)
    acts = acts[acts["CHEM"].str.lower().isin(plant_chems)]
    for _, r in acts.iterrows():
        cid = chem_id(r["CHEM"])
        aid = activity_id(r["ACTIVITY"])
        G.add_node(aid, node_type="Activity", label=r["ACTIVITY"], superact=r.get("SUPERACT", ""))
        G.add_edge(cid, aid, edge_type="HAS_ACTIVITY", reference=r.get("REFERENCE", ""), citation=r.get("LONGREF", ""))

    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    for t in ["Plant", "TraditionalUse", "Chemical", "Activity"]:
        n = sum(1 for _, d in G.nodes(data=True) if d.get("node_type") == t)
        print(f"  {t}: {n}")

    nx.write_graphml(G, PROC / "knowledge_graph.graphml")

    data = nx.node_link_data(G, edges="edges")
    with open(PROC / "knowledge_graph.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print(f"Saved to {PROC / 'knowledge_graph.graphml'} and {PROC / 'knowledge_graph.json'}")


if __name__ == "__main__":
    main()
