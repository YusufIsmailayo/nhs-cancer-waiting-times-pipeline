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
import sys
import pathlib

import streamlit as st

st.set_page_config(page_title="NHS Cancer Waiting Times", page_icon="🩺")

# My python modules live in notebooks/; I add that folder to the path so the app reuses the exact
# same resolving logic instead of duplicating it. (These modules are pandas-only, so they deploy
# fine on Streamlit Cloud.)
HERE = pathlib.Path(__file__).parent
sys.path.append(str(HERE / "notebooks"))
import cwt_query as q          # noqa: E402
import cwt_serve as serve      # noqa: E402

DATA = HERE / "data" / "gold"


@st.cache_data
def load():
    """I load the trust table (for resolving names) and the precomputed answers, just once."""
    df = q.load_gold_table(DATA / "gold_62d_trust_month.parquet")
    answers = json.loads((DATA / "answers_62d.json").read_text())
    return df, answers


df, answers = load()
data_month = answers.get("data_month", "")
source_url = answers.get("source_url", "")


def show_answer(code: str, personal: bool) -> None:
    """I show one trust's precomputed answer, with the other angle a click away."""
    rec = answers["trusts"].get(code)
    if not rec:
        st.warning("I don't have an answer for that trust this month.")
        return
    st.subheader(rec["org_name"])
    st.write(rec["personal"] if personal else rec["general"])
    other = "What about my own wait?" if not personal else "How is the trust performing overall?"
    with st.expander(other):
        st.write(rec["general"] if personal else rec["personal"])
    st.caption(f"[Source: NHS England Cancer Waiting Times]({source_url}) · data to {data_month}")



st.title("How is my hospital doing on cancer waits?")
st.caption(f"England NHS trusts · the 62-day cancer treatment standard · data to {data_month}")
st.write(
    "Ask about an NHS trust — for example, *“how is Shrewsbury and Telford doing?”* "
    "or *“how long will I wait at Leeds?”*"
)

question = st.text_input("Your question", placeholder="how is Shrewsbury doing?")

if question:
    personal = serve.looks_personal(question)
    hits = serve.resolve_from_question(df, question)

    if len(hits) == 1:
        show_answer(hits[0]["org_code"], personal)

    elif len(hits) > 1:
        st.info("Several trusts match — which did you mean?")
        names = {answers["trusts"].get(h["org_code"], {}).get("org_name", h["org_name"]):
                 h["org_code"] for h in hits}
        choice = st.radio("Trust", list(names), index=None)
        if choice:
            show_answer(names[choice], personal)

    else:
        st.info("I couldn't find that trust from your question — pick one from the list:")
        all_names = {rec["org_name"]: code
                     for code, rec in sorted(answers["trusts"].items(),
                                             key=lambda kv: kv[1]["org_name"])}
        choice = st.selectbox("Choose a trust", [""] + list(all_names))
        if choice:
            show_answer(all_names[choice], personal)

with st.expander("About this tool"):
    st.write(
        "These figures are official NHS England statistics, refreshed monthly. The tool reports "
        "how a trust performed against the 62-day cancer standard — it cannot predict how long "
        "any individual will wait, because the data does not measure that. Each answer is written "
        "by an AI model from figures computed in advance; the AI never invents a number."
    )
