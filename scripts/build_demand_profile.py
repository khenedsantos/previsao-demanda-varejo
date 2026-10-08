"""Reproduz a Fase 2 lendo exclusivamente train.parquet."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.demand_profile import build_demand_profile
from src.reporting.demand_understanding_report import write_report


if __name__ == "__main__":
    report = build_demand_profile()
    write_report(report)
