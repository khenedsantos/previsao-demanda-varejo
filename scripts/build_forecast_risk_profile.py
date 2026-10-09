"""Constrói diagnósticos com os outputs aprovados; não ajusta ETS nem abre raw."""

from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

if __name__=="__main__":
    from src.segmentation.demand_risk import build_forecast_risk
    build_forecast_risk()
