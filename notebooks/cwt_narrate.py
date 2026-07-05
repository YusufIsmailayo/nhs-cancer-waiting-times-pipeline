"""
cwt_narrate.py — the one place my agent talks to the model, and the only place it touches the
network or needs an API key.

I keep this deliberately separate from cwt_answer.py. The findings builder there must stay
testable with nothing but pandas — no SDK, no key — because my eval set leans on it. So the
single networked call lives alone, here.

The model's job is the easiest thing it does: take finished, pre-checked facts and write them
up in three or four sentences. No arithmetic, nothing to decide. That is why I run the
smallest, fastest tier — Claude Haiku. Paying for a larger model to phrase a sentence would
be waste, and on a public endpoint cheap-per-answer and low latency both matter.

I never put the key in code. The SDK reads ANTHROPIC_API_KEY from the environment.

Yusuf Ismail | NHS Data Engineering Portfolio | Project 4
"""
from __future__ import annotations

import re

from anthropic import Anthropic

import cwt_answer as ans

# Right-sized for the task: assemble pre-decided facts into a short answer.
MODEL = "claude-haiku-4-5-20251001"


def narrate(findings: ans.Findings, question: str, client: Anthropic | None = None) -> str:
    """I hand the brief to the model and return its prose.

    Every figure is already fixed in the findings; the system prompt forbids the model from
    introducing any other number. So this call adds language, never facts. It is the only
    network call in the whole agent."""
    client = client or Anthropic()  # picks up ANTHROPIC_API_KEY from the environment

    # The system prompt is the contract (passed as the API's top-level `system`); the user
    # message carries the person's question and the brief of finished findings.
    user = f"QUESTION: {question}\n\nFINDINGS:\n{ans.findings_to_brief(findings)}"

    resp = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=ans.SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
    )

    body = "".join(block.text for block in resp.content if block.type == "text").strip()

    # I guarantee the citation in code rather than trust the model, which dropped it on one
    # answer in testing. I strip any source line the model may have written, then stamp the
    # canonical one. The model owns the words; my code always owns the source.
    body = re.sub(r"\n+\s*source[:.].*$", "", body, flags=re.IGNORECASE | re.DOTALL).strip()
    return f"{body}\n\nSource: {findings.provenance}."
