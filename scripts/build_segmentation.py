"""Reproduz ABC/XYZ/exposição, exclusivamente ao corte documentado de train."""

from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from src.segmentation.operational_profile import build_segmentation
from src.reporting.segmentation_report import write_report


if __name__ == "__main__":
    write_report(build_segmentation())
