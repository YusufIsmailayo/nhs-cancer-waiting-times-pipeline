"""
cwt_serve.py — the pure logic the public app runs: turn what a visitor typed into a trust, and
decide which precomputed answer fits. No AI, no API key, pandas only — so it deploys anywhere and
is fully testable. app.py is a thin Streamlit shell over these functions.

Resolution here is sentence-tolerant (a visitor types a whole question, not a bare trust name),
but it keeps the same principle as the rest of the project: it is deterministic, and when several
trusts match it returns them all rather than guessing one.

Yusuf Ismail | NHS Data Engineering Portfolio | Project 4
"""
from __future__ import annotations

import re

import pandas as pd

# A personal "what about MY wait" question — so the app shows the answer that opens with the
# "no one can predict your wait" reframe.
_PERSONAL = re.compile(r"\b(i|i'm|im|me|my|mine|myself)\b|how long (will|do|would|does)",
                       re.IGNORECASE)

# Words common to many trust names (and to questions), so they don't identify one trust alone.
_GENERIC = {
    "nhs", "foundation", "trust", "hospital", "hospitals", "university", "royal", "general",
    "healthcare", "health", "care", "centre", "center", "cancer", "treatment", "waiting",
    "times", "and", "the", "of", "for",
}


def looks_personal(question: str) -> bool:
    """I decide which precomputed answer fits: the personal reframe, or the general one."""
    return bool(_PERSONAL.search(question or ""))


def _distinctive(text: str) -> set:
    """I reduce text to its identifying words: lowercase, 4+ letters, not generic filler.
    So 'THE SHREWSBURY AND TELFORD HOSPITAL NHS TRUST' -> {'shrewsbury', 'telford'}."""
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) >= 4 and w not in _GENERIC}


def resolve_from_question(df: pd.DataFrame, question: str) -> list[dict]:
    """I find which trust(s) the visitor means, from their whole question.

    I match on shared distinctive words (so 'how is shrewsbury doing?' finds Shrewsbury), and
    when several trusts share a word ('manchester') I return them all for the app to ask — I
    never silently pick one. No match returns an empty list, and the app falls back to a picker."""
    trusts = (df.loc[df["org_code"] != "Total", ["org_code", "org_name"]]
              .drop_duplicates().to_dict("records"))
    qwords = _distinctive(question)
    if not qwords:
        return []
    return [t for t in trusts if qwords & _distinctive(t["org_name"])]
