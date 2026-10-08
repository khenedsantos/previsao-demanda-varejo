"""ABC por contribuição de venda normalizada, exclusivamente no grão produto."""

import numpy as np


BOUNDARY_TOLERANCE = 1e-12


def classify_products(product_totals):
    """O item que cruza 80%/95% encerra a classe; o próximo inicia outra.

    Classifica pelo acumulado ANTERIOR ao item. Igualdade numérica com a fronteira
    (tolerância absoluta 1e-12 na participação) significa intervalo já completo.
    Empates de contribuição são ordenados por product_id, sem quotas por contagem.
    """
    result = product_totals.sort_values(
        ["normalized_sales_total", "product_id"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True).copy()
    sales = result.normalized_sales_total.to_numpy(dtype=float)
    if result.product_id.isna().any() or result.product_id.duplicated().any():
        raise ValueError("ABC exige product_id único e não nulo.")
    if not np.isfinite(sales).all() or (sales < 0).any() or sales.sum() <= 0:
        raise ValueError("ABC exige contribuições finitas, não negativas e soma positiva.")
    cumulative = np.cumsum(sales) / sales.sum()
    before = np.r_[0.0, cumulative[:-1]]
    below_a = (before < .8) & ~np.isclose(before, .8, rtol=0, atol=BOUNDARY_TOLERANCE)
    below_b = (before < .95) & ~np.isclose(before, .95, rtol=0, atol=BOUNDARY_TOLERANCE)
    result["normalized_sales_share"] = sales / sales.sum()
    result["normalized_sales_cumulative_share"] = cumulative
    result["normalized_sales_cumulative_share_before"] = before
    result["abc_rank"] = np.arange(1, len(result)+1, dtype=np.int64)
    result["abc_class"] = np.select([below_a, below_b], ["A", "B"], default="C")
    return result
