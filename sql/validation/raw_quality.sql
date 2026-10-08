-- Consultas sobre a view raw: Parquet oficiais + proveniência, sem alteração da fonte.
-- name: summary
SELECT coalesce(source_split, 'all') AS scope,
       count(*) AS n_rows,
       min(try_cast(dt AS DATE)) AS first_date,
       max(try_cast(dt AS DATE)) AS last_date,
       count(DISTINCT dt) AS n_dates,
       count(DISTINCT city_id) AS n_cities,
       count(DISTINCT store_id) AS n_stores,
       count(DISTINCT product_id) AS n_products,
       count(DISTINCT (store_id, product_id)) AS n_series,
       count(*) FILTER (WHERE try_cast(dt AS DATE) IS NULL
           OR NOT regexp_full_match(dt, '[0-9]{4}-[0-9]{2}-[0-9]{2}')) AS invalid_dates,
       count(*) FILTER (WHERE dt IS NULL OR store_id IS NULL OR product_id IS NULL) AS null_keys
FROM raw GROUP BY GROUPING SETS ((source_split), ()) ORDER BY scope;

-- name: duplicate_keys
SELECT coalesce(source_split, 'all') AS scope, dt, store_id, product_id, count(*) AS occurrences
FROM raw
GROUP BY GROUPING SETS ((source_split, dt, store_id, product_id), (dt, store_id, product_id))
HAVING count(*) > 1;

-- name: coverage
WITH series AS (
    SELECT coalesce(source_split, 'all') AS scope, store_id, product_id,
           min(try_cast(dt AS DATE)) AS first_date,
           max(try_cast(dt AS DATE)) AS last_date,
           count(*) AS n_observations,
           count(DISTINCT try_cast(dt AS DATE)) AS n_unique_dates
    FROM raw GROUP BY GROUPING SETS ((source_split, store_id, product_id), (store_id, product_id))
)
SELECT *, date_diff('day', first_date, last_date) + 1 AS n_calendar_days,
       n_calendar_days - n_unique_dates AS missing_days,
       n_unique_dates::DOUBLE / n_calendar_days AS coverage_ratio
FROM series;

-- name: coverage_summary
SELECT scope, count(*) AS n_series, min(n_observations) AS min_observations,
       median(n_observations) AS median_observations, avg(n_observations) AS mean_observations,
       max(n_observations) AS max_observations,
       count(*) FILTER (WHERE missing_days=0) AS complete_series,
       count(*) FILTER (WHERE missing_days>0) AS series_with_gaps,
       min(coverage_ratio) AS min_coverage_ratio, max(coverage_ratio) AS max_coverage_ratio
FROM coverage GROUP BY scope ORDER BY scope;

-- name: coverage_distribution
SELECT scope, n_observations, n_calendar_days, missing_days, count(*) AS n_series
FROM coverage GROUP BY ALL ORDER BY scope, n_observations, n_calendar_days, missing_days;

-- name: stockout_sales
SELECT coalesce(source_split, 'all') AS scope,
       CASE WHEN stock_hour6_22_cnt IS NULL THEN 'unknown'
            WHEN stock_hour6_22_cnt>0 THEN 'with_stockout' ELSE 'without_stockout' END AS availability,
       CASE WHEN sale_amount IS NULL THEN 'null' WHEN NOT isfinite(sale_amount) THEN 'nonfinite'
            WHEN sale_amount=0 THEN 'zero' WHEN sale_amount>0 THEN 'positive' ELSE 'negative' END AS sales,
       count(*) AS n_rows, avg(sale_amount) AS mean_sale, median(sale_amount) AS median_sale
FROM raw GROUP BY GROUPING SETS ((source_split, availability, sales), (availability, sales))
ORDER BY scope, availability, sales;

-- name: stockout_summary
SELECT coalesce(source_split, 'all') AS scope,
       count(*) AS n_rows,
       count(*) FILTER (WHERE stock_hour6_22_cnt>0) AS stockout_rows,
       100.0 * stockout_rows / n_rows AS stockout_rows_pct,
       count(DISTINCT (store_id, product_id)) AS n_series,
       count(DISTINCT (store_id, product_id)) FILTER (WHERE stock_hour6_22_cnt>0) AS stockout_series,
       100.0 * stockout_series / n_series AS stockout_series_pct,
       avg(sale_amount) FILTER (WHERE stock_hour6_22_cnt>0) AS mean_sale_with_stockout,
       median(sale_amount) FILTER (WHERE stock_hour6_22_cnt>0) AS median_sale_with_stockout,
       avg(sale_amount) FILTER (WHERE stock_hour6_22_cnt=0) AS mean_sale_without_stockout,
       median(sale_amount) FILTER (WHERE stock_hour6_22_cnt=0) AS median_sale_without_stockout
FROM raw GROUP BY GROUPING SETS ((source_split), ()) ORDER BY scope;

-- name: hourly
SELECT coalesce(source_split, 'all') AS scope,
       min(len(hours_sale)) AS sale_min_length, max(len(hours_sale)) AS sale_max_length,
       min(len(hours_stock_status)) AS stock_min_length, max(len(hours_stock_status)) AS stock_max_length,
       count(*) FILTER (WHERE hours_sale IS NULL) AS sale_null_lists,
       count(*) FILTER (WHERE hours_stock_status IS NULL) AS stock_null_lists,
       sum(len(hours_sale)-list_count(hours_sale)) AS sale_null_elements,
       sum(len(hours_stock_status)-list_count(hours_stock_status)) AS stock_null_elements,
       sum(list_count(list_filter(hours_sale, x -> NOT isfinite(x)))) AS sale_nonfinite_elements,
       sum(list_count(list_filter(hours_sale, x -> x<0))) AS sale_negative_elements,
       sum(list_count(list_filter(hours_stock_status, x -> x NOT IN (0,1)))) AS stock_invalid_elements,
       max(abs(sale_amount-list_sum(hours_sale))) AS max_daily_hourly_sales_difference,
       count(*) FILTER (WHERE abs(sale_amount-list_sum(hours_sale)) > 1e-9 + 1e-12*abs(sale_amount)) AS daily_hourly_sales_mismatches,
       count(*) FILTER (WHERE stock_hour6_22_cnt != list_sum(list_slice(hours_stock_status,7,22))) AS stock_count_mismatches_06_22_exclusive,
       count(*) FILTER (WHERE stock_hour6_22_cnt != list_sum(list_slice(hours_stock_status,7,23))) AS stock_count_mismatches_06_22_inclusive,
       sum(list_sum(hours_stock_status)) AS stockout_hour_slots_24h,
       sum(len(hours_stock_status)) AS total_hour_slots_24h,
       sum(stock_hour6_22_cnt) AS stockout_hour_slots_06_22,
       count(*)*16 AS total_hour_slots_06_22,
       count(*) FILTER (WHERE stock_hour6_22_cnt=0 AND list_sum(hours_stock_status)>0) AS stockout_only_outside_06_22
FROM raw GROUP BY GROUPING SETS ((source_split), ()) ORDER BY scope;
