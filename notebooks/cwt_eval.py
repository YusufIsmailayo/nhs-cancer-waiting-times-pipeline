"""
cwt_eval.py — the quality gate my answers pass before anything goes public.

The model writes 346 answers a month (173 trusts x 2). No human proofreads that reliably, and my
own batch proved it: a handful of answers contradicted themselves ("two in three people (100%)"),
used banned framing ("the good news is"), or gave advice ("contact the trust directly"). This
script checks every answer, every month, in seconds — figures against my Gold table, wording
against my rules — and lists exactly which trusts to regenerate.

My monthly routine is: batch -> eval -> regenerate failures -> eval again -> deploy.

Checks per answer:
  1. FIGURE     — the trust's latest compliance rate (from the Gold table) appears in the text.
  2. FRACTION   — any plain fraction phrase used matches the rate (no "two in three (100%)").
  3. SOURCE     — the code-stamped "Source:" line is present, with the trust's own data month.
  4. BANNED     — no evaluative/framing words the prompt forbids (steadily, good news, ...).
  5. ADVICE     — no advice or signposting ("contact the trust", "your clinical team", ...).
  6. MEASURE    — no "GP" narrowing and no converting 62 days into months.
  7. ENGLAND    — the England figure is never called an "average".
  8. TIME        — no relative-age phrasing ("a year earlier"); the findings NAME the month.

Pandas-only; no API key needed. Run:  python cwt_eval.py

Yusuf Ismail | NHS Data Engineering Portfolio | Project 4
"""
from __future__ import annotations

import json
import re
import sys

import pandas as pd

import cwt_query as q
from cwt_answer import _pct, _FRACTIONS  # I reuse the exact formatting/fraction rules.

# Words and framings my prompt forbids. If the model uses one, the answer regenerates.
BANNED = [
    "good news", "bad news", "unfortunately", "sadly", "worryingly", "thankfully",
    "encouragingly", "significantly", "dramatically", "sharply", "steadily", "markedly",
    "notably", "strong result", "impressive", "concerning", "good sign", "good thing",
]

# Advice/signposting the answers must never give.
ADVICE = [
    "contact the trust", "speak to your", "your clinical team", "your doctor", "your gp",
    "you may want to", "you should", "ask your",
]

# Relative-age phrasing the answers must never use. The findings always NAME the month
# (e.g. "up from 56.4% in October 2023"), so any "a year earlier" / "two years ago" is the model
# working out — and possibly mis-stating — a relative age. This is the check that would have
# caught "improved from 56.4% a year earlier" when the anchor month is October 2023 (~two years).
# It deliberately does NOT match a plain span like "in the 24 months" (no earlier/ago after it).
_REL_TIME = re.compile(
    r"\b(?:a|an|one|two|three|four|\d+)\s+(?:year|years|month|months|decade|decades)\s+"
    r"(?:earlier|ago|before|prior)\b"
    r"|\blast\s+year\b|\bthe\s+(?:previous|prior)\s+year\b|\bthe\s+year\s+before\b"
    r"|\byear[-\s]on[-\s]year\b",
    re.IGNORECASE,
)

# The fraction phrases the findings layer can emit, with the rate each one anchors.
_FRACTION_RATE = {phrase: rate for rate, phrase in _FRACTIONS}
# Sorted longest-first so "two in three" is found before any shorter overlap.
_FRACTION_PHRASES = sorted(_FRACTION_RATE, key=len, reverse=True)

# The model also paraphrases fractions in spoken form ("two in three", "nine in ten"), so I
# parse those generically: N in M -> N/M.
_WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_N_IN_M = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+in\s+"
                     r"(two|three|four|five|six|seven|eight|nine|ten|\d+)\b")


def _num(tok: str) -> int:
    return _WORD_NUM.get(tok) or int(tok)


def _stated_fraction(low: str) -> float | None:
    """I find the first plain fraction the answer states, as a rate — from either a named
    phrase ('two-thirds') or a spoken 'N in M' form ('two in three') — or None if absent."""
    named_pos, named_rate = len(low) + 1, None
    for phrase in _FRACTION_PHRASES:
        p = low.find(phrase)
        if p != -1 and p < named_pos:
            named_pos, named_rate = p, _FRACTION_RATE[phrase]
    m = _N_IN_M.search(low)
    if m and m.start() < named_pos:
        n, d = _num(m.group(1)), _num(m.group(2))
        return n / d if d else None
    return named_rate

FRACTION_TOLERANCE = 0.09  # a phrase may sit up to ~9pp from its anchor before it's misleading


def check_answer(text: str, kind: str, code: str, latest_rate: float, month_label: str,
                 org_name: str = "") -> list[str]:
    """I return a list of problems with one answer (empty list = clean)."""
    problems = []
    low = text.lower()

    # 1. The trust's actual latest figure must appear. At the extremes, the plain-English word
    #    forms are legitimate statements of the figure: "none of the patients" IS 0%, and
    #    "all of their patients" IS 100% — I accept those alongside the literal percentage.
    stated = _pct(latest_rate) in text
    if not stated and latest_rate <= 0.005:
        stated = bool(re.search(r"\b(none|no)\b.{0,40}patients|\bno patients\b", low))
    if not stated and latest_rate >= 0.995:
        stated = bool(re.search(r"\ball\b.{0,30}patients|\bevery patient", low))
    if not stated:
        problems.append(f"{kind}: latest figure {_pct(latest_rate)} not stated")

    # 2. Any fraction phrase used must match the rate — named ("two-thirds") or spoken
    #    ("two in three") form.
    stated = _stated_fraction(low)
    if stated is not None and abs(stated - latest_rate) > FRACTION_TOLERANCE:
        problems.append(
            f"{kind}: states a fraction near {stated:.0%} but the rate is {_pct(latest_rate)}")

    # 3. The code-stamped source line, carrying the trust's own data month.
    if "source: nhs england cancer waiting times" not in low:
        problems.append(f"{kind}: source line missing")
    elif month_label.lower() not in low:
        problems.append(f"{kind}: data month '{month_label}' not stated")

    # 4. Banned evaluative/framing words.
    for w in BANNED:
        if w in low:
            problems.append(f"{kind}: banned word '{w}'")

    # 5. Advice/signposting.
    for w in ADVICE:
        if w in low:
            problems.append(f"{kind}: gives advice ('{w}')")

    # 6. Measure accuracy: no GP narrowing, no unit conversion of the 62 days. I mask the
    #    trust's own name first — 'Gp Care Uk Limited' must not fail for being called by name.
    name_masked = low.replace(org_name.lower(), " ") if org_name else low
    if re.search(r"\bgp\b", name_masked):
        problems.append(f"{kind}: narrows the measure to GP referrals")
    if re.search(r"(two|2)\s+months", low):
        problems.append(f"{kind}: converts 62 days into months")

    # 7. England is a national aggregate, not an average.
    if re.search(r"england.{0,10}average|average.{0,15}england", low):
        problems.append(f"{kind}: calls the England figure an 'average'")

    # 8. Relative-age phrasing. The findings always NAME the month; a phrase like "a year
    #    earlier" is the model computing a relative age, which can contradict the real gap.
    m = _REL_TIME.search(low)
    if m:
        problems.append(f"{kind}: uses relative time '{m.group(0)}' — findings name the month")

    return problems


def run_eval(parquet_path=None, answers_path=None) -> dict:
    """I check every trust's answers against the table and the rules, and report."""
    import cwt_utils as cwt  # imported here so the checks above are testable without it
    parquet_path = parquet_path or (cwt.GOLD_DIR / "gold_62d_trust_month.parquet")
    answers_path = answers_path or (cwt.GOLD_DIR / "answers_62d.json")

    df = q.load_gold_table(parquet_path)
    answers = json.loads(open(answers_path).read())

    failures: dict[str, list[str]] = {}
    for code, rec in answers["trusts"].items():
        res = q.get_trust_performance(df, code)
        rate = res.latest.compliance_rate
        month_label = pd.Timestamp(res.latest.period_month + "-01").strftime("%B %Y")

        problems = (check_answer(rec["general"], "general", code, rate, month_label,
                                 org_name=rec["org_name"])
                    + check_answer(rec["personal"], "personal", code, rate, month_label,
                                   org_name=rec["org_name"]))
        if problems:
            failures[code] = problems

    total = len(answers["trusts"])
    print(f"Checked {total} trusts ({total * 2} answers).")
    print(f"Clean: {total - len(failures)}  |  Need regenerating: {len(failures)}\n")
    for code, probs in sorted(failures.items()):
        name = answers["trusts"][code]["org_name"]
        print(f"  {code}  {name}")
        for p in probs:
            print(f"      - {p}")

    if failures:
        codes = sorted(failures)
        print(f"\nRegenerate just these {len(codes)} trusts (pennies, not a full batch):")
        print(f"  import cwt_batch; cwt_batch.regenerate({codes})")
        print("Then run this eval again until it reports 0.")
    else:
        print("All answers clean — ready to deploy.")
    return failures


if __name__ == "__main__":
    fails = run_eval()
    sys.exit(1 if fails else 0)
