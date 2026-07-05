"""
cwt_batch.py — the monthly batch step that writes every trust's answers in one go.

This is the ONLY part of the live system that calls Claude or needs an API key, and I run it on
my own machine. The data changes once a month, so the full set of answers is small and stable
for the whole month: I generate them all here, save them to a file, and the public app just
looks them up. The deployed app makes no API calls and holds no key.

I run this whenever NHS England publishes new data, after re-running the pipeline to refresh
gold_62d_trust_month.parquet. Cost: ~173 trusts x 2 short Haiku answers = a few pennies, once a
month.

Needs ANTHROPIC_API_KEY in the environment (cwt_narrate reads it).

Yusuf Ismail | NHS Data Engineering Portfolio | Project 4
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import cwt_utils as cwt
import cwt_query as q
import cwt_answer as a
import cwt_narrate as n

# The two fixed questions I precompute per trust. The app maps a visitor's real question to one
# of these. The personal one uses "I" so the model opens with the "no one can predict your wait"
# reframe; the general one carries the always-on honesty note anyway.
GENERAL_Q  = "How is this trust performing against the 62-day cancer standard?"
PERSONAL_Q = "How long will I personally wait for cancer treatment here?"


def generate_all(parquet_path=None, out_path=None) -> dict:
    """I generate both answers for every real trust and write them to one JSON file."""
    parquet_path = parquet_path or (cwt.GOLD_DIR / "gold_62d_trust_month.parquet")
    out_path     = out_path or (cwt.GOLD_DIR / "answers_62d.json")

    df = q.load_gold_table(parquet_path)

    # Every real trust — the England 'Total' row is the national figure, not a trust.
    codes = sorted(c for c in df["org_code"].unique() if c != "Total")
    data_month = df["period_month"].max()

    trusts = {}
    for i, code in enumerate(codes, start=1):
        try:
            res = q.get_trust_performance(df, code)
            f   = a.build_findings(res)
            trusts[code] = {
                "org_name": f.subject,
                "general":  n.narrate(f, GENERAL_Q),
                "personal": n.narrate(f, PERSONAL_Q),
            }
            print(f"[{i}/{len(codes)}] {code}  {f.subject}")
        except Exception as e:
            # I never let one trust's failure abandon the whole batch — I note it and carry on.
            print(f"[{i}/{len(codes)}] {code}  SKIPPED: {e}")

    out = {
        "data_month": data_month,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_url": q.SOURCE_URL,
        "trusts": trusts,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    print(f"\nWrote {len(trusts)} of {len(codes)} trusts to {out_path}")
    return out


def regenerate(codes: list[str], parquet_path=None, answers_path=None) -> None:
    """I regenerate the answers for just the listed trusts (the ones my eval failed) and update
    the existing answers file in place — pennies, instead of re-running the whole batch."""
    parquet_path = parquet_path or (cwt.GOLD_DIR / "gold_62d_trust_month.parquet")
    answers_path = answers_path or (cwt.GOLD_DIR / "answers_62d.json")

    df = q.load_gold_table(parquet_path)
    with open(answers_path) as fh:
        out = json.load(fh)

    for i, code in enumerate(codes, start=1):
        res = q.get_trust_performance(df, code)
        f   = a.build_findings(res)
        out["trusts"][code] = {
            "org_name": f.subject,
            "general":  n.narrate(f, GENERAL_Q),
            "personal": n.narrate(f, PERSONAL_Q),
        }
        print(f"[{i}/{len(codes)}] regenerated {code}  {f.subject}")

    out["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(answers_path, "w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    print(f"\nUpdated {len(codes)} trusts in {answers_path}")


if __name__ == "__main__":
    generate_all()
