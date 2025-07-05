from pathlib import Path
from typing import List
from nlp_utils import extract_disease_symptom
from neo4j_utils import merge_disease, merge_symptom, connect_disease_symptom, log_audit

def read_knowledge_file(fp: str | Path) -> List[str]:
    """Read knowledge from the file and return processed lines."""
    try:
        with open(fp, 'r', encoding='utf-8') as file:
            lines = [line.strip() for line in file if line.strip()]
        log_audit("KNOWLEDGE_FILE_READ", {"file_path": fp, "lines_count": len(lines)})
        return lines
    except FileNotFoundError:
        log_audit("KNOWLEDGE_FILE_READ_ERROR", {"file_path": fp, "error": "File not found"})
        print("Error: Knowledge file not found.")
        return []

def load(fp="knowledge.txt"):
    """Load diseases and symptoms from the knowledge file to Neo4j."""
    try:
        for line in read_knowledge_file(fp):
            pairs = extract_disease_symptom(line)
            for disease, symptom in pairs:
                merge_disease(disease)
                merge_symptom(symptom)
                connect_disease_symptom(disease, symptom)
        print("✓ Knowledge graph populated.")
        log_audit("KNOWLEDGE_GRAPH_POPULATED", {"file_path": fp})
    except Exception as e:
        print(f"Error loading knowledge: {e}")
        log_audit("KNOWLEDGE_LOADING_ERROR", {"error": str(e)})
