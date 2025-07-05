"""
Global config – nothing else in the codebase hard-codes credentials.
Override with environment variables in production.
"""
import os

# ── Neo4j connection ──────────────────────────────────────────────────────
NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")          # ya "" agar auth disabled
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j1234")     # ya "" agar auth disabled

# ── Bayesian-network defaults ─────────────────────────────────────────────
MIN_PROB       = float(os.getenv("MIN_PROB",       0.01))   # zero-prob khatam karne ke liye
UNUSUAL_THRESH = float(os.getenv("UNUSUAL_THRESH", 0.15))   # “unusual case” flag threshold