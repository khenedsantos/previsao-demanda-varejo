"""Integra ABC, XYZ e exposição mantendo dimensões e razões independentes."""

from datetime import date
from importlib.metadata import version
import json
from pathlib import Path
import re
import sys

import duckdb
import numpy as np
import pandas as pd

from src.features.demand_profile import TRAIN_START, TRAIN_END
from src.ingestion.source_manifest import ROOT, load_manifest, project_paths, sha256_file, verify_file
from src.segmentation.abc import classify_products, BOUNDARY_TOLERANCE
from src.segmentation.xyz import (
    WEEKLY_CV, PATTERN, REASONS, fit_thresholds, classify_series, assess_candidates,
)
from src.segmentation.stockout_exposure import (
    SUPPORT_METRICS, fit_exposure_thresholds, classify_exposure,
)


KEYS = ["store_id","product_id"]
CORRELATION_METRICS = ["coefficient_of_variation",WEEKLY_CV,PATTERN,"weekly_pattern_half_mae",
                       "autocorrelation_lag7","zero_ratio","adi"]
DIAGNOSTICS = ["coefficient_of_variation",WEEKLY_CV,PATTERN,"weekly_pattern_half_mae",
               "autocorrelation_lag7","zero_ratio","mean_demand","weekend_weekday_relative_difference"]


def load_sql():
    source = (ROOT / "sql/analytical/segmentation.sql").read_text(encoding="utf-8")
    pieces = re.split(r"^-- name: (\w+)\s*$",source,flags=re.MULTILINE)
    return {pieces[i]:pieces[i+1].strip().rstrip(";") for i in range(1,len(pieces),2)}


def validate_profile_scope(profile, as_of):
    expected_days = (as_of-TRAIN_START).days+1
    if profile.empty or profile[KEYS].isna().any().any() or profile.duplicated(KEYS).any():
        raise ValueError("Perfil de entrada vazio ou com chave inválida/duplicada.")
    if not profile.source_split.eq("train").all():
        raise ValueError("Somente perfil derivado de train é permitido; eval proibido.")
    if not pd.to_datetime(profile.first_date).eq(pd.Timestamp(TRAIN_START)).all():
        raise ValueError("Início do perfil difere da janela train.")
    if not pd.to_datetime(profile.last_date).eq(pd.Timestamp(as_of)).all():
        raise ValueError("Perfil contém dados posteriores ao corte ou janela diferente.")
    if not profile.n_days.eq(expected_days).all():
        raise ValueError("Cobertura temporal do perfil incompatível com o corte.")


def read_verified_profile(root, paths, train_entry, as_of):
    path = paths["processed"] / "mart_demand_profile.parquet"
    summary_path = paths["outputs"] / "demand_understanding/summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary["source_split"] != "train" or summary["as_of"] != str(as_of):
        raise ValueError("Resumo da Fase 2 não corresponde a train no corte solicitado.")
    if summary["source"]["path"] != "data/raw/train.parquet" or summary["source"]["sha256"] != train_entry["sha256"]:
        raise ValueError("Proveniência do perfil não corresponde ao train congelado.")
    if sha256_file(path) != summary["artifacts"]["profile"]["sha256"]:
        raise ValueError("Hash do perfil difere do output aprovado da Fase 2.")
    profile = pd.read_parquet(path).sort_values(KEYS).reset_index(drop=True)
    validate_profile_scope(profile,as_of)
    for column in ["total_stockout_hours","zero_days_with_stockout","zero_days"]:
        profile[column] = pd.to_numeric(profile[column]).astype("int64")
    return profile,{"profile_sha256":sha256_file(path),"phase2_summary_sha256":sha256_file(summary_path)}


def correlate_metrics(profile):
    rows = []
    for method in ["pearson","spearman"]:
        matrix = profile[CORRELATION_METRICS].corr(method=method)
        for left in CORRELATION_METRICS:
            for right in CORRELATION_METRICS:
                rows.append({"method":method,"metric_1":left,"metric_2":right,
                             "correlation":matrix.loc[left,right],
                             "paired_series":int((profile[left].notna() & profile[right].notna()).sum())})
    return pd.DataFrame(rows)


def describe_groups(frame, group, metrics):
    rows = []
    for label,subset in frame.groupby(group,sort=True):
        for metric in metrics:
            values = pd.to_numeric(subset[metric],errors="raise")
            rows.append({group:label,"metric":metric,"n_series":len(subset),
                         "valid":int(values.notna().sum()),"undefined":int(values.isna().sum()),
                         "minimum":values.min(),"p25":values.quantile(.25),"median":values.median(),
                         "p75":values.quantile(.75),"maximum":values.max(),"mean":values.mean()})
    return pd.DataFrame(rows)


def combine_dimensions(profile, abc, xyz, exposure):
    support = list(dict.fromkeys(["first_date","last_date","source_split","n_days","total_demand",
                                 *DIAGNOSTICS,"adi","zero_days","zero_days_with_stockout"]))
    result = profile[[*KEYS,*support]].merge(abc[["product_id","abc_class"]],on="product_id",validate="many_to_one")
    result = result.merge(xyz[[*KEYS,"xyz_class","xyz_reason","xyz_rule"]],on=KEYS,validate="one_to_one")
    exposure_fields = [c for c in exposure if c not in result or c in KEYS]
    result = result.merge(exposure[exposure_fields],on=KEYS,validate="one_to_one")
    classes = ["abc_class","xyz_class","stockout_exposure","censoring_risk_flag"]
    if len(result) != len(profile) or result.duplicated(KEYS).any() or result[classes].isna().any().any():
        raise ValueError("Junção das dimensões perdeu/duplicou séries ou deixou classe faltante.")
    return result.sort_values(KEYS).reset_index(drop=True)


def select_examples(operational):
    """Seis regras determinísticas; nenhum risco é reduzido a um score escalar."""
    abc,xyz = operational.abc_class,operational.xyz_class
    rules = [
        ("AX_MAX_SALES",(abc=="A") & (xyz=="X"),"total_demand",False,False),
        ("AX_MAX_STOCKOUT",(abc=="A") & (xyz=="X"),"stockout_rate",False,False),
        ("AZ_MAX_STOCKOUT",(abc=="A") & (xyz=="Z"),"stockout_rate",False,False),
        ("A_CENSOR_HIGH_STOCKOUT",(abc=="A") & operational.censoring_risk_flag,"stockout_rate",False,False),
        ("CX_MEDIAN_WEEKLY_CV",(abc=="C") & (xyz=="X"),WEEKLY_CV,True,True),
        ("CZ_MEDIAN_WEEKLY_CV",(abc=="C") & (xyz=="Z"),WEEKLY_CV,True,True),
    ]
    selected = []
    for name,mask,metric,ascending,typical in rules:
        candidates = operational.loc[mask].copy()
        if candidates.empty:
            continue
        reference = float(candidates[metric].median()) if typical else None
        candidates["selection_order"] = (candidates[metric]-reference).abs() if typical else candidates[metric]
        columns,order = ["selection_order",*KEYS],[ascending,True,True]
        if name == "A_CENSOR_HIGH_STOCKOUT":
            columns,order = ["selection_order","zero_ratio",*KEYS],[False,False,True,True]
        row = candidates.sort_values(columns,ascending=order,kind="stable").iloc[0].drop("selection_order").to_dict()
        selected.append({"selection_rule":name,"selection_metric":metric,"median_reference":reference,**row})
    return pd.DataFrame(selected)


def priority_profiles(operational):
    a,x,e = operational.abc_class,operational.xyz_class,operational.stockout_exposure
    masks = {"AX_HIGH":(a=="A")&(x=="X")&(e=="HIGH"),
             "AY_HIGH":(a=="A")&(x=="Y")&(e=="HIGH"),
             "AZ_HIGH":(a=="A")&(x=="Z")&(e=="HIGH"),
             "A_CENSOR_FLAG":(a=="A")&operational.censoring_risk_flag,
             "CZ_LOW":(a=="C")&(x=="Z")&(e=="LOW")}
    total = operational.total_demand.sum()
    rows = []
    for name,mask in masks.items():
        subset=operational.loc[mask]
        rows.append({"profile":name,"n_series":len(subset),"n_products":subset.product_id.nunique(),
                     "normalized_sales_total":subset.total_demand.sum(),"normalized_sales_share":subset.total_demand.sum()/total,
                     "median_stockout_rate":subset.stockout_rate.median(),
                     "median_weekly_cv":subset[WEEKLY_CV].median(),"median_pattern_correlation":subset[PATTERN].median(),
                     "censoring_risk_count":int(subset.censoring_risk_flag.sum())})
    return rows


def export(frame,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(".parquet.tmp")
    frame.to_parquet(temporary,index=False,engine="pyarrow",compression="zstd",row_group_size=65536)
    temporary.replace(path)
    return {"sha256":sha256_file(path),"rows":len(frame)}


def json_ready(value):
    if isinstance(value,dict):
        return {str(k):json_ready(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):
        return [json_ready(v) for v in value]
    if isinstance(value,(date,pd.Timestamp)):
        return value.isoformat()
    if isinstance(value,np.generic):
        return json_ready(value.item())
    if isinstance(value,float) and not np.isfinite(value):
        return None
    return value


def build_segmentation(root=ROOT,as_of=TRAIN_END):
    root=Path(root)
    if not TRAIN_START<=as_of<=TRAIN_END:
        raise ValueError("Corte fora de train; eval não pode ser usado.")
    _,paths=project_paths(root)
    manifest=load_manifest(root)
    train_entry=next(entry for entry in manifest["files"] if entry["role"]=="train")
    train_path=paths["raw"] / "train.parquet"
    verify_file(train_path,train_entry)
    profile,provenance=read_verified_profile(root,paths,train_entry,as_of)
    print(f"Fase 3: {len(profile)} séries train, corte {as_of}; ABC recalculado da fonte.",flush=True)
    sql=load_sql()
    with duckdb.connect(config={"threads":1,"memory_limit":"1GB"}) as connection:
        connection.execute("""CREATE TEMP TABLE train_sales AS
            SELECT cast(dt AS DATE) AS dt,store_id,product_id,sale_amount,
                   stock_hour6_22_cnt,activity_flag
            FROM read_parquet(?) WHERE cast(dt AS DATE) BETWEEN ? AND ?
            ORDER BY store_id,product_id,dt""",[str(train_path),TRAIN_START,as_of])
        raw_series=connection.execute("SELECT store_id,product_id,sum(sale_amount) AS raw_total,count(*) AS raw_days FROM train_sales GROUP BY store_id,product_id ORDER BY store_id,product_id").df()
        matched=profile.merge(raw_series,on=KEYS,validate="one_to_one",how="outer",indicator=True)
        if not matched["_merge"].eq("both").all() or not matched.n_days.eq(matched.raw_days).all():
            raise ValueError("Séries/dias do perfil não coincidem com train até o corte.")
        if not np.allclose(matched.total_demand,matched.raw_total,rtol=1e-12,atol=1e-9):
            raise ValueError("Venda total do perfil não coincide com train.")
        abc=classify_products(connection.execute(sql["product_totals"]).df())
        if as_of==TRAIN_END and (len(abc)!=865 or len(profile)!=50000):
            raise ValueError("Universo final de train difere dos 865 produtos / 50.000 séries validados.")
        xyz_thresholds=fit_thresholds(profile)
        xyz=classify_series(profile,xyz_thresholds)
        exposure_thresholds=fit_exposure_thresholds(profile)
        exposure=classify_exposure(profile,exposure_thresholds)
        operational=combine_dimensions(profile,abc,xyz,exposure)
        connection.register("operational",operational)
        matrix=connection.execute(sql["abc_xyz_matrix"]).df()
        cube=connection.execute(sql["exposure_cube"]).df()
        correlations=correlate_metrics(profile)
        candidates=assess_candidates(profile,DIAGNOSTICS)
        candidate_rows=[{"candidate":r["name"],"xyz_class":cls,"n_series":count,
                         "changed_vs_selected":r["changed_vs_selected"]}
                        for r in candidates for cls,count in r["class_counts"].items()]
        class_profiles=describe_groups(operational,"xyz_class",DIAGNOSTICS)
        examples=select_examples(operational)
        connection.register("examples",examples[["selection_rule",*KEYS]])
        example_daily=connection.execute("""
            SELECT e.selection_rule,t.* FROM train_sales t JOIN examples e USING(store_id,product_id)
            ORDER BY e.selection_rule,t.dt
        """).df()
    abc_counts=abc.groupby("abc_class",sort=True).agg(
        n_products=("product_id","size"),normalized_sales_total=("normalized_sales_total","sum"),
        normalized_sales_share=("normalized_sales_share","sum"),n_series=("associated_series","sum")).reset_index()
    exposure_counts=operational.groupby("stockout_exposure",sort=True).agg(
        n_series=("store_id","size"),normalized_sales_total=("total_demand","sum"),
        mean_stockout_rate=("stockout_rate","mean"),median_stockout_rate=("stockout_rate","median"),
        censoring_risk_count=("censoring_risk_flag","sum")).reset_index()
    flagged=operational.loc[operational.censoring_risk_flag]
    summary={"source_split":"train","as_of":str(as_of),"n_series":len(profile),"n_products":len(abc),
             "source":{"path":"data/raw/train.parquet","sha256":train_entry["sha256"],"revision":manifest["source_revision"]},
             "inputs":provenance,"runtime":{"python":sys.version.split()[0],**{p:version(p) for p in ["pandas","numpy","duckdb","pyarrow"]}},
             "abc":{"a_cumulative_limit":.8,"b_cumulative_limit":.95,"boundary_tolerance":BOUNDARY_TOLERANCE,
                    "rule":"cumulative_before_item; crossing_item_in_completing_class; ties_by_product_id",
                    "distribution":abc_counts.to_dict("records"),
                    "class_ending_products":abc.groupby("abc_class",sort=True).tail(1).to_dict("records")},
             "xyz":{"thresholds":xyz_thresholds,"reasons":REASONS,"candidates":candidates,
                    "distribution":xyz.xyz_class.value_counts().reindex(["X","Y","Z"],fill_value=0).to_dict(),
                    "undefined_stability":operational.loc[operational[PATTERN].isna(),[*KEYS,WEEKLY_CV,PATTERN,"xyz_class","xyz_reason"]].to_dict("records"),
                    "zero_majority_classes":operational.loc[operational.zero_ratio>.5,"xyz_class"].value_counts().reindex(["X","Y","Z"],fill_value=0).to_dict(),
                    "class_profiles":class_profiles.to_dict("records")},
             "correlations":correlations.to_dict("records"),
             "exposure":{"thresholds":exposure_thresholds,"distribution":exposure_counts.to_dict("records"),
                         "metric_profiles":describe_groups(operational,"stockout_exposure",SUPPORT_METRICS).to_dict("records"),
                         "censoring_count":len(flagged),"censoring_share":len(flagged)/len(profile),
                         "flagged_zero_stockout_fraction":float(flagged.zero_days_with_stockout.sum()/flagged.zero_days.sum()) if flagged.zero_days.sum() else None},
             "abc_xyz_matrix":matrix.to_dict("records"),"priority_profiles":priority_profiles(operational),
             "examples":examples.to_dict("records")}
    output=paths["outputs"] / "segmentation"
    artifacts={
        "product_abc":(abc,paths["processed"] / "mart_product_abc.parquet"),
        "series_xyz":(xyz,paths["processed"] / "mart_series_xyz.parquet"),
        "stockout_exposure":(exposure,paths["processed"] / "mart_stockout_exposure.parquet"),
        "operational_profile":(operational,paths["processed"] / "mart_operational_profile.parquet"),
        "correlations":(correlations,output / "metric_correlations.parquet"),
        "candidate_comparison":(pd.DataFrame(candidate_rows),output / "xyz_candidates.parquet"),
        "xyz_class_profiles":(class_profiles,output / "xyz_class_profiles.parquet"),
        "abc_xyz_matrix":(matrix,output / "abc_xyz_matrix.parquet"),
        "exposure_cube":(cube,output / "abc_xyz_exposure.parquet"),
        "example_profiles":(examples,output / "example_profiles.parquet"),
        "example_series":(example_daily,output / "example_series.parquet"),
    }
    summary["artifacts"]={name:{"path":path.relative_to(root).as_posix(),**export(frame,path)}
                          for name,(frame,path) in artifacts.items()}
    summary=json_ready(summary)
    (output / "summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(f"Segmentação concluída: ABC {len(abc)} produtos; XYZ {len(xyz)} séries; {len(flagged)} flags.",flush=True)
    return summary
