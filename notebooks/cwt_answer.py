"""
cwt_answer.py — the answer layer my agent speaks through.

This sits between the numbers and the words. My query layer hands me a TrustResult full of
figures; I turn it into FINDINGS — finished, checked statements — and only those go to the AI.

The whole design rests on one boundary:
  - My code decides every number and every comparison here. The rounding, the verdict against
    the 85% standard, the "slightly below England", the trend direction — all computed in this
    file, by rules I can read and test.
  - The AI receives finished phrases and assembles them into fluent prose. It is forbidden from
    introducing any number not already in the findings. It never sees a figure it must round or
    compare, so there is nothing for it to get wrong.

So the AI is the voice, never the source. Every fact traces back to my code; the model only
makes it read like plain English and handles the awkward cases.

The thresholds below are the only "opinions" in the layer, and I keep them named and in one
place so the wording is consistent and easy to tune.

Yusuf Ismail | NHS Data Engineering Portfolio | Project 4
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import cwt_query as q   # I reuse the TrustResult contract from my query layer.

# ── The wording thresholds — the only judgement calls, all in one place ────
JUST_BELOW_PP = 0.02   # within 2pp under the standard reads as "just below", not "below"
IN_LINE_PP    = 0.01   # within 1pp of England reads as "in line with"
SLIGHTLY_PP   = 0.05   # within 5pp of England reads as "slightly" above/below
FLAT_PP       = 0.03   # a change under 3pp over the period reads as "broadly flat"

# I map the machine metric name to the words a person understands. One entry today; new
# standards slot in here later without touching the logic.
_MEASURE = {
    "62d_combined": "the combined 62-day cancer standard (all referral routes)",
}

# The plain-English gloss of the standard, owned by code so the model can't improvise a
# wrong one. I keep it route-agnostic: the combined standard covers screening and consultant
# upgrades too, so I deliberately do NOT say "by a GP".
_MEASURE_PLAIN = {
    "62d_combined": "within 62 days of an urgent referral for suspected cancer",
}

# Coarse plain-language fractions. I pick the nearest anchor so the AI can say "two-thirds"
# without me letting it invent the figure — the fraction is my decision, not its.
_FRACTIONS = [
    (0.95, "almost all"), (0.90, "nine in ten"), (0.80, "four in five"),
    (0.75, "three-quarters"), (0.70, "seven in ten"), (0.667, "two-thirds"),
    (0.60, "six in ten"), (0.50, "half"), (0.40, "four in ten"),
    (0.333, "a third"), (0.25, "a quarter"), (0.20, "one in five"), (0.10, "one in ten"),
]

_SMALL = {"and", "of", "the", "for", "to", "in", "on", "at", "by"}
_FORCE_UPPER = {"nhs"}


def _pct(x: float) -> str:
    """I format a rate as a percentage to one decimal, dropping a trailing .0 so the 85%
    standard reads as '85%', not '85.0%'."""
    s = f"{x * 100:.1f}"
    return (s[:-2] if s.endswith(".0") else s) + "%"


def _month_label(ym: str) -> str:
    """I turn '2025-03' into 'March 2025'."""
    return datetime.strptime(ym, "%Y-%m").strftime("%B %Y")


def _approx_fraction(rate: float) -> str:
    """I return the nearest plain fraction phrase, e.g. 0.6655 -> 'two-thirds'. The extremes get
    their own honest words: a 0% trust must never be described as 'one in ten' (the nearest
    mid-range anchor), so 0 -> 'none' and 1 -> 'all'."""
    if rate <= 0.02:
        return "none"
    if rate >= 0.98:
        return "all"
    return min(_FRACTIONS, key=lambda fr: abs(fr[0] - rate))[1]


def present_name(name: str) -> str:
    """I title-case a trust's faithful uppercase name for display, keeping small words lower
    and NHS upper: 'THE SHREWSBURY AND TELFORD HOSPITAL NHS TRUST' ->
    'The Shrewsbury and Telford Hospital NHS Trust'."""
    out = []
    for i, w in enumerate(name.split()):
        lw = w.lower()
        if lw in _FORCE_UPPER:
            out.append(lw.upper())
        elif lw in _SMALL and i != 0:
            out.append(lw)
        else:
            out.append(w.capitalize())
    return " ".join(out).replace("'S ", "'s ")


@dataclass
class Findings:
    """The finished, checked statements about one trust. Every number a good answer needs is
    already a phrase in here — so the AI derives nothing."""
    subject: str            # "The Shrewsbury and Telford Hospital NHS Trust"
    measure: str            # "the combined 62-day cancer standard (all referral routes)"
    measure_plain: str      # "within 62 days of an urgent referral for suspected cancer"
    headline: str           # "66.6% of patients began treatment within 62 days in March 2025"
    counts: str             # "around 192 of 289 patients"
    approx_fraction: str    # "two-thirds"  (a proportion of patients, or rough odds)
    vs_standard: str        # "below the 85% standard"
    vs_england: str | None  # "slightly below England's 71.4% that month"
    trend: str              # "up from 56.4% in October 2023, and now at its highest..."
    limits: str             # fixed honesty statement about individual waits
    provenance: str         # "NHS England Cancer Waiting Times, data to March 2025"
    source_url: str
    caveats: list           # [] in v1; the v2 layer fills it


def build_findings(result: q.TrustResult) -> Findings:
    """I convert the numeric result into finished phrases. This is where the judging lives —
    after this function, no number is the AI's to decide."""
    latest = result.latest
    rate = latest.compliance_rate
    month = _month_label(latest.period_month)
    standard = result.standard

    headline = f"{_pct(rate)} of patients began treatment within 62 days in {month}"
    counts = f"around {round(latest.within_62d):,} of {round(latest.total_patients):,} patients"

    # Verdict against the 85% standard.
    gap = standard - rate
    if rate >= standard:
        vs_standard = f"meeting the {_pct(standard)} standard"
    elif gap <= JUST_BELOW_PP:
        vs_standard = f"just below the {_pct(standard)} standard"
    else:
        vs_standard = f"below the {_pct(standard)} standard"

    # Comparison to England, on the same month, with a tolerance band for the adverb.
    if result.england is None:
        vs_england = None
    else:
        e = result.england.compliance_rate
        diff = rate - e
        ad = abs(diff)
        ep = _pct(e)
        if ad <= IN_LINE_PP:
            vs_england = f"in line with England's {ep} that month"
        elif diff < 0:
            word = "slightly below" if ad <= SLIGHTLY_PP else "below"
            vs_england = f"{word} England's {ep} that month"
        else:
            word = "slightly above" if ad <= SLIGHTLY_PP else "above"
            vs_england = f"{word} England's {ep} that month"

    # Trend over the whole window. I anchor the change to the FIRST month (honest about the
    # starting point), then note if the latest month is the high or low of the series.
    rates = [p.compliance_rate for p in result.trend]
    first = result.trend[0]
    n = len(rates)
    delta = rate - first.compliance_rate
    fm = _month_label(first.period_month)
    if delta > FLAT_PP:
        trend = f"up from {_pct(first.compliance_rate)} in {fm}"
    elif delta < -FLAT_PP:
        trend = f"down from {_pct(first.compliance_rate)} in {fm}"
    else:
        trend = f"broadly flat over the {n} months"
    if n > 1 and rate >= max(rates) - 1e-9:
        trend += f", and now at its highest in the {n} months"
    elif n > 1 and rate <= min(rates) + 1e-9:
        trend += f", and now at its lowest in the {n} months"

    limits = ("no public data can predict how long any individual will wait; these figures "
              "describe the trust's recent record, not a personal forecast")

    return Findings(
        subject=present_name(result.trust["org_name"]),
        measure=_MEASURE.get(result.metric, result.metric),
        measure_plain=_MEASURE_PLAIN.get(result.metric, ""),
        headline=headline,
        counts=counts,
        approx_fraction=_approx_fraction(rate),
        vs_standard=vs_standard,
        vs_england=vs_england,
        trend=trend,
        limits=limits,
        provenance=f"NHS England Cancer Waiting Times, data to {month}",
        source_url=result.source_url if hasattr(result, "source_url") else result.provenance.source_url,
        caveats=list(result.caveats),
    )


def findings_to_brief(f: Findings) -> str:
    """I lay the findings out as a labelled brief — this exact text is what the AI reads."""
    lines = [
        f"TRUST: {f.subject}",
        f"MEASURE: {f.measure}",
        f"MEASURE (PLAIN): {f.measure_plain}",
        f"HEADLINE: {f.headline}",
        f"PATIENTS: {f.counts}",
        f"PLAIN FRACTION: {f.approx_fraction} (a proportion of patients, or rough odds for a new referral)",
        f"VS STANDARD: {f.vs_standard}",
        f"VS ENGLAND: {f.vs_england if f.vs_england else 'national figure unavailable for this month'}",
        f"TREND: {f.trend}",
        f"LIMITS: {f.limits}",
        f"SOURCE: {f.provenance}",
        f"SOURCE URL: {f.source_url}",
        f"CAVEATS: {'; '.join(f.caveats) if f.caveats else '(none)'}",
    ]
    return "\n".join(lines)


# ── The prompt contract ────────────────────────────────────────────────────
# This is the hard boundary in words. The model is told, plainly, that it is the voice and not
# the source: it may use only the figures in the brief, and must invent nothing.

SYSTEM_PROMPT = """You explain NHS cancer waiting-times performance to members of the public — including people who may be worried and who are not used to statistics. Write in plain, everyday British English.

You will be given FINDINGS: finished statements about one NHS trust, already computed and checked by code. You will also be given the person's QUESTION.

Write a short, calm, factual answer (2 to 4 short sentences) using ONLY the findings.

Make it easy to read:
- Lead with the plain-language proportion. The findings give it as a simple fraction (for example "two-thirds"); phrase it warmly as "about two in three people". Give the exact percentage straight afterwards, in support — never as the opening figure.
- The first time you mention the 62-day standard, explain it using the MEASURE (PLAIN) wording from the findings, and add nothing to it — do not name who makes the referral (for example a GP), and do not convert 62 days into other units such as weeks or months. You may keep its proper name too, but never leave the jargon unexplained.
- Use short sentences and everyday words. Avoid statistical or technical phrasing.

Hard rules:
- Every figure you state must already appear in the findings. Do not introduce, recalculate, re-round, combine, or estimate any number that is not in the findings.
- Add nothing beyond the findings: no extra facts, no explanation of why waits vary, no reassurance, and no advice about what the person should do or who they should contact. State only what the findings say.
- Do not add evaluative or intensifying words that are not in the findings — for example "significantly", "dramatically", "sharply", "steadily", "worryingly", "thankfully".
- Do not frame the figures as good or bad news (no "the good news is", "unfortunately", "sadly"). State them plainly and let them speak.
- Refer to the England comparison as the findings phrase it (for example "England's 71.4%", or "the England-wide figure of 71.4%"). Do not describe it as an "average".
- State the data month.
- Do NOT write a source or citation line yourself — it is added automatically after your answer.
- If the question asks how long an individual will wait, or uses "I" or "my", open by saying plainly that no one can predict an individual's wait, then give the trust's record as the useful answer.
- Plain prose only: no markdown, headings, bullets, or lists.

You are the voice that makes the findings readable. You are not the source of any fact."""


def build_messages(f: Findings, question: str) -> list[dict]:
    """I assemble the messages for the model. The system prompt is the contract; the user
    message carries the person's question and the brief. (For the Anthropic API the system
    text is passed as the top-level `system` parameter, not as a message — I keep it here so
    the whole contract lives in one place.)"""
    user = f"QUESTION: {question}\n\nFINDINGS:\n{findings_to_brief(f)}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


# ── The deterministic edge cases (no AI involved) ──────────────────────────

def not_found_message(query: str) -> str:
    """When resolution finds no trust, I answer in code — there is nothing for the AI to say."""
    return (f"I couldn't find an NHS trust matching \"{query}\". Try the trust's full name, "
            f"or its organisation code (for example, RXW for Shrewsbury and Telford).")


def ambiguous_message(query: str, candidates: list[dict]) -> str:
    """When several trusts match, I list them and ask — I never let the AI pick one."""
    lines = [f"Several trusts match \"{query}\":"]
    for c in candidates:
        lines.append(f"  - {present_name(c['org_name'])} ({c['org_code']})")
    lines.append("Which did you mean?")
    return "\n".join(lines)
