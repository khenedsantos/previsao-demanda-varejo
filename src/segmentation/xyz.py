"""XYZ categórico: variabilidade semanal e estabilidade da forma, sem score."""

import numpy as np
import pandas as pd


WEEKLY_CV = "weekly_coefficient_of_variation"
PATTERN = "weekly_pattern_half_correlation"
CANDIDATES = [
    {"name":"weekly_quartiles", "variability_metric":WEEKLY_CV, "low_q":.25, "high_q":.75},
    {"name":"weekly_median_tail", "variability_metric":WEEKLY_CV, "low_q":.5, "high_q":.75},
    {"name":"weekly_tertiles", "variability_metric":WEEKLY_CV, "low_q":1/3, "high_q":2/3},
    {"name":"daily_median_tail", "variability_metric":"coefficient_of_variation", "low_q":.5, "high_q":.75},
]
SELECTED_RULE = "weekly_median_tail"
REASONS = {
    "X_LOW_CV_STABLE":"CV até a mediana e estabilidade a partir da mediana; nenhum critério Z.",
    "Y_INTERMEDIATE":"Métricas válidas, fora dos critérios X e Z.",
    "Z_HIGH_CV":"CV a partir do p75; estabilidade não está na cauda inferior.",
    "Z_LOW_STABILITY":"Estabilidade até p25; CV não está na cauda superior.",
    "Z_BOTH":"CV a partir de p75 e estabilidade até p25.",
    "Z_HIGH_CV_NO_PATTERN":"Estabilidade indefinida; CV válido a partir de p75 já justifica Z.",
    "Z_LOW_PATTERN_NO_CV":"CV indefinido; estabilidade válida até p25 já justifica Z.",
    "Y_INCOMPLETE_METRICS":"Sem evidência válida suficiente para X ou Z; revisar, não presumir estabilidade.",
}


def fit_thresholds(profile, candidate=None):
    candidate = candidate or next(c for c in CANDIDATES if c["name"] == SELECTED_RULE)
    v = profile[candidate["variability_metric"]].replace([np.inf, -np.inf], np.nan)
    s = profile[PATTERN].replace([np.inf, -np.inf], np.nan)
    if not v.notna().any() or not s.notna().any():
        raise ValueError("Sem valores válidos para derivar thresholds XYZ de train.")
    return {**candidate,"stability_metric":PATTERN,"interpolation":"linear",
            "variability_low":float(v.quantile(candidate["low_q"])),
            "variability_high":float(v.quantile(candidate["high_q"])),
            "stability_low":float(s.quantile(1-candidate["high_q"])),
            "stability_good":float(s.quantile(1-candidate["low_q"])),
            "n_series":len(profile),"valid_variability":int(v.notna().sum()),"valid_stability":int(s.notna().sum())}


def classify_series(profile, thresholds):
    """Não lê ABC, disponibilidade, atividade ou importância financeira.

    Prioridade: evidência de Z; depois X; demais Y. Uma métrica indefinida nunca é
    preenchida com zero. Sem evidência válida de Z, indefinidos recebem Y explícito.
    """
    metric = thresholds["variability_metric"]
    result = profile[["store_id","product_id",metric,PATTERN]].copy()
    v = result[metric].replace([np.inf, -np.inf], np.nan)
    s = result[PATTERN].replace([np.inf, -np.inf], np.nan)
    result[metric],result[PATTERN] = v,s
    high = v.ge(thresholds["variability_high"])
    poor = s.le(thresholds["stability_low"])
    low_stable = v.le(thresholds["variability_low"]) & s.ge(thresholds["stability_good"])
    result["xyz_class"] = np.select([high | poor, low_stable], ["Z","X"], default="Y")
    result["xyz_reason"] = np.select(
        [high & s.isna(), poor & v.isna(), high & poor, high, poor,
         v.isna() | s.isna(), low_stable],
        ["Z_HIGH_CV_NO_PATTERN","Z_LOW_PATTERN_NO_CV","Z_BOTH","Z_HIGH_CV","Z_LOW_STABILITY",
         "Y_INCOMPLETE_METRICS","X_LOW_CV_STABLE"], default="Y_INTERMEDIATE")
    result["xyz_rule"] = thresholds["name"]
    return result.sort_values(["store_id","product_id"]).reset_index(drop=True)


def assess_candidates(profile, diagnostic_metrics):
    evaluations = []
    memberships = pd.DataFrame(index=profile.index)
    for candidate in CANDIDATES:
        thresholds = fit_thresholds(profile, candidate)
        classes = classify_series(profile, thresholds)
        joined = profile.merge(classes[["store_id","product_id","xyz_class"]],
                               on=["store_id","product_id"], validate="one_to_one")
        counts = joined.xyz_class.value_counts().reindex(["X","Y","Z"],fill_value=0)
        medians = joined.groupby("xyz_class")[diagnostic_metrics].median().reset_index()
        majority = joined.loc[joined.zero_ratio>.5,"xyz_class"].value_counts().reindex(["X","Y","Z"],fill_value=0)
        evaluations.append({"name":candidate["name"],"thresholds":thresholds,
                            "class_counts":counts.to_dict(),"median_profiles":medians.to_dict("records"),
                            "majority_zero_classes":majority.to_dict()})
        memberships[candidate["name"]] = joined.xyz_class.to_numpy()
    for evaluation in evaluations:
        evaluation["changed_vs_selected"] = int((memberships[evaluation["name"]] != memberships[SELECTED_RULE]).sum())
    return evaluations
