"""
app.py — the public Streamlit app.

It holds NO API key and makes NO model calls. Every answer was written by Claude in the monthly
batch step (cwt_batch.py) and saved to a file; this app just resolves the trust the visitor asked
about and shows the matching precomputed answer. That is why it is free to run, instant, and safe
to expose publicly.

Run locally:   streamlit run app.py

Yusuf Ismail | NHS Data Engineering Portfolio | Project 4
"""
from __future__ import annotations

import json
import re
import sys
import pathlib
from datetime import datetime

import streamlit as st

# set_page_config must be the FIRST Streamlit command in the script — even a cached loader
# counts as one — so it lives here, directly after the import.
st.set_page_config(page_title="NHS Cancer Waiting Times", page_icon="🩺")

# My python modules live in notebooks/; I add that folder to the path so the app reuses the exact
# same resolving logic instead of duplicating it. (These modules are pandas-only, so they deploy
# fine on Streamlit Cloud.)
HERE = pathlib.Path(__file__).parent
sys.path.append(str(HERE / "notebooks"))
import cwt_query as q          # noqa: E402
import cwt_serve as serve      # noqa: E402

DATA = HERE / "data" / "gold"
GITHUB_URL = "https://github.com/YusufIsmailayo/nhs-cancer-waiting-times-pipeline"
LOW_VOLUME = 25   # below this many patients in a month, the percentage is noisy — I flag it.

EXAMPLES = [
    "How is Shrewsbury and Telford doing?",
    "How long will I wait at Leeds?",
    "How is Liverpool doing?",
]


@st.cache_data
def load():
    """I load the trust table (for resolving names) and the precomputed answers, just once."""
    df = q.load_gold_table(DATA / "gold_62d_trust_month.parquet")
    answers = json.loads((DATA / "answers_62d.json").read_text())
    return df, answers


df, answers = load()
data_month = answers.get("data_month", "")
source_url = answers.get("source_url", "")


def _strip_source(text: str) -> str:
    """I remove the stamped 'Source:' line from the answer for display — the app shows its own
    single source caption. The line stays in the saved answer so a copied answer keeps its
    citation; I just don't show it three times on one screen."""
    return re.sub(r"\n+\s*source:.*$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()


def latest_row(code: str):
    rows = df[df["org_code"] == code].sort_values("period_date")
    return None if rows.empty else rows.iloc[-1]


def trust_month_label(code: str) -> str:
    """The trust's OWN latest reported month, in words — e.g. 'October 2024'. This is the honest
    date for the source line, since some trusts stopped reporting before the dataset's latest month."""
    row = latest_row(code)
    if row is None:
        return data_month
    return datetime.strptime(str(row["period_month"]), "%Y-%m").strftime("%B %Y")


def show_answer(code: str, personal: bool) -> None:
    """I show one trust's precomputed answer, with volume context and the other angle a click away."""
    rec = answers["trusts"].get(code)
    if not rec:
        st.warning("I don't have an answer for that trust this month.")
        return
    st.subheader(rec["org_name"])
    st.write(_strip_source(rec["personal"] if personal else rec["general"]))

    # Volume context — how many patients the percentage is based on, read straight from the Gold
    # table (not the AI), with a caution for small numbers.
    row = latest_row(code)
    if row is not None:
        n = round(float(row["total_patients"]))
        if n == 0:
            st.caption("No patients were recorded at this trust for this measure that month.")
        else:
            st.caption(f"Based on {n:,} patients treated that month.")
            if n < LOW_VOLUME:
                st.warning("These are small patient numbers, so a single case can move the "
                           "percentage a lot — read it with caution.")

    other = "What about my own wait?" if not personal else "How is the trust performing overall?"
    with st.expander(other):
        st.write(_strip_source(rec["general"] if personal else rec["personal"]))

    # ONE source line per answer, carrying THIS trust's data month.
    st.caption(f"[Source: NHS England Cancer Waiting Times]({source_url}) "
               f"· data to {trust_month_label(code)}")


st.title("How is my hospital doing on cancer waits?")
st.caption(f"England NHS trusts · latest data {data_month}")
st.write(
    "The NHS aims for 85% of people to start cancer treatment within **62 days of an urgent "
    "referral**. This tool shows how any English NHS trust is doing against that standard — "
    "in plain English, from official NHS England figures."
)
st.caption("Official statistics about trusts, not personal medical advice.")

# Example questions — one tap fills the box, so nobody faces an empty field.
cols = st.columns(len(EXAMPLES))
for col, ex in zip(cols, EXAMPLES):
    if col.button(ex, use_container_width=True):
        st.session_state["question"] = ex

question = st.text_input("Your question", key="question",
                         placeholder="how is Shrewsbury doing?")

if question:
    personal = serve.looks_personal(question)
    hits = serve.resolve_from_question(df, question)

    if len(hits) == 1:
        show_answer(hits[0]["org_code"], personal)

    elif len(hits) > 1:
        st.info(f"More than one NHS trust matches your question — {len(hits)} possibilities. "
                f"Which did you mean?")
        names = {answers["trusts"].get(h["org_code"], {}).get("org_name", h["org_name"]):
                 h["org_code"] for h in hits}
        choice = st.radio("Trust", list(names), index=None)
        if choice:
            show_answer(names[choice], personal)

    else:
        st.info(
            "I couldn't match that to an English NHS trust. Two things that usually help:\n\n"
            "- This tool covers **England only** — Wales, Scotland and Northern Ireland publish "
            "their cancer figures separately, so a town outside England won't appear here.\n"
            "- Try a **hospital or trust name** (for example \"Leeds\" or \"Shrewsbury and "
            "Telford\") rather than just a town — or pick one from the full list below."
        )
        all_names = {rec["org_name"]: code
                     for code, rec in sorted(answers["trusts"].items(),
                                             key=lambda kv: kv[1]["org_name"])}
        choice = st.selectbox("Choose a trust", [""] + list(all_names))
        if choice:
            show_answer(all_names[choice], personal)

with st.expander("About this tool"):
    st.write(
        "These figures are official NHS England statistics for the combined 62-day cancer "
        "standard, covering England's NHS trusts. Every month the answers are generated from "
        "validated trust-level data and automatically checked against the source figures before "
        "publication — so the numbers you read always reconcile with the official data.\n\n"
        "The tool reports how a trust performed; it cannot predict how long any individual will "
        "wait, because the data does not measure that. Each answer is written by an AI model from "
        "figures computed in advance — the AI never invents or changes a number."
    )

st.link_button("View the project on GitHub", GITHUB_URL)
