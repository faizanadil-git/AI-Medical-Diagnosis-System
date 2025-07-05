
from __future__ import annotations
import time
import json
from typing import Iterable, List, Dict, Any
from neo4j import GraphDatabase, Driver, Session
from settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

# ── Neo4j driver ────────────────────────────────────────────────────────
driver: Driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD),
    max_connection_lifetime=3600,
)

# --------------------------- Low-level helpers -------------------------- #
def _run(query: str, **params):
    try:
        with driver.session() as session:
            session.run(query, **params)
    except Exception as e:
        print(f"Error executing query: {e}")
        log_audit("QUERY_ERROR", {"error": str(e), "query": query})


def close():
    try:
        driver.close()
    except Exception as e:
        print(f"Error closing Neo4j connection: {e}")
        log_audit("CONNECTION_CLOSE_ERROR", {"error": str(e)})

# --------------------------- Audit logging ----------------------------- #
def log_audit(action: str, details: dict):
    try:
        _run(
            """
            CREATE (:Audit {action:$action, details:$d, ts:timestamp()})
            """,
            action=action,
            d=json.dumps(details, ensure_ascii=False),
        )
    except Exception as e:
        _run(
            """
            CREATE (:AuditError {action:'AUDIT_LOGGING_FAILED',
                                 details:$d, ts:timestamp(), error:$err})
            """,
            d=json.dumps(details, ensure_ascii=False),
            err=str(e),
        )

# --------------------------- Entity management ------------------------- #
def merge_symptom(name: str):
    try:
        _run("MERGE (:Symptom {name:$name})", name=name)
        log_audit("MERGE_SYMPTOM", {"name": name})
    except Exception as e:
        log_audit("MERGE_SYMPTOM_ERROR", {"name": name, "error": str(e)})


def merge_disease(name: str, **attrs):
    try:
        _run("MERGE (d:Disease {name:$name}) SET d += $attrs",
             name=name, attrs=attrs)
        log_audit("MERGE_DISEASE", {"name": name, **attrs})
    except Exception as e:
        log_audit("MERGE_DISEASE_ERROR", {"name": name, "error": str(e)})


def connect_disease_symptom(disease: str, symptom: str):
    try:
        _run(
            """
            MATCH (d:Disease {name:$d}), (s:Symptom {name:$s})
            MERGE (d)-[:HAS_SYMPTOM]->(s)
            """,
            d=disease, s=symptom,
        )
        log_audit("CONNECT_DISEASE_SYMPTOM",
                  {"disease": disease, "symptom": symptom})
    except Exception as e:
        log_audit("CONNECT_DISEASE_SYMPTOM_ERROR",
                  {"disease": disease, "symptom": symptom, "error": str(e)})

# --------------------------- User / Admin ------------------------------ #
def merge_person(name: str, role: str = "User"):
    try:
        _run(
            """
            MERGE (p:Person {name:$name})
            ON CREATE SET p.role=$role
            ON MATCH  SET p.role=coalesce(p.role,$role)
            """,
            name=name, role=role,
        )
        log_audit("MERGE_PERSON", {"name": name, "role": role})
    except Exception as e:
        log_audit("MERGE_PERSON_ERROR",
                  {"name": name, "role": role, "error": str(e)})


def create_diagnosis(person: str, disease: str, confidence: float):
    try:
        _run(
            """
            MATCH (p:Person {name:$p}), (d:Disease {name:$d})
            MERGE (p)-[r:DIAGNOSED_WITH]->(d)
            SET r.confidence=$c, r.ts=timestamp()
            """,
            p=person, d=disease, c=confidence,
        )
        log_audit("CREATE_DIAGNOSIS",
                  {"person": person, "disease": disease, "confidence": confidence})
    except Exception as e:
        log_audit("CREATE_DIAGNOSIS_ERROR",
                  {"person": person, "disease": disease, "error": str(e)})

# --------------------------- Query helpers ----------------------------- #
def diseases_by_symptoms(
    symptoms: Iterable[str],
    min_matches: int | None = None
) -> List[str]:
    """
    Return diseases that match *at least* min_matches of the given
    symptoms.  If min_matches is None (default) **all** symptoms must
    match.

        >>> diseases_by_symptoms(["Fever", "Cough"])        # all
        >>> diseases_by_symptoms(["Fever", "Cough"], 2)     # ≥2
        >>> diseases_by_symptoms(["Fever", "Cough"], 1)     # ≥1
    """
    try:
        sympts = [s.strip().title() for s in symptoms if s.strip()]
        if not sympts:
            return []

        needed = len(sympts) if min_matches is None else max(1, min_matches)

        query = """
        MATCH (d:Disease)-[:HAS_SYMPTOM]->(s:Symptom)
        WHERE s.name IN $symptoms
        WITH d, collect(DISTINCT s.name) AS found
        WHERE size(found) >= $needed
        RETURN d.name AS name
        """

        with driver.session() as sess:
            recs = sess.run(query, {"symptoms": sympts, "needed": needed})
            return [r["name"] for r in recs]

    except Exception as e:
        log_audit("QUERY_DISEASES_BY_SYMPTOMS_ERROR",
                  {"symptoms": symptoms, "min_matches": min_matches,
                   "error": str(e)})
        return []

# --------------------------- Special-case helpers ----------------------- #
def _sym_key(symptoms: Iterable[str]) -> str:
    """Stable key like 'Cough|Leg Pain|Memory Loss'."""
    return "|".join(sorted({s.strip().title() for s in symptoms if s.strip()}))


def upsert_special_case(symptoms: Iterable[str]) -> Dict[str, Any] | None:
    #Create or update a SpecialCase node for this exact bundle.
    key = _sym_key(symptoms)
    sympts = list({s.strip().title() for s in symptoms if s.strip()})
    ts = int(time.time() * 1000)

    query = """
    MERGE (c:SpecialCase {sym_key:$key})
      ON CREATE SET c.symptoms=$symptoms,
                    c.first_seen=$ts,
                    c.hits=1
      ON MATCH  SET c.hits = c.hits + 1,
                    c.last_seen=$ts
    WITH c
    UNWIND $symptoms AS name
    MATCH (s:Symptom {name:name})
    MERGE (c)-[:HAS_SYMPTOM]->(s)
    RETURN c {.*, sym_key:c.sym_key} AS case
    """
    try:
        with driver.session() as sess:
            rec = sess.run(query, key=key, symptoms=sympts, ts=ts).single()
            log_audit("UPSERT_SPECIAL_CASE",
                      {"key": key, "symptoms": sympts})
            return rec["case"] if rec else None
    except Exception as e:
        log_audit("UPSERT_SPECIAL_CASE_ERROR",
                  {"key": key, "symptoms": sympts, "error": str(e)})
        return None


def find_special_case(symptoms: Iterable[str]) -> Dict[str, Any] | None:
    """Return an existing SpecialCase bundle, or None if not present."""
    key = _sym_key(symptoms)
    try:
        with driver.session() as sess:
            rec = sess.run(
                """
                MATCH (c:SpecialCase {sym_key:$key})
                RETURN c {.*, sym_key:c.sym_key} AS case
                """,
                key=key,
            ).single()
            return rec["case"] if rec else None
    except Exception as e:
        log_audit("FIND_SPECIAL_CASE_ERROR",
                  {"key": key, "error": str(e)})
        return None


# Add these new functions to your neo4j_utils.py file

def get_known_symptoms() -> List[str]:
    """Get all symptoms that exist in the knowledge base."""
    try:
        with driver.session() as sess:
            recs = sess.run("MATCH (s:Symptom) RETURN s.name AS name")
            return [r["name"] for r in recs]
    except Exception as e:
        log_audit("GET_KNOWN_SYMPTOMS_ERROR", {"error": str(e)})
        return []


def find_unknown_symptoms(symptoms: List[str]) -> List[str]:
    """Find symptoms that don't exist in the knowledge base."""
    known = set(get_known_symptoms())
    return [s for s in symptoms if s not in known]


def upsert_special_case_with_patient(symptoms: Iterable[str], patient_name: str) -> Dict[str, Any] | None:
    """Create or update a SpecialCase node with patient information."""
    key = _sym_key(symptoms)
    sympts = list({s.strip().title() for s in symptoms if s.strip()})
    ts = int(time.time() * 1000)

    query = """
    MERGE (c:SpecialCase {sym_key:$key})
      ON CREATE SET c.symptoms=$symptoms,
                    c.first_seen=$ts,
                    c.hits=1,
                    c.patients=[$patient]
      ON MATCH  SET c.hits = c.hits + 1,
                    c.last_seen=$ts,
                    c.patients = CASE 
                        WHEN $patient IN c.patients THEN c.patients
                        ELSE c.patients + [$patient]
                    END
    WITH c
    UNWIND $symptoms AS name
    MERGE (s:Symptom {name:name})
    MERGE (c)-[:HAS_SYMPTOM]->(s)
    RETURN c {.*, sym_key:c.sym_key} AS case
    """
    try:
        with driver.session() as sess:
            rec = sess.run(query, key=key, symptoms=sympts, ts=ts, patient=patient_name).single()
            log_audit("UPSERT_SPECIAL_CASE_WITH_PATIENT",
                      {"key": key, "symptoms": sympts, "patient": patient_name})
            return rec["case"] if rec else None
    except Exception as e:
        log_audit("UPSERT_SPECIAL_CASE_WITH_PATIENT_ERROR",
                  {"key": key, "symptoms": sympts, "patient": patient_name, "error": str(e)})
        return None


def find_similar_special_cases(symptoms: Iterable[str], similarity_threshold: float = 0.5) -> List[Dict[str, Any]]:
    """Find special cases with similar symptoms."""
    sympts = list({s.strip().title() for s in symptoms if s.strip()})

    query = """
    MATCH (c:SpecialCase)-[:HAS_SYMPTOM]->(s:Symptom)
    WHERE s.name IN $symptoms
    WITH c, collect(DISTINCT s.name) AS matched_symptoms
    WHERE size(matched_symptoms) >= $min_matches
    RETURN c {.*, sym_key:c.sym_key, matched_symptoms: matched_symptoms} AS case
    ORDER BY size(matched_symptoms) DESC
    """

    min_matches = max(1, int(len(sympts) * similarity_threshold))

    try:
        with driver.session() as sess:
            recs = sess.run(query, symptoms=sympts, min_matches=min_matches)
            return [r["case"] for r in recs]
    except Exception as e:
        log_audit("FIND_SIMILAR_SPECIAL_CASES_ERROR",
                  {"symptoms": sympts, "error": str(e)})
        return []


def get_symptom_disease_probabilities(symptom: str) -> Dict[str, float]:
    """Get probability of diseases given a specific symptom."""
    try:
        with driver.session() as sess:
            # Count total diseases that have this symptom
            total_query = """
            MATCH (d:Disease)-[:HAS_SYMPTOM]->(s:Symptom {name: $symptom})
            RETURN count(d) AS total
            """
            total_result = sess.run(total_query, symptom=symptom).single()
            total_diseases = total_result["total"] if total_result else 0

            if total_diseases == 0:
                return {}

            # Get diseases and their relative frequencies
            disease_query = """
            MATCH (d:Disease)-[:HAS_SYMPTOM]->(s:Symptom {name: $symptom})
            OPTIONAL MATCH (d)-[:HAS_SYMPTOM]->(all_symptoms:Symptom)
            WITH d, count(all_symptoms) AS symptom_count
            RETURN d.name AS disease, symptom_count
            ORDER BY symptom_count DESC
            """

            disease_results = sess.run(disease_query, symptom=symptom)
            probabilities = {}

            for record in disease_results:
                disease = record["disease"]
                # Simple probability calculation based on inverse of symptom count
                # Diseases with fewer symptoms are more likely given a specific symptom
                prob = 1.0 / (record["symptom_count"] + 1)  # +1 to avoid division by zero
                probabilities[disease] = prob

            # Normalize probabilities
            total_prob = sum(probabilities.values())
            if total_prob > 0:
                probabilities = {k: v / total_prob for k, v in probabilities.items()}

            return probabilities
    except Exception as e:
        log_audit("GET_SYMPTOM_DISEASE_PROBABILITIES_ERROR",
                  {"symptom": symptom, "error": str(e)})
        return {}