"""Export and validate six BI tables; no forecasting, raw or dashboard."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    from src.reporting.powerbi_layer import build_powerbi_layer
    build_powerbi_layer()
