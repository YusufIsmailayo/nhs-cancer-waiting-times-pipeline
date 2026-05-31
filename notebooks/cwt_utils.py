"""
cwt_utils.py — shared helpers for my NHS Cancer Waiting Times Gold notebooks.

I keep the logic that every Gold notebook needs in one place: loading Silver files,
the common filters I reuse, and my chart styling. This way my three Gold notebooks
(trust lottery, cancer type, routes) stay focused on findings, not boilerplate —
and if I change a shared rule, I change it once, here.

Yusuf Ismail | NHS Data Engineering Portfolio | Project 4
"""

import pandas as pd
from pathlib import Path

# I resolve my project paths relative to this file, so it works no matter which
# notebook imports it.
PROJECT_DIR = Path(__file__).resolve().parent.parent
SILVER_DIR = PROJECT_DIR / "data" / "silver"
GOLD_DIR = PROJECT_DIR / "data" / "gold"
OUTPUTS_DIR = PROJECT_DIR / "outputs"

# The three standards and their official targets. I reference these everywhere so my
# compliance comparisons are always against the right threshold.
TARGETS = {
    "FDS": 0.75,   # Faster Diagnosis Standard — 75% (rising to 80% by 2026)
    "31D": 0.96,   # 31-day decision-to-treat — 96%
    "62D": 0.85,   # 62-day referral-to-treatment — 85% (interim 70% from Mar 2024)
}
TARGET_62D_INTERIM = 0.70  # the interim 62-day target NHS set as a stepping stone


def load_silver(stem: str) -> pd.DataFrame:
    """I load one primary Silver file by its stem, e.g. load_silver('62d')."""
    path = SILVER_DIR / f"silver_{stem}.parquet"
    df = pd.read_parquet(path)
    return df


def load_silver_bands(stem: str) -> pd.DataFrame:
    """I load one Silver bands file when I need severity (waiting-time band) detail."""
    path = SILVER_DIR / f"silver_bands_{stem}.parquet"
    return pd.read_parquet(path)


# The join key that lets me reattach bands to headline data. Proven unique in Silver.
JOIN_KEY = [
    "period_date", "Org_Code", "Standard_or_Item",
    "Cancer_Type", "Referral_Route_or_Stage", "Treatment_Modality",
]


def exclude_total_row(df: pd.DataFrame) -> pd.DataFrame:
    """I drop the England aggregate row (Org_Code == 'Total') for any trust-level ranking.
    The Total row is the national figure living inside the data — useful for national
    trends, wrong for league tables."""
    return df[df["Org_Code"] != "Total"].copy()


def national_only(df: pd.DataFrame) -> pd.DataFrame:
    """I keep ONLY the England aggregate row, for national trend analysis."""
    return df[df["Org_Code"] == "Total"].copy()

# ── Chart styling ─────────────────────────────────────────────────────────
# I keep my chart look in one place so all three articles in the trilogy match,
# and stay consistent with my earlier NHS projects (RTT, A&E).
import matplotlib.pyplot as plt

# My house palette.
INK = "#111111"        # titles / primary text
BLUE = "#1a56db"       # the "improving" or neutral series
RED = "#e02424"        # the "failure" / breach series
GREEN = "#059669"      # target reference lines
GREY = "#666666"       # subtitles / source notes
BG = "#FAFAF7"         # warm off-white background

def style_axes(ax):
    """I apply my standard clean look to any axes: warm background, no top/right
    spines, soft horizontal gridlines, no tick marks."""
    ax.set_facecolor(BG)
    ax.yaxis.grid(True, color="#E0E0D8", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(left=False, bottom=False, labelsize=10)

def source_note(fig, text):
    """I stamp every chart with a source + attribution line, like my other projects."""
    fig.text(0.01, -0.02, text, fontsize=8, color=GREY)

SOURCE_LINE = ("Source: NHS England Cancer Waiting Times | "
               "github.com/YusufIsmailayo")