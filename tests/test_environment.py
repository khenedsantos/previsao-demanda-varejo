"""Verifica somente a disponibilidade da stack; não contém testes analíticos."""

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "pandas",
        "numpy",
        "duckdb",
        "pyarrow",
        "statsmodels.api",
        "sklearn",
        "matplotlib.pyplot",
        "jupyter_core",
        "pytest",
        "yaml",
    ],
)
def test_stack_import(module_name):
    import_module(module_name)
