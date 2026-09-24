"""
Settings for The Unofficial Guide.

Everything you're likely to change lives here, at the top, on purpose.
You'll edit THRESHOLD in Milestone 4 and the chunking numbers in Milestone 3.

Anything you set in your .env file wins over the defaults here.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")


# ─── The corpus you're working with ──────────────────────────────────────────
# Change this to switch corpora, or pass --corpus on the command line.
# Options are the folder names inside corpora/. See corpora/README.md.

CORPUS = os.getenv("AI201_CORPUS", "campus_life")


# ─── Chunking (Milestone 3) ──────────────────────────────────────────────────
# Measured against campus_life: 88 posts, 178-549 characters each, every one
# opening with a bare title line, 271 paragraph blocks with a median of 93
# characters. See README "Chunking Strategy" for the experiment behind these.
#
# CHUNK_SIZE is a SOFT target, not a hard cut. chunker.py::split_documents
# never splits a paragraph, so a single long paragraph produces a chunk over
# this size rather than being cut in half.

CHUNK_SIZE = 300        # target characters per chunk, title included
CHUNK_OVERLAP = 100     # characters of whole trailing sentences carried forward


# ─── Retrieval (Milestone 4) ─────────────────────────────────────────────────

TOP_K = 4               # how many chunks to pull back per question
# Measured in Milestone 4: the answer-bearing chunk comes back at rank 1 for
# all five test questions, so k is not doing retrieval work — it is deciding
# how much loosely-related material rides along into the prompt. At k=5 the
# fifth chunk sat at 0.632-0.747 for four of the five, i.e. past the gate's own
# cutoff. Dropping to 4 removes it at no cost to criterion 1.

# The relevance gate. If the best chunk is further away than this, the system
# refuses to answer instead of handing the model thin material.
#
# LOWER IS BETTER: 0.3 is a close match, 0.9 is unrelated.
#
# Measured in Milestone 4, and the starter's 0.6 turned out to be wrong here.
#
#   5 OUT_OF_SCOPE questions          0.825 - 0.932
#   5 test questions                  0.173 - 0.370
#   15 further questions the corpus
#   genuinely answers                 0.170 - 0.610   <-- the one that matters
#
# The five test questions all target short single-topic admin posts, so they
# make the in-corpus group look tighter than it is. Widen the sample and the
# ceiling moves to 0.610 — "Do I need an adviser signature to withdraw?",
# which admin_withdrawal_deadline.txt answers in those exact words. At 0.6 the
# gate refuses it.
#
# The real gap is 0.610 to 0.825. 0.70 sits in it with room on both sides:
# 0.090 above the hardest answerable question, 0.125 below the easiest
# out-of-scope one. Criterion 3 still refuses 5 of 5.
THRESHOLD = 0.70


# ─── Models ──────────────────────────────────────────────────────────────────
# Embeddings run on your own machine and cost no API quota.
# Only generation calls out to a service.

# This is the model Chroma bundles, and leaving it alone is the fast path: it
# downloads about 80 MB from Chroma's own CDN and needs nothing else installed.
#
# Setting it to any other name — unit 2's "try a second embedding model"
# stretch option — switches to loading that model from Hugging Face instead,
# which needs `pip install 'sentence-transformers>=3.4,<3.5'` first. store.py
# says so with a real error message rather than a stack trace if you forget.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
MODEL = os.getenv("AI201_MODEL", "gemini-3.5-flash-lite")


# ─── Rate limiting and quota guards ──────────────────────────────────────────
# You should not need to touch these. They exist so that a runaway loop costs
# you a warning instead of your whole day's allowance.

REQUESTS_PER_MINUTE = 30       # outgoing calls the limiter will allow per minute
SESSION_REQUEST_BUDGET = 300   # stop and warn rather than draining the daily quota
MAX_RETRIES = 4                # on 429 / resource-exhausted, with backoff

CACHE_ENABLED = os.getenv("AI201_CACHE", "1") != "0"
CACHE_DIR = ROOT / ".cache"


# ─── Paths ───────────────────────────────────────────────────────────────────

CORPORA_DIR = ROOT / "corpora"
CHROMA_DIR = ROOT / "chroma_db"
RESULTS_DIR = ROOT / "results"


def corpus_path(name: str | None = None) -> Path:
    """Folder holding the documents for a corpus."""
    return CORPORA_DIR / (name or CORPUS) / "documents"


def collection_name(name: str | None = None, variant: str = "default") -> str:
    """
    Name of the vector-store collection for a corpus.

    `variant` lets you index the same corpus two different ways and query both
    without deleting anything — you'll want that in unit 2 when you compare
    chunking strategies.

    Chroma is fussy about collection names: 3 to 63 characters, starting and
    ending with a letter or digit, and nothing but letters, digits, underscores
    and hyphens in between. If you bring your own corpus and name the folder
    something Chroma won't accept, this cleans it up rather than failing.
    """
    import re

    raw = f"{name or CORPUS}__{variant}"
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", raw)
    cleaned = cleaned.strip("_-")          # must start and end alphanumeric
    if not cleaned or not cleaned[0].isalnum():
        cleaned = f"c{cleaned}"
    if not cleaned[-1].isalnum():
        cleaned = f"{cleaned}0"
    return cleaned[:63].rstrip("_-") or "collection"
