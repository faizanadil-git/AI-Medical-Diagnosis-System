from __future__ import annotations
import spacy
from typing import List, Tuple, Dict

nlp = spacy.load("en_core_web_sm")

# --------------------------- Low-level helpers --------------------------- #
def _get_full_span(token) -> str:
    """
    Return the complete noun-phrase span for a token (handles compounds / amods).
    """
    parts = list(token.lefts) + [token] + list(token.rights)
    entity_tokens = [t for t in parts
                     if t.dep_ in ("compound", "amod")
                     or t == token
                     or t.pos_ in ("PROPN", "NOUN")]
    entity_tokens = sorted(set(entity_tokens), key=lambda t: t.i)
    return " ".join(t.text for t in entity_tokens)


# --------------------------- Triplet extraction -------------------------- #
def extract_triplets(sentence: str) -> List[Tuple[str, str, str]]:
    """
    Generic (subject, predicate, object) extractor – good enough for the
    medical sentences in the assignment; passive voice supported.
    """
    doc = nlp(sentence)
    triplets = []

    for token in doc:
        if token.pos_ != "VERB":
            continue

        subs = [w for w in token.lefts if w.dep_ in ("nsubj", "nsubjpass")]
        objs = [w for w in token.rights if w.dep_ in ("dobj", "attr", "pobj")]

        # prepositional objects
        for prep in [w for w in token.rights if w.dep_ == "prep"]:
            objs.extend([w for w in prep.rights if w.dep_ == "pobj"])

        # passive “by” agents
        agents = []
        for prep in [w for w in token.rights if w.dep_ == "prep" and w.text == "by"]:
            agents.extend([w for w in prep.rights if w.dep_ == "pobj"])
        if agents:                               # passive voice => flip direction
            for subj in subs:
                for ag in agents:
                    triplets.append((_get_full_span(ag),
                                     token.lemma_,
                                     _get_full_span(subj)))
            continue

        # active voice
        for subj in subs:
            for obj in objs:
                pred = token.lemma_
                preps = [w.text for w in token.rights if w.dep_ == "prep"]
                if preps:
                    pred += "_" + "_".join(preps)
                triplets.append((_get_full_span(subj), pred, _get_full_span(obj)))

    return triplets


# ---------------- Disease / Symptom specific ---------------------------- #
def extract_disease_symptom(sentence: str) -> List[Tuple[str, str]]:
    """
    Very small grammar: “… has symptoms Fever, Cough …”
    Returns list of (disease, symptom) pairs.
    """
    doc = nlp(sentence)
    disease = None
    symptoms: List[str] = []

    for token in doc:
        # disease is usually first Noun before 'has'
        if token.text.lower() == "has" and token.dep_ == "ROOT":
            left = [w for w in token.lefts if w.pos_ in ("PROPN", "NOUN")]
            if left:
                disease = _get_full_span(left[-1])

    # gather symptom list after keywords 'symptom' / 'symptoms'
    for i, tok in enumerate(doc):
        if tok.lemma_.lower().startswith("symptom"):
            symptoms = [t.text.strip(",") for t in doc[i+1:] if t.pos_ in ("PROPN", "NOUN")]
            break

    return [(disease, s) for s in symptoms if disease and s]
