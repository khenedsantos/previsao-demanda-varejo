"""Executa os dois baselines e quatro folds prospectivos em train."""

from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from src.forecasting.backtesting import run_backtest
from src.reporting.forecast_report import write_report


if __name__ == "__main__":
    summary,performance=run_backtest()
    write_report(summary,performance)
