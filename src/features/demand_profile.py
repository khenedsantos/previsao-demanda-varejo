"""Perfil descritivo reproduzível, exclusivamente train, com corte temporal explícito."""

from datetime import date
from importlib.metadata import version
import json
from pathlib import Path
import re

import duckdb
import pyarrow.parquet as pq

from src.ingestion.source_manifest import ROOT, load_manifest, project_paths, sha256_file, verify_file


TRAIN_START = date(2024, 3, 28)
TRAIN_END = date(2024, 6, 25)
# Tolerância numérica na escala normalizada; não é limiar de segmentação.
MEAN_EPSILON = 1e-9
PROBABILITIES = [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]


def records(connection, query, parameters=None):
    cursor = connection.execute(query, parameters or [])
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def load_queries():
    source = (ROOT / "sql/analytical/demand_profile.sql").read_text(encoding="utf-8")
    pieces = re.split(r"^-- name: (\w+)\s*$", source, flags=re.MULTILINE)
    return {pieces[i]: pieces[i+1].strip().rstrip(";") for i in range(1, len(pieces), 2)}


def prepare_tables(connection, train_path, as_of=TRAIN_END):
    """Filtra ANTES de agregações, lags, semanas, quantis e seleção de exemplos.

    Entrada fixa train.parquet, nunca um glob ou staging combinado. Exige calendário
    diário completo até o corte para que ADI e sequências tenham denominador correto.
    """
    if not isinstance(as_of, date) or not TRAIN_START <= as_of <= TRAIN_END:
        raise ValueError("Corte fora da janela train congelada.")
    train_path = Path(train_path)
    if train_path.name != "train.parquet":
        raise ValueError("A Fase 2 aceita somente train.parquet.")
    connection.execute("""
        CREATE TEMP TABLE train AS
        SELECT cast(dt AS DATE) AS dt,store_id,product_id,sale_amount,
               stock_hour6_22_cnt,activity_flag,discount
        FROM read_parquet(?) WHERE cast(dt AS DATE) BETWEEN ? AND ?
        ORDER BY store_id,product_id,dt
    """, [str(train_path), TRAIN_START, as_of])
    expected_days = (as_of-TRAIN_START).days+1
    invalid = connection.execute("""
        SELECT count(*) FROM (
            SELECT store_id,product_id FROM train GROUP BY store_id,product_id
            HAVING count(*)!=? OR count(DISTINCT dt)!=?
        )
    """, [expected_days, expected_days]).fetchone()[0]
    bad_values = connection.execute("""
        SELECT count(*) FROM train WHERE store_id IS NULL OR product_id IS NULL
        OR sale_amount IS NULL OR NOT isfinite(sale_amount) OR sale_amount<0
        OR stock_hour6_22_cnt IS NULL OR stock_hour6_22_cnt NOT BETWEEN 0 AND 16
        OR activity_flag IS NULL OR activity_flag NOT IN (0,1)
        OR discount IS NULL OR NOT isfinite(discount)
    """).fetchone()[0]
    if invalid or bad_values or connection.execute("SELECT count(*) FROM train").fetchone()[0] == 0:
        raise ValueError("Train vazio, inválido ou com calendário incompleto até o corte.")
    queries = load_queries()
    for table, query in [("daily", "daily_features"), ("weekly", "weekly"),
                         ("weekday", "weekday"), ("stability", "stability"), ("profile", "profile")]:
        parameters = {"epsilon": MEAN_EPSILON} if "$epsilon" in queries[query] else None
        connection.execute(f"CREATE TEMP TABLE {table} AS " + queries[query], parameters)
    validate_profile(connection, expected_days, as_of)


def validate_profile(connection, expected_days, as_of):
    row = records(connection, """
        SELECT count(*) AS n_series,count(DISTINCT (store_id,product_id)) AS unique_series,
               count(*) FILTER(WHERE source_split!='train' OR first_date!=? OR last_date!=?
                   OR n_days!=? OR positive_days+zero_days!=n_days
                   OR zero_ratio NOT BETWEEN 0 AND 1 OR stockout_rate NOT BETWEEN 0 AND 1
                   OR zero_days_with_stockout+zero_days_without_stockout!=zero_days) AS invalid
        FROM profile
    """, [TRAIN_START, as_of, expected_days])[0]
    if row["n_series"] != row["unique_series"] or row["invalid"]:
        raise ValueError(f"Contrato do perfil reprovado: {row}")


def export_table(connection, query, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Ordenação total, uma thread e formato fixo tornam o hash reproduzível no runtime registrado.
    table = connection.execute(query).to_arrow_table()
    temporary = path.with_suffix(".parquet.tmp")
    pq.write_table(table, temporary, compression="zstd", version="2.6", row_group_size=65536)
    temporary.replace(path)


def concentration(connection):
    connection.execute("""
        CREATE TEMP TABLE concentration AS
        WITH entities AS (
            SELECT 'product' AS level,NULL::BIGINT AS store_id,product_id,sum(sale_amount) AS total_demand
                FROM daily GROUP BY product_id
            UNION ALL
            SELECT 'store',store_id,NULL::BIGINT,sum(sale_amount) FROM daily GROUP BY store_id
            UNION ALL
            SELECT 'series',store_id,product_id,total_demand FROM profile
        ), ranked AS (
            SELECT *,row_number() OVER w AS rank,
                   count(*) OVER(PARTITION BY level) AS n_entities,
                   total_demand/nullif(sum(total_demand) OVER(PARTITION BY level),0) AS demand_share
            FROM entities WINDOW w AS (PARTITION BY level ORDER BY total_demand DESC,store_id,product_id)
        )
        SELECT *,rank::DOUBLE/n_entities AS entity_fraction,
               sum(demand_share) OVER(PARTITION BY level ORDER BY rank) AS cumulative_share
        FROM ranked
    """)
    return records(connection, """
        SELECT level,max(n_entities) AS n_entities,
            sum(demand_share) FILTER(WHERE rank<=ceil(n_entities*.01)) AS top_1pct_share,
            sum(demand_share) FILTER(WHERE rank<=ceil(n_entities*.05)) AS top_5pct_share,
            sum(demand_share) FILTER(WHERE rank<=ceil(n_entities*.20)) AS top_20pct_share,
            min(rank) FILTER(WHERE cumulative_share>=.80) AS entities_for_80pct,
            min(rank) FILTER(WHERE cumulative_share>=.95) AS entities_for_95pct
        FROM concentration GROUP BY level ORDER BY level
    """)


def choose_examples(connection):
    thresholds = records(connection, """
        SELECT quantile_cont(mean_demand,.25) AS demand_q25,quantile_cont(mean_demand,.75) AS demand_q75,
               quantile_cont(stockout_rate,.25) AS stockout_q25,quantile_cont(stockout_rate,.75) AS stockout_q75,
               quantile_cont(zero_ratio,.75) AS zero_q75 FROM profile
    """)[0]
    # Quantis empíricos apenas para exemplos; nenhuma classe é gravada no mart.
    conditions = [
        ("alta_venda_baixa_ruptura", "mean_demand>=? AND stockout_rate<=?", "mean_demand DESC", [thresholds["demand_q75"],thresholds["stockout_q25"]]),
        ("alta_venda_alta_ruptura", "mean_demand>=? AND stockout_rate>=?", "mean_demand DESC", [thresholds["demand_q75"],thresholds["stockout_q75"]]),
        ("baixa_venda_baixa_ruptura", "mean_demand<=? AND stockout_rate<=?", "mean_demand ASC", [thresholds["demand_q25"],thresholds["stockout_q25"]]),
        ("maior_volatilidade", "coefficient_of_variation IS NOT NULL", "coefficient_of_variation DESC", []),
        ("maior_proporcao_zeros", "true", "zero_ratio DESC", []),
    ]
    examples = []
    for name, condition, order, params in conditions:
        candidates = records(connection, f"SELECT * FROM profile WHERE {condition} ORDER BY {order},store_id,product_id LIMIT 1", params)
        if candidates:
            examples.append({"rule":name, **candidates[0]})
    return thresholds, examples


def summarize(connection, as_of):
    report = {"source_split":"train", "as_of":str(as_of), "mean_epsilon":MEAN_EPSILON,
              "quantile_probabilities":PROBABILITIES}
    report["overview"] = records(connection, """
        SELECT count(*) AS n_rows,count(DISTINCT (store_id,product_id)) AS n_series,
            count(DISTINCT product_id) AS n_products,count(DISTINCT store_id) AS n_stores,
            min(dt) AS first_date,max(dt) AS last_date,avg(sale_amount) AS mean_daily_sale,
            median(sale_amount) AS median_daily_sale,sum(sale_amount) AS total_sale,
            count(*) FILTER(WHERE sale_amount=0) AS zero_rows,
            avg((sale_amount=0)::INTEGER) AS zero_row_ratio,
            avg(stockout::INTEGER) AS stockout_row_rate,avg(activity_flag) AS activity_row_rate
        FROM daily
    """)[0]
    report["distributions"] = {}
    for metric in ["mean_demand","median_demand","total_demand","coefficient_of_variation","zero_ratio",
                   "adi","positive_demand_cv_squared","stockout_rate","total_stockout_hours",
                   "mean_stockout_hours_when_affected","maximum_consecutive_stockout_days",
                   "autocorrelation_lag7","weekly_coefficient_of_variation",
                   "weekly_pattern_half_correlation","weekly_pattern_half_mae",
                   "weekend_weekday_relative_difference","activity_rate","activity_stockout_rate_difference"]:
        report["distributions"][metric] = records(connection, f"""
            SELECT count({metric}) AS valid,count(*)-count({metric}) AS undefined,
                min({metric}) AS minimum,max({metric}) AS maximum,avg({metric}) AS mean,
                quantile_cont({metric},?) AS quantiles FROM profile
        """, [PROBABILITIES])[0]
    report["intermittency"] = records(connection, """
        SELECT count(*) FILTER(WHERE zero_days=0) AS no_zeros,
               count(*) FILTER(WHERE zero_days>0) AS any_zeros,
               count(*) FILTER(WHERE zero_days>n_days/2.0) AS majority_zero_days,
               count(*) FILTER(WHERE positive_days=0) AS all_zero,
               count(*) FILTER(WHERE near_zero_mean) AS near_zero_mean,
               sum(zero_days_with_stockout) AS zero_rows_with_stockout,
               sum(zero_days_without_stockout) AS zero_rows_without_stockout
        FROM profile
    """)[0]
    report["zero_days_distribution"] = records(connection, "SELECT zero_days,count(*) AS n_series FROM profile GROUP BY zero_days ORDER BY zero_days")
    report["weekday"] = records(connection, """
        WITH global_day AS (
            SELECT weekday,count(*) AS n_rows,avg(sale_amount) AS mean_demand,
                   avg(stockout::INTEGER) AS stockout_rate,avg(activity_flag) AS activity_rate
            FROM daily GROUP BY weekday
        ), relative AS (
            SELECT w.weekday,quantile_cont(w.mean_demand/p.mean_demand,[.25,.5,.75]) AS relative_series_quantiles
            FROM weekday w JOIN profile p USING(store_id,product_id)
            WHERE p.mean_demand>$epsilon GROUP BY w.weekday
        ) SELECT * FROM global_day JOIN relative USING(weekday) ORDER BY weekday
    """, {"epsilon":MEAN_EPSILON})
    report["weekly"] = records(connection, """
        SELECT min(complete_weeks) AS min_complete_weeks,max(complete_weeks) AS max_complete_weeks,
               count(*) FILTER(WHERE autocorrelation_lag7>0) AS positive_lag7,
               count(*) FILTER(WHERE weekly_pattern_half_correlation>0) AS positive_half_correlation,
               count(*) FILTER(WHERE weekend_weekday_difference>0) AS weekend_above_weekday
        FROM profile
    """)[0]
    report["stockout_comparison"] = records(connection, """
        SELECT stockout,count(*) AS n_rows,avg(sale_amount) AS mean_demand,median(sale_amount) AS median_demand,
               avg((sale_amount=0)::INTEGER) AS zero_ratio FROM daily GROUP BY stockout ORDER BY stockout
    """)
    report["stockout_hours"] = records(connection, """
        SELECT stock_hour6_22_cnt AS stockout_hours,count(*) AS n_rows,avg(sale_amount) AS mean_demand,
               avg((sale_amount=0)::INTEGER) AS zero_ratio
        FROM daily GROUP BY stock_hour6_22_cnt ORDER BY stock_hour6_22_cnt
    """)
    report["within_series"] = records(connection, """
        SELECT count(*) FILTER(WHERE stockout_demand_difference IS NOT NULL) AS stockout_comparable_series,
               count(*) FILTER(WHERE stockout_demand_difference>0) AS stockout_higher_series,
               count(*) FILTER(WHERE stockout_demand_difference<0) AS stockout_lower_series,
               median(stockout_demand_difference) AS median_stockout_difference,
               avg(stockout_demand_difference) AS mean_stockout_difference,
               count(*) FILTER(WHERE activity_demand_difference IS NOT NULL) AS activity_comparable_series,
               count(*) FILTER(WHERE activity_demand_difference>0) AS activity_higher_series,
               count(*) FILTER(WHERE activity_stockout_rate_difference>0) AS activity_stockout_higher_series,
               median(activity_stockout_rate_difference) AS median_activity_stockout_difference,
               median(activity_demand_difference) AS median_activity_difference,
               avg(activity_demand_difference) AS mean_activity_difference
        FROM profile
    """)[0]
    report["stockout_quartiles"] = records(connection, """
        WITH q AS (SELECT quantile_cont(stockout_rate,[.25,.5,.75]) AS cuts FROM profile),
        grouped AS (SELECT *,CASE WHEN stockout_rate<=cuts[1] THEN 1 WHEN stockout_rate<=cuts[2] THEN 2
                    WHEN stockout_rate<=cuts[3] THEN 3 ELSE 4 END AS empirical_quartile FROM profile,q)
        SELECT empirical_quartile,count(*) AS n_series,min(stockout_rate) AS min_stockout_rate,
               max(stockout_rate) AS max_stockout_rate,avg(mean_demand) AS mean_demand,
               avg(zero_ratio) AS mean_zero_ratio,median(coefficient_of_variation) AS median_cv,
               sum(zero_days_with_stockout)::DOUBLE/nullif(sum(zero_days),0) AS fraction_zeros_with_stockout,
               median(stockout_demand_difference) AS median_within_series_difference
        FROM grouped GROUP BY empirical_quartile ORDER BY empirical_quartile
    """)
    report["activity_comparison"] = records(connection, """
        SELECT activity_flag,count(*) AS n_rows,avg(sale_amount) AS mean_demand,
               median(sale_amount) AS median_demand,avg(stockout::INTEGER) AS stockout_rate
        FROM daily GROUP BY activity_flag ORDER BY activity_flag
    """)
    report["discount"] = records(connection, """
        SELECT min(discount) AS minimum,max(discount) AS maximum,
               quantile_cont(discount,[.01,.05,.25,.5,.75,.95,.99]) AS quantiles,
               count(*) FILTER(WHERE discount=0) AS zero_rows,
               count(*) FILTER(WHERE discount>0 AND discount<1) AS discount_rows,
               count(*) FILTER(WHERE discount=1) AS equal_one_rows,
               count(*) FILTER(WHERE discount>1) AS above_one_rows
        FROM daily
    """)[0]
    report["discount_domains"] = records(connection, "SELECT discount,count(*) AS n_rows FROM daily GROUP BY discount ORDER BY discount")
    report["discount_activity"] = records(connection, """
        SELECT activity_flag,CASE WHEN discount=0 THEN 'zero' WHEN discount<0 THEN 'negative'
               WHEN discount<1 THEN 'between_zero_one' WHEN discount=1 THEN 'one' ELSE 'above_one' END AS discount_group,
               count(*) AS n_rows FROM daily GROUP BY ALL ORDER BY activity_flag,discount_group
    """)
    report["discount_anomalies"] = records(connection, """
        SELECT store_id,product_id,dt,discount,activity_flag,sale_amount,stock_hour6_22_cnt
        FROM daily WHERE discount>1 ORDER BY product_id,store_id,dt
    """)
    report["anomalous_product_context"] = records(connection, """
        SELECT product_id,count(*) AS n_rows,count(DISTINCT store_id) AS n_stores,
               min(discount) AS min_discount,max(discount) AS max_discount,
               count(*) FILTER(WHERE discount>1) AS above_one_rows,
               count(*) FILTER(WHERE discount=0) AS zero_rows,
               count(*) FILTER(WHERE activity_flag=1) AS activity_rows
        FROM daily WHERE product_id IN(SELECT product_id FROM daily WHERE discount>1)
        GROUP BY product_id ORDER BY product_id
    """)
    report["concentration"] = concentration(connection)
    report["example_thresholds"], report["examples"] = choose_examples(connection)
    report["censoring_overlap"] = records(connection, """
        WITH q AS (SELECT quantile_cont(stockout_rate,.75) AS sr,quantile_cont(zero_ratio,.75) AS zr FROM profile)
        SELECT count(*) AS n_series,avg(zero_ratio) AS mean_zero_ratio,avg(stockout_rate) AS mean_stockout_rate,
               sum(zero_days_with_stockout)::DOUBLE/nullif(sum(zero_days),0) AS fraction_zeros_with_stockout
        FROM profile,q WHERE stockout_rate>=sr AND zero_ratio>=zr
    """)[0]
    return report


def build_demand_profile(root=ROOT, as_of=TRAIN_END):
    root = Path(root)
    _, paths = project_paths(root)
    manifest = load_manifest(root)
    train_entry = next(entry for entry in manifest["files"] if entry["role"] == "train")
    train_path = paths["raw"] / "train.parquet"
    verify_file(train_path, train_entry)  # Apenas train; eval pode nem existir neste ambiente.
    output = paths["outputs"] / "demand_understanding"
    temporary = root / ".tmp/demand_understanding"
    temporary.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(config={"threads":1,"memory_limit":"1GB", "temp_directory":str(temporary),
                                "max_temp_directory_size":"2GB"}) as connection:
        print(f"Fase 2: somente train, corte {as_of}; calculando perfis...", flush=True)
        prepare_tables(connection, train_path, as_of)
        report = summarize(connection, as_of)
        exports = {
            "profile": (paths["processed"] / "mart_demand_profile.parquet", "SELECT * FROM profile ORDER BY store_id,product_id"),
            "weekly": (output / "series_weekly.parquet", "SELECT * FROM weekly ORDER BY store_id,product_id,week_start"),
            "weekday": (output / "series_weekday.parquet", "SELECT * FROM weekday ORDER BY store_id,product_id,weekday"),
            "concentration": (output / "concentration.parquet", "SELECT * FROM concentration ORDER BY level,rank"),
            "discount_anomalies": (output / "discount_above_one.parquet", "SELECT store_id,product_id,dt,discount,activity_flag,sale_amount,stock_hour6_22_cnt FROM daily WHERE discount>1 ORDER BY product_id,store_id,dt"),
        }
        connection.execute("CREATE TEMP TABLE selected_examples(rule VARCHAR,store_id BIGINT,product_id BIGINT)")
        for example in report["examples"]:
            connection.execute("INSERT INTO selected_examples VALUES (?,?,?)", [example["rule"],example["store_id"],example["product_id"]])
        exports["examples"] = (output / "example_series.parquet", "SELECT e.rule,d.dt,d.store_id,d.product_id,d.sale_amount,d.stock_hour6_22_cnt,d.activity_flag,d.discount FROM daily d JOIN selected_examples e USING(store_id,product_id) ORDER BY e.rule,d.dt")
        report["artifacts"] = {}
        for name, (path, query) in exports.items():
            export_table(connection, query, path)
            report["artifacts"][name] = {"path":path.relative_to(root).as_posix(), "sha256":sha256_file(path),
                                         "rows":pq.ParquetFile(path).metadata.num_rows}
    report["source"] = {"path":train_path.relative_to(root).as_posix(), "sha256":train_entry["sha256"],
                        "revision":manifest["source_revision"]}
    report["runtime"] = {package:version(package) for package in ["duckdb","pyarrow"]}
    # Nenhum relógio, caminho absoluto ou metadado volátil entra no output.
    payload = json.dumps(report, ensure_ascii=False, indent=2, default=str, allow_nan=False)+"\n"
    (output / "summary.json").write_text(payload, encoding="utf-8")
    print(f"Perfil concluído: {report['overview']['n_series']} séries.", flush=True)
    return report
