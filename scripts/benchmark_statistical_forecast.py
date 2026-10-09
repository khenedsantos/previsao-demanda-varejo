"""Mede duas especificações aditivas; não executa a população completa."""

import os
from pathlib import Path
import sys

for name in ["OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"]:
    os.environ[name]="1"
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from src.forecasting.ets_benchmark import run_benchmark


if __name__=="__main__":
    run_benchmark()
