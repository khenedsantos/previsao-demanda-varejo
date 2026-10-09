"""Única população final; análise reproduzível com --evaluate-only sem refit."""

import argparse
import os
from pathlib import Path
import sys

for name in ["OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"]:
    os.environ[name]="1"
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group()
    group.add_argument("--fit-only",action="store_true")
    group.add_argument("--evaluate-only",action="store_true")
    args=parser.parse_args()
    if not args.evaluate_only:
        from src.forecasting.holdout import run_holdout_predictions
        run_holdout_predictions()
    if not args.fit_only:
        from src.validation.holdout_evaluation import evaluate_holdout
        evaluate_holdout()
