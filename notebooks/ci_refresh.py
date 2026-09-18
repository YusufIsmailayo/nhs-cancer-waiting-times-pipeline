"""
ci_refresh.py — my monthly routine (batch -> eval -> regenerate failures -> eval again),
run unattended by GitHub Actions instead of by me typing it into a notebook cell.

This is a thin wrapper. It calls nothing but my own existing functions, in the same order
cwt_eval.py's docstring already documents as my routine:

    batch -> eval -> regenerate failures -> eval again -> deploy.

If a second eval still finds problems, I refuse to let CI commit anything. A failed workflow
run is a safe outcome; a bad answer reaching the public app is not.

Needs ANTHROPIC_API_KEY in the environment (cwt_batch -> cwt_narrate reads it).
Run from the notebooks/ directory: python ci_refresh.py

Yusuf Ismail | NHS Data Engineering Portfolio | Project 4
"""
from __future__ import annotations

import sys

import cwt_batch
import cwt_eval

print("=== Step 1: batch-generating all answers ===")
cwt_batch.generate_all()

print("\n=== Step 2: first eval pass ===")
failures = cwt_eval.run_eval()

if failures:
    codes = sorted(failures)
    print(f"\n=== Step 3: regenerating {len(codes)} failing trust(s) ===")
    cwt_batch.regenerate(codes)

    print("\n=== Step 4: second eval pass ===")
    failures = cwt_eval.run_eval()

if failures:
    print(f"\n{len(failures)} trust(s) still failing after regeneration — I'm stopping here. "
          f"Nothing will be committed.")
    sys.exit(1)

print("\nAll answers clean — ready to commit.")
