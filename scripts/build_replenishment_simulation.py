"""Build hypothetical thresholds from frozen forecasts and train backtest errors."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    from src.replenishment.simulation import build_simulation
    build_simulation()
