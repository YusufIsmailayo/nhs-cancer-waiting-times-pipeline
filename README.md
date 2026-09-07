# NHS Cancer Waiting Times Pipeline

A production-style data pipeline processing **NHS England Cancer Waiting Times** data across **181 provider trusts**, **three cancer standards**, and **24 months** of activity — built on a Bronze → Silver → Gold medallion architecture, with a public question-answering agent on top.

Covers **1,076,000+ raw records**, narrowed to **460,000+ analysis-ready rows** spanning October 2023 to September 2025, the post-framework period where the cancer standards are directly comparable.

**[Try the live app](https://nhs-cancer-waiting-times-pipeline-odkmcjhlgafcqtmo62ntmz.streamlit.app)** — ask how any English NHS trust is doing on 62-day cancer waits, in plain English.

---

## The Problem

The NHS sets time standards for cancer treatment. The headline is the 62-day standard: from an urgent referral to the start of first treatment, no more than 62 days should pass, with 85% of patients treated inside that window. It has not been met nationally for years.

But the national average hides far more than it reveals. This pipeline ingests the raw monthly data NHS England publishes, cleans and conforms it through a medallion architecture, and surfaces what the single national number obscures: the variation between trusts, between cancer types, and between referral routes.

---

## Key Findings

| Metric | Value |
|--------|-------|
| Raw records ingested | 1,076,865 |
| Analysis-ready rows (provider, Oct 2023–Sep 2025) | 460,238 |
| Provider trusts | 181 (137 reporting in all 24 months) |
| Trusts in the compliance ranking | 124 (≥500 patients over 24 months) |
| Months covered | 24 |
| National 62-day average (urgent route) | 62.2% |
| National 62-day average (all routes) | 67.8% |
| Months hitting the 85% standard | 0 of 24 |
| Months hitting the 70% interim target | 0 of 24 (urgent route) |
| Patients who breached 62 days (urgent route) | 148,987 |
| Best vs worst trust (the lottery) | 87.1% vs 38.8% — a 48.3-point gap |
| Fastest vs slowest referral route | Consultant Upgrade 78.7% vs Urgent Suspected Cancer 62.2% |
| Best vs worst cancer type (all routes) | Skin 84.8% vs Head & Neck 55.4% — a 29.4-point gap |
| Patients waiting more than 104 days | 61,934 |

> **Note:** `gold_62d_by_cancer_type.csv` and `gold_62d_severity_by_type.csv` currently return the same figures as the 18-month run, and their patient totals do not reconcile to either the urgent-route or all-routes 24-month totals. Notebook 04 needs re-running and its scoping checking before these two rows are filled in.

---

## The Series

This pipeline produced a written series, each piece built on a different Gold cut:

1. **[The Cancer Standard Nobody Is Hitting — And the Hospital Lottery Behind It](https://medium.com/@yusufismail_91982/the-cancer-standard-nobody-is-hitting-and-the-hospital-lottery-behind-it-e075df3ad626)** — your chance of timely treatment depends on which trust your referral lands in.
2. **[It Depends What Kind of Cancer You Have](https://medium.com/@yusufismail_91982/it-dependswhat-kind-of-cancer-you-have-03a2c8b97fd5)** — it also depends on what kind of cancer you have, and for some, "late" means catastrophically late.
3. **[The Cancer Route Built for Urgency Is the Slowest One](https://medium.com/@yusufismail_91982/the-cancer-route-built-for-urgency-is-the-slowest-one-4ec929091da4)** — it depends on how you were referred; the route built for urgency is the slowest of all.
4. **[Every Number Has a Denominator](https://medium.com/@yusufismail_91982/every-number-has-a-denominator-97b4906eef41)** — the engineering companion: how this pipeline is built to survive being challenged.

Written up separately: **[I Built an AI Agent for NHS Cancer Waits. Its Best Feature Is the Question It Won't Answer](https://medium.com/towards-artificial-intelligence/i-built-an-ai-agent-for-nhs-cancer-waits-its-best-feature-is-the-question-it-wont-answer-99ab8127e6a2)**

---

## Architecture

```
Raw CSVs (NHS England, 4 financial years)
        │
        ▼
   BRONZE  ── faithful Parquet copies + audit columns (source file, ingest time, FY)
        │      no cleaning; nulls preserved; fully traceable
        ▼
   SILVER  ── combined, filtered to Provider + post-Oct-2023
        │      casing normalised, compliance recalculated from source counts
        │      split into clean per-standard files + parallel waiting-time band files
        ▼
    GOLD   ── analytical tables, one cut per article, plus one for the agent:
               trust ranking · cancer-type divide · referral-route gap · trust × month
        │
        ▼
   AGENT   ── answers precomputed monthly, checked, then served as static lookup
```

---

## Structure

```
data/raw/        : original NHS England CSVs (not committed)
data/bronze/     : ingested raw copies, one Parquet per financial year
data/silver/     : cleaned per-standard tables + parallel waiting-time band files
data/gold/       : analytics-ready output tables + published agent answers
notebooks/       : the full pipeline, run in order (00–06), plus the agent modules
outputs/         : chart-ready CSVs and publication charts (PNG)
app.py           : Streamlit front end
cwt_utils.py     : shared helpers (loading, common filters, chart styling)
```

---

## Notebooks

| Notebook | Layer | Purpose |
|----------|-------|---------|
| `00_data_exploration.ipynb` | — | Document the raw structure before building; catch data traps |
| `01_bronze_ingestion.ipynb` | Bronze | Ingest 4 raw CSVs to audited Parquet, verify round-trip |
| `02_silver_transformation.ipynb` | Silver | Combine, filter, clean, split into per-standard files |
| `03_gold_trust_lottery.ipynb` | Gold | Trust-level 62-day ranking (Article 1) |
| `04_gold_cancer_type.ipynb` | Gold | Compliance and severity by cancer type (Article 2) |
| `05_gold_routes.ipynb` | Gold | 62-day compliance by referral route (Article 3) |
| `06_gold_trust_month.ipynb` | Gold | Trust × month × combined 62-day standard — the table the agent reads |

---

## The live app

The three article notebooks each collapse the data one way, and none of them can answer "how is my hospital doing this month". Notebook 06 builds the cut that can: one row per trust per month, on the combined 62-day standard rather than the urgent route alone, because that is what a member of the public means when they ask about cancer waits.

The app is deliberately boring at runtime. It makes no API calls, holds no key, and computes nothing.

```
06_gold_trust_month.ipynb  ->  gold_62d_trust_month.parquet   (the numbers)
cwt_query.py               ->  reads that table, resolves a trust name
cwt_answer.py              ->  turns figures into finished FINDINGS
cwt_narrate.py             ->  the only networked call: Claude Haiku phrases them
cwt_batch.py               ->  monthly, writes all answers to answers_62d.json
cwt_eval.py                ->  checks every answer before it ships
cwt_serve.py + app.py      ->  the public app: lookup only, no AI, no key
```

| Module | Role |
|--------|------|
| `cwt_query.py` | The only path from the agent to the Gold table. Defines one frozen result shape and resolves a typed name to a trust deterministically. Computes no figures. |
| `cwt_answer.py` | Decides every number, comparison, rounding and verdict in code, and emits finished statements. |
| `cwt_narrate.py` | The single call to the model. Claude Haiku assembles pre-checked facts into prose and is forbidden from introducing any number. |
| `cwt_batch.py` | Run monthly after new NHS data. 181 trusts × 2 questions, a few pennies of Haiku. |
| `cwt_eval.py` | Eight automated checks per answer — figure present, fractions consistent, source line stamped, no banned framing, no advice, no unit drift, England never called an "average", no relative-age phrasing. Pandas only, no key. |
| `cwt_serve.py` | Pure lookup and name resolution. Sentence-tolerant, deterministic, returns every match rather than guessing one. |
| `app.py` | Thin Streamlit shell over `cwt_serve`. |

### The boundary that matters

The model is the voice, never the source. Every figure in every published answer is computed by my code, from the Gold table, before the model sees it. The model receives finished phrases and writes them up in three or four sentences. There is no arithmetic for it to get wrong because there is no arithmetic left to do.

That boundary is enforced rather than trusted. `cwt_eval.py` re-checks all 362 answers against the Gold table each month and names the trusts to regenerate. It exists because the first batch produced answers that contradicted themselves — "two in three people (100%)" — and no one proofreads 362 answers reliably.

Monthly routine: re-run the pipeline → `cwt_batch.py` → `cwt_eval.py` → regenerate failures → `cwt_eval.py` again → deploy.

---

## Quickstart

1. Download the Monthly Combined CSVs from NHS England (see Data Source) into `data/raw/`
2. Run the notebooks in order, 00 through 06
3. Gold tables land in `data/gold/`, charts and chart-ready CSVs in `outputs/`

---

## Principles

- Raw data is never modified — Bronze is a faithful copy
- Nulls stay null — NHS suppresses small numbers; they are never coerced to zero
- Compliance is recalculated from source counts, not taken on trust
- Dates are parsed to real datetimes before filtering — source files mix ISO and UK formats
- The Silver split is provably lossless — the band files rejoin headline data one-to-one
- The agent's Gold table asserts its grain rather than assuming it
- Analysis is scoped to October 2023 onwards, where the standards are comparable
- Every layer has clear rules and is reproducible end to end

---

## Data Source

**NHS England — Cancer Waiting Times Statistics**
Published monthly at: https://www.england.nhs.uk/statistics/statistical-work-areas/cancer-waiting-times/

This pipeline uses the Monthly Combined Provider and Commissioner CSV files for 2022-23, 2023-24, 2024-25 and 2025-26 (Apr–Sep). Analysis is filtered to provider-level data from October 2023 onwards, reflecting the cancer standards framework introduced that month.

---

## Tech Stack

- **Python** — pandas, numpy, pathlib
- **Storage** — Parquet (Bronze/Silver/Gold), CSV (analysis outputs), JSON (published answers)
- **Visualisation** — matplotlib
- **App** — Streamlit
- **Model** — Claude Haiku, batch only, never at request time
- **Architecture** — Medallion (Bronze → Silver → Gold)
- **Environment** — Anaconda, JupyterLab

---

## Related Work

- **Project 1:** [NHS Outpatient Attendance Pipeline — 226 million records](https://github.com/YusufIsmailayo/nhs-patient-flow-data-pipeline)
- **Project 2:** [NHS RTT Incomplete Pathways Pipeline — 14 million pathways](https://github.com/YusufIsmailayo/nhs-rtt-incomplete-pathways-pipeline)
- **Project 3:** [NHS A&E Waiting Times Pipeline](https://github.com/YusufIsmailayo/nhs-ae-waiting-times)

---

*Built by [Yusuf Ismail](https://github.com/YusufIsmailayo) — Data Engineer focused on NHS pipelines and public sector analytics.*
