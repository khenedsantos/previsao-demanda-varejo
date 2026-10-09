"""Executa apenas A/N/A autorizado; --compare-only preserva os ajustes já gerados."""

import argparse
import os
from pathlib import Path
import sys

for name in ["OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"]:
    os.environ[name]="1"
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--compare-only",action="store_true",help="Recalcula somente comparação, sem ajustar ETS novamente.")
    parser.add_argument("--fit-only",action="store_true",help="Executa somente os ajustes populacionais.")
    args=parser.parse_args()
    if args.compare_only and args.fit_only:
        parser.error("Escolha somente uma modalidade.")
    if not args.compare_only:
        from src.forecasting.statistical_backtesting import run_population
        run_population()
    if not args.fit_only:
        from src.forecasting.model_comparison import run_comparison
        run_comparison()
        from src.reporting.statistical_report import write_report
        write_report()
