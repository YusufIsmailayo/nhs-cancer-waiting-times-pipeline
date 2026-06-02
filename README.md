# NHS Cancer Waiting Times Pipeline

A production-style data pipeline processing **NHS England Cancer Waiting Times** data across **172 provider trusts**, **three cancer standards**, and **18 months** of activity — built on a Bronze → Silver → Gold medallion architecture.

Covers **914,000+ raw records**, narrowed to **344,000+ analysis-ready rows** spanning October 2023 to March 2025, the post-framework period where the cancer standards are directly comparable.

---

## The Problem

The NHS sets time standards for cancer treatment. The headline is the 62-day standard: from an urgent referral to the start of first treatment, no more than 62 days should pass, with 85% of patients treated inside that window. It has not been met nationally for years.

But the national average hides far more than it reveals. This pipeline ingests the raw monthly data NHS England publishes, cleans and conforms it through a medallion architecture, and surfaces what the single national number obscures: the variation between trusts, between cancer types, and between referral routes.

---

## Key Findings

| Metric | Value |
|--------|-------|
| Raw records ingested | 914,430 |
| Analysis-ready rows (provider, Oct 2023–Mar 2025) | 344,880 |
| Provider trusts | 172 |
| Months covered | 18 |
| National 62-day average (urgent route) | 62.1% |
| Months hitting the 85% target | 0 of 18 |
| Months hitting the 70% interim target | 0 of 18 |
| Total patients who breached 62 days | 111,280 |
| Best vs worst trust (the lottery) | 87.3% vs 39.1% — a 48-point gap |
| Best vs worst cancer type | Skin 84.3% vs Gynaecological/Head & Neck 55.3% |
| Patients waiting more than 104 days | 46,690 |
| Fastest vs slowest referral route | Consultant Upgrade 78.2% vs Urgent Suspected Cancer 62.0% |

---

## The Series

This pipeline produced a three-part written series, each built on a different Gold cut:

1. **[The Cancer Standard Nobody Is Hitting — And the Hospital Lottery Behind It](https://medium.com/@yusufismail_91982/the-cancer-standard-nobody-is-hitting-and-the-hospital-lottery-behind-it-e075df3ad626)** — your chance of timely treatment depends on which trust your referral lands in.
2. **[It Depends What Kind of Cancer You Have](https://medium.com/@yusufismail_91982/it-dependswhat-kind-of-cancer-you-have-03a2c8b97fd5)** — it also depends on what kind of cancer you have, and for some, "late" means catastrophically late.
3. **[The Cancer Route Built for Urgency Is the Slowest One](https://medium.com/@yusufismail_91982/the-cancer-route-built-for-urgency-is-the-slowest-one-4ec929091da4)** — it depends on how you were referred; the route built for urgency is the slowest of all.
---

## Architecture

```
Raw CSVs (NHS England, 3 financial years)
        │
        ▼
   BRONZE  ── faithful Parquet copies + audit columns (source file, ingest time, FY)
        │      no cleaning; nulls preserved; fully traceable
        ▼
   SILVER  ── combined, filtered to Provider + post-Oct-2023
        │      casing normalised, compliance recalculated from source counts
        │      split into clean per-standard files + parallel waiting-time band files
        ▼
    GOLD   ── analytical tables, one cut per article:
               trust ranking · cancer-type divide · referral-route gap
```

---

## Structure

```
data/raw/        : original NHS England CSVs (not committed)
data/bronze/     : ingested raw copies, one Parquet per financial year
data/silver/     : cleaned per-standard tables + parallel waiting-time band files
data/gold/       : analytics-ready output tables
notebooks/       : the full pipeline, run in order (00–05)
outputs/         : chart-ready CSVs and publication charts (PNG)
cwt_utils.py     : shared helpers (loading, common filters, chart styling)
```

---

## Notebooks

| Notebook | Layer | Purpose |
|----------|-------|---------|
| `00_data_exploration.ipynb` | — | Document the raw structure before building; catch data traps |
| `01_bronze_ingestion.ipynb` | Bronze | Ingest 3 raw CSVs to audited Parquet, verify round-trip |
| `02_silver_transformation.ipynb` | Silver | Combine, filter, clean, split into per-standard files |
| `03_gold_trust_lottery.ipynb` | Gold | Trust-level 62-day ranking (Article 1) |
| `04_gold_cancer_type.ipynb` | Gold | Compliance and severity by cancer type (Article 2) |
| `05_gold_routes.ipynb` | Gold | 62-day compliance by referral route (Article 3) |

---

## Quickstart

1. Download the Monthly Combined CSVs from NHS England (see Data Source) into `data/raw/`
2. Run the notebooks in order, 00 through 05
3. Gold tables land in `data/gold/`, charts and chart-ready CSVs in `outputs/`

---

## Principles

- Raw data is never modified — Bronze is a faithful copy
- Nulls stay null — NHS suppresses small numbers; they are never coerced to zero
- Compliance is recalculated from source counts, not taken on trust
- The Silver split is provably lossless — the band files rejoin headline data one-to-one
- Analysis is scoped to October 2023 onwards, where the standards are comparable
- Every layer has clear rules and is reproducible end to end

---

## Data Source

**NHS England — Cancer Waiting Times Statistics**
Published monthly at: https://www.england.nhs.uk/statistics/statistical-work-areas/cancer-waiting-times/

This pipeline uses the Monthly Combined Provider and Commissioner CSV files for 2022-23, 2023-24, and 2024-25. Analysis is filtered to provider-level data from October 2023 onwards, reflecting the cancer standards framework introduced that month.

---

## Tech Stack

- **Python** — pandas, numpy, pathlib
- **Storage** — Parquet (Bronze/Silver/Gold), CSV (analysis outputs)
- **Visualisation** — matplotlib
- **Architecture** — Medallion (Bronze → Silver → Gold)
- **Environment** — Anaconda, JupyterLab

---

## Related Work

- **Project 1:** [NHS Outpatient Attendance Pipeline — 226 million records](https://github.com/YusufIsmailayo/nhs-patient-flow-data-pipeline)
- **Project 2:** [NHS RTT Incomplete Pathways Pipeline — 14 million pathways](https://github.com/YusufIsmailayo/nhs-rtt-incomplete-pathways-pipeline)
- **Project 3:** [NHS A&E Waiting Times Pipeline](https://github.com/YusufIsmailayo/nhs-ae-waiting-times)

---

*Built by [Yusuf Ismail](https://github.com/YusufIsmailayo) — Data Engineer focused on NHS pipelines and public sector analytics.*
