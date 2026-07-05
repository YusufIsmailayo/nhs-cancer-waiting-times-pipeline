"""
cwt_query.py — the query layer my public agent calls.

This is the seam between my pipeline and the agent. My notebooks compute the numbers and
write the Gold table; this module is the ONLY way the agent reads them. It does three jobs
and nothing else:

  1. It defines the result contract — one frozen shape every query returns.
  2. It resolves what a person typed ("Shrewsbury") to a trust, deterministically.
  3. It assembles the result object for one trust, reading every figure from the table.

Two deliberate boundaries:
  - I depend on pandas alone — not on cwt_utils, which pulls in matplotlib for my charts.
    The public agent's runtime should carry as little as possible, so the 85% standard lives
    here as a constant (it matches cwt.TARGETS["62D"] by design).
  - I never compute a performance figure here. I only ever read what the Gold table already
    holds. The maths is owned once, in Silver. The answer layer rounds rates to a percentage
    when it speaks; I keep them at full precision.

Yusuf Ismail | NHS Data Engineering Portfolio | Project 4
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional
import re

import pandas as pd

# The 85% standard the 62-day combined figure is judged against. I keep my own copy so the
# agent runtime needs only pandas; it equals cwt.TARGETS["62D"].
STANDARD_62D = 0.85

# The one public source for every number this agent reports.
SOURCE_URL = (
    "https://www.england.nhs.uk/statistics/statistical-work-areas/cancer-waiting-times/"
)


# ── The contract ──────────────────────────────────────────────────────────
# These dataclasses ARE the agreement between my query layer and the answer layer. The shape
# is frozen now; v2's Confidence Layer fills `caveats`, it does not reshape anything.

@dataclass
class MonthPoint:
    """One month's headline rate. I use this for each point on the trend, and for the
    England comparison. Lean on purpose — it's what the answer layer reads to describe a
    trajectory or a comparison, so I don't weigh it down with counts it won't use."""
    period_month: str          # 'YYYY-MM'
    compliance_rate: float     # 0–1, full precision


@dataclass
class LatestPerformance:
    """The most recent month, richer — this is the one place the answer quotes real patient
    counts ("192 of 288 treated within 62 days"), so this is where the counts belong."""
    period_month: str
    compliance_rate: float
    total_patients: float
    within_62d: float
    breached_62d: float


@dataclass
class Provenance:
    """Where the answer's numbers come from. Every result carries this — provenance is not
    optional for a tool that speaks about the NHS."""
    data_month: str
    source_url: str = SOURCE_URL


@dataclass
class TrustResult:
    """The single shape every successful query returns. The answer layer consumes exactly
    this and nothing else."""
    trust: dict                              # {"org_code": ..., "org_name": ...}
    metric: str                              # '62d_combined'
    latest: LatestPerformance
    trend: list                              # list[MonthPoint], every month for this trust
    england: Optional[MonthPoint]            # England on the trust's latest month
    standard: float                          # 0.85
    provenance: Provenance
    caveats: list = field(default_factory=list)   # the v2 seam — always [] in v1

    def to_dict(self) -> dict:
        """I hand the answer layer a plain dict (JSON-ready) so the prompt can show the model
        clean structured facts to narrate."""
        return asdict(self)


# ── Trust-name resolution ─────────────────────────────────────────────────
# This is the part I keep deliberately boring. Fuzzy or probabilistic matching is exactly
# where a tool silently returns the WRONG hospital and then answers confidently about it —
# the worst failure this agent could have. So I match deterministically and, when more than
# one trust fits, I refuse to guess: I hand back every candidate and let the agent ask.

# Words in nearly every trust name that carry no signal for matching.
_NOISE = re.compile(r"\b(the|nhs|foundation|trust)\b")


def _normalise(name: str) -> str:
    """I lowercase, strip the boilerplate words, drop punctuation and collapse whitespace,
    so 'THE SHREWSBURY AND TELFORD HOSPITAL NHS TRUST' and a typed 'shrewsbury and telford'
    can meet on common ground."""
    s = name.lower()
    s = _NOISE.sub(" ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def resolve_trust(df: pd.DataFrame, query: str) -> list[dict]:
    """I turn what a person typed into candidate trusts — never a single silent guess.

    I return a list of {"org_code", "org_name"}:
        0 candidates  -> not found        (the agent says so plainly)
        1 candidate   -> resolved         (the agent proceeds)
        2+ candidates -> ambiguous        (the agent asks which one)

    Note: a trust that changed org code mid-period can legitimately appear twice here, under
    its old and new codes. In v1 I surface both as candidates; merging them is the v2
    Confidence Layer's job (the 'org code changes' caveat)."""
    q = query.strip()
    if not q:
        return []

    # The distinct real trusts. Every month repeats the name, so I de-duplicate; England's
    # 'Total' row is the national aggregate, not a trust, so I drop it from what's resolvable.
    trusts = (
        df.loc[df["org_code"] != "Total", ["org_code", "org_name"]]
        .drop_duplicates()
        .to_dict("records")
    )

    # 1) If they typed an exact org code (e.g. 'RXW'), I honour it directly — unambiguous.
    code = q.upper()
    by_code = [t for t in trusts if t["org_code"] == code]
    if by_code:
        return by_code

    # 2) Otherwise I match normalised names by containment, both directions, so a short query
    #    finds the long official name and a query that embeds the full name still matches.
    nq = _normalise(q)
    if not nq:
        return []
    return [
        t for t in trusts
        if nq in _normalise(t["org_name"]) or _normalise(t["org_name"]) in nq
    ]


# ── The lookup ────────────────────────────────────────────────────────────

def get_trust_performance(df: pd.DataFrame, org_code: str) -> TrustResult:
    """I assemble the frozen result object for one trust, by org code.

    I assume the code is valid — the agent resolves a name to a code first. If it yields no
    rows I fail loudly rather than return an empty shell. Every number comes straight from
    the Gold table; I compute none of them here."""
    rows = df[df["org_code"] == org_code].sort_values("period_date")
    if rows.empty:
        raise ValueError(f"No rows in the Gold table for org_code {org_code!r}.")

    # The most recent spelling on record — handles a trust renamed mid-period.
    org_name = str(rows["org_name"].iloc[-1])

    # The trust's OWN latest reported month — not the dataset's latest, which can differ if
    # this trust stopped reporting (again, an org-code-change case for the v2 caveat layer).
    latest_row = rows.iloc[-1]
    latest_month = str(latest_row["period_month"])

    latest = LatestPerformance(
        period_month=latest_month,
        compliance_rate=float(latest_row["compliance_rate"]),
        total_patients=float(latest_row["total_patients"]),
        within_62d=float(latest_row["within_62d"]),
        breached_62d=float(latest_row["breached_62d"]),
    )

    # Every month for this trust, oldest to newest — the trajectory the answer describes.
    trend = [
        MonthPoint(period_month=str(r.period_month),
                   compliance_rate=float(r.compliance_rate))
        for r in rows.itertuples()
    ]

    # England on the SAME month, so the comparison the agent draws is strictly like-for-like.
    eng = df[(df["org_code"] == "Total") & (df["period_month"] == latest_month)]
    if eng.empty:
        # England's aggregate reports every month, so this should not happen. But I will not
        # fabricate a national comparison if it is somehow missing — I leave it None and let
        # the answer layer say the national figure is unavailable for this month.
        england: Optional[MonthPoint] = None
    else:
        england = MonthPoint(period_month=latest_month,
                             compliance_rate=float(eng["compliance_rate"].iloc[0]))

    return TrustResult(
        trust={"org_code": org_code, "org_name": org_name},
        metric=str(latest_row["metric"]),
        latest=latest,
        trend=trend,
        england=england,
        standard=STANDARD_62D,
        provenance=Provenance(data_month=latest_month),
        caveats=[],
    )


def load_gold_table(path) -> pd.DataFrame:
    """I load the agent's Gold table once, at startup. It's a few thousand rows, so the agent
    holds it in memory and every query is an in-memory filter — no database, no per-request
    I/O, and the whole thing is unit-testable with no fixtures to stand up."""
    return pd.read_parquet(path)
