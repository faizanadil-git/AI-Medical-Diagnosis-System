"""
Builds and queries a Bayesian Network on-the-fly from the disease / symptom
structure stored in Neo4j.  CPDs are naïve – every symptom is assumed
conditionally independent given the disease, with probabilities taken from a
JSON file or default heuristic (0.8 if known, MIN_PROB if not).
"""
from __future__ import annotations
import json
from datetime import time
from pathlib import Path

from typing import Dict, List
from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination
from pyexpat import model
from torch.onnx._internal.diagnostics import diagnose
from functools import lru_cache
from neo4j_utils import driver, upsert_special_case, create_diagnosis, log_audit, diseases_by_symptoms, \
    find_special_case
from settings import MIN_PROB, UNUSUAL_THRESH
from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination

_PROB_FILE = Path("symptom_probabilities.json")   # optional

def _load_probs() -> Dict[str, Dict[str, float]]:
    if _PROB_FILE.exists():
        return json.loads(_PROB_FILE.read_text())
    return {}               # fall back to defaults


def _fetch_graph() -> Dict[str, List[str]]:
    """
    Pull current disease-symptom mapping from Neo4j.
    """
    mapping: Dict[str, List[str]] = {}
    with driver.session() as sess:
        recs = sess.run("""
            MATCH (d:Disease)-[:HAS_SYMPTOM]->(s:Symptom)
            RETURN d.name AS dis, collect(s.name) AS syms
        """)
        for r in recs:
            mapping[r["dis"]] = r["syms"]
    return mapping


def build_model() -> DiscreteBayesianNetwork:
    probs = _load_probs()
    mapping = _fetch_graph()

    edges = []
    cpds = []

    for dis, syms in mapping.items():
        for sym in syms:
            edges.append((sym, dis))  # Connect symptoms to diseases

    model = DiscreteBayesianNetwork(edges)

    # Symptom priors (uninformed 0.5/0.5 for each symptom)
    uniq_syms = {s for syms in mapping.values() for s in syms}
    for s in uniq_syms:
        cpds.append(TabularCPD(variable=s, variable_card=2,
                               values=[[0.5], [0.5]]))  # 0 = absent, 1 = present

    # Disease CPDs
    for dis, syms in mapping.items():
        e_card = [2] * len(syms)  # Two values for each symptom (0 and 1)
        row_true = []
        row_false = []

        for i in range(2 ** len(syms)):
            # Binary pattern for evidence row
            bits = [(i >> j) & 1 for j in reversed(range(len(syms)))]
            p_true = probs.get(dis, {}).get("base_prob", MIN_PROB)
            for b, sym in zip(bits, syms):
                if b == 1:  # symptom present
                    p_true = max(p_true, probs.get(dis, {}).get(sym, 0.8))
            row_true.append(p_true)
            row_false.append(1 - p_true)

        cpds.append(TabularCPD(variable=dis, variable_card=2,
                               values=[row_false, row_true],
                               evidence=syms, evidence_card=e_card))

    model.add_cpds(*cpds)
    model.check_model()  # Ensure the model is valid
    return model
# ----------------------------- Diagnosis ------------------------------- #

def diagnose_patient():
    """Interactive patient diagnosis."""
    person = input("Patient name: ")
    syms = [
        s.strip().title()
        for s in input("List present symptoms comma-sep: ").split(",")
        if s.strip()
    ]

    # ——— special-case bundle lookup ———
    sc = find_special_case(syms)
    if sc:
        first = time.strftime(
            "%Y-%m-%d",
            time.localtime(sc.get("first_seen", 0) / 1000)
        )
        print(
            f"⚠️  Special-case bundle recognised!  "
            f"Seen {sc.get('hits', 1)} time(s), first on {first}."
        )

    # ——— choose match mode ———
    mode = input(
        "Match mode – (a)ll symptoms, (p)artial ≥2, (w)ide ≥1  [a]: "
    ).strip().lower()
    if mode == "p":
        min_matches = 2
    elif mode == "w":
        min_matches = 1
    else:  # default "all"
        min_matches = None

    diseases = diseases_by_symptoms(syms, min_matches)

    # graceful fallback: if strict search empty → try ≥2 symptoms
    if not diseases and min_matches is None:
        diseases = diseases_by_symptoms(syms, 2)
        if diseases:
            print(
                "No disease matched *all* symptoms – "
                "showing diseases that match at least 2."
            )

    print("Diseases in KG matching criteria:", diseases or "None")

    # Perform Bayesian inference and display results
    model = build_model()  # Make sure the model is built
    infer = VariableElimination(model)

    # Prepare evidence for Bayesian Inference (assuming symptoms are present)
    evidence = {symptom: 1 for symptom in syms}  # 1 means "present"

    # Loop through all diseases and get their probabilities
    result = {}
    for disease in diseases:
        prob = infer.query(variables=[disease], evidence=evidence)[disease].values[1]
        result[disease] = round(float(prob), 4)

    # Display results
    for d, p in sorted(result.items(), key=lambda x: -x[1]):
        print(f"{d}: {p * 100:.2f}%")

        # Show the symptom probabilities for this disease
        print(f"Symptoms probabilities given {d}:")
        for symptom in syms:
            symptom_cpd = model.get_cpds(symptom)
            if symptom_cpd:
                prob_symptom_given_disease = symptom_cpd.values[1]  # probability of symptom given disease
                print(f" - P({symptom} | {d}): {prob_symptom_given_disease * 100:.2f}%")
            else:
                print(f" - No data for {symptom} given {d}.")

    # Handle unusual cases if all disease probabilities are below a threshold
    if is_unusual(result):
        print(
            "⚠️  Unusual case – storing as special bundle for future alerts."
        )
        upsert_special_case(syms)
        log_audit("UNUSUAL_CASE", {"person": person, "symptoms": syms})

    # Store the best guess (disease with the highest probability)
    if result:
        best = max(result, key=result.get)
        create_diagnosis(person, best, result[best])
        print(f"✓ Recorded diagnosis {best} for {person}")

def is_unusual(prob_dict: Dict[str, float]) -> bool:
    """
    True if every disease probability is below the configured threshold.
    """
    return all(p < UNUSUAL_THRESH for p in prob_dict.values())


# Cache the model to avoid rebuilding it every time
_cached_model = None


def build_model() -> DiscreteBayesianNetwork:
    global _cached_model

    # If the model is already built and cached, return the cached model
    if _cached_model is not None:
        return _cached_model

    # Fetching probabilities and graph data from Neo4j
    probs = _load_probs()
    mapping = _fetch_graph()

    edges = []
    cpds = []

    # Create edges (connections between symptoms and diseases)
    for dis, syms in mapping.items():
        for sym in syms:
            edges.append((sym, dis))  # Connect symptoms to diseases

    model = DiscreteBayesianNetwork(edges)

    # Symptom priors (uninformative 0.5/0.5 for each symptom)
    uniq_syms = {s for syms in mapping.values() for s in syms}
    for s in uniq_syms:
        cpds.append(TabularCPD(variable=s, variable_card=2,
                               values=[[0.5], [0.5]]))  # 0 = absent, 1 = present

    # Disease CPDs
    for dis, syms in mapping.items():
        e_card = [2] * len(syms)  # Two values for each symptom (0 and 1)
        row_true = []
        row_false = []

        for i in range(2 ** len(syms)):
            bits = [(i >> j) & 1 for j in reversed(range(len(syms)))]
            p_true = probs.get(dis, {}).get("base_prob", MIN_PROB)
            for b, sym in zip(bits, syms):
                if b == 1:  # symptom present
                    p_true = max(p_true, probs.get(dis, {}).get(sym, 0.8))
            row_true.append(p_true)
            row_false.append(1 - p_true)

        cpds.append(TabularCPD(variable=dis, variable_card=2,
                               values=[row_false, row_true],
                               evidence=syms, evidence_card=e_card))

    # Add CPDs to the model and check if the model is valid
    model.add_cpds(*cpds)
    model.check_model()  # Ensure the model is valid

    # Cache the model so we can reuse it
    _cached_model = model

    return model


# Optionally, you can invalidate the cache if necessary
def invalidate_cache():
    global _cached_model
    _cached_model = None