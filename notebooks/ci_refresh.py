"""
ci_refresh.py — my monthly routine (batch -> eval -> regenerate failures -> eval again),
run unattended by GitHub Actions instead of by me typing it into a notebook cell.

This is a thin wrapper. It calls nothing but my own existing functions, in the same order
cwt_eval.py's docstring already documents as my routine:

    batch -> eval -> regenerate failures -> eval again -> deploy.

cwt_eval.py's own eval message says to keep re-running eval "until it reports 0" — that's a
loop, not a single retry. The first version of this script only gave it one regeneration
attempt before giving up, which is stricter than my actual manual routine: Haiku is an
independent roll each time it narrates, so one retry doesn't guarantee the same trust lands
clean. I now allow a few regenerate -> eval cycles before I refuse to commit.

If it still finds problems after MAX_ATTEMPTS, I refuse to let CI commit anything. A failed
workflow run is a safe outcome; a bad answer reaching the public app is not.

Needs ANTHROPIC_API_KEY in the environment (cwt_batch -> cwt_narrate reads it).
Run from the notebooks/ directory: python ci_refresh.py

Yusuf Ismail | NHS Data Engineering Portfolio | Project 4
"""
from __future__ import annotations

import sys

import cwt_batch
import cwt_eval

# One regeneration cycle is often enough, but not always — Haiku can land on the same
# problem twice in a row. I cap the retries rather than loop forever.
MAX_ATTEMPTS = 4

print("=== Step 1: batch-generating all answers ===")
cwt_batch.generate_all()

print("\n=== Step 2: eval pass 1 ===")
failures = cwt_eval.run_eval()

attempt = 1
while failures and attempt < MAX_ATTEMPTS:
    attempt += 1
    codes = sorted(failures)
    print(f"\n=== Step 3: regenerating {len(codes)} failing trust(s) (attempt {attempt}) ===")
    cwt_batch.regenerate(codes)

    print(f"\n=== Step 4: eval pass {attempt} ===")
    failures = cwt_eval.run_eval()

if failures:
    print(f"\n{len(failures)} trust(s) still failing after {attempt} attempts — I'm stopping "
          f"here. Nothing will be committed.")
    sys.exit(1)

print(f"\nAll answers clean after {attempt} attempt(s) — ready to commit.")
