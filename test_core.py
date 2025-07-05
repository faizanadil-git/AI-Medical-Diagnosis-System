"""
Unit-tests for the mini medical–diagnosis project.
Run with:  pytest -q
"""

from typing import Iterable
import pytest

# ---------- 1. NLP extraction ------------------------------------------- #
from nlp_utils import extract_disease_symptom


def test_extract_disease_symptom():
    sent = "Flu has symptoms Fever, Cough."
    pairs = extract_disease_symptom(sent)

    assert ("Flu", "Fever") in pairs
    assert ("Flu", "Cough") in pairs
    assert len(pairs) == 2


# ---------- 2. Special-case key helper ---------------------------------- #
from neo4j_utils import _sym_key


@pytest.mark.parametrize(
    "symptoms, expected",
    [
        (["Cough", "Fever"], "Cough|Fever"),
        (["Fever", "cough", "Fever"], "Cough|Fever"),  # duplicates & case
    ],
)
def test_sym_key_ordering(symptoms: Iterable[str], expected: str):
    assert _sym_key(symptoms) == expected


# ---------- 3. diseases_by_symptoms (DB mocked) ------------------------- #
from neo4j_utils import diseases_by_symptoms


# Dummy objects that imitate neo4j records / sessions
class _Rec(dict):
    def __init__(self, name):
        super().__init__(name=name)


class _DummySession:
    def __init__(self, names):
        self._names = names

    def run(self, q, params):
        return [_Rec(n) for n in self._names]

    # Context-manager protocol
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


class _DummyDriver:
    def __init__(self, names):
        self._names = names

    def session(self):
        return _DummySession(self._names)


def test_diseases_by_symptoms(monkeypatch):
    """
    Monkey-patch neo4j_utils.driver so no real DB is needed.
    """
    import neo4j_utils

    dummy = _DummyDriver(["Flu", "COVID-19"])
    monkeypatch.setattr(neo4j_utils, "driver", dummy, raising=True)

    diseases = diseases_by_symptoms(["Fever", "Cough"], min_matches=2)
    assert diseases == ["Flu", "COVID-19"]
