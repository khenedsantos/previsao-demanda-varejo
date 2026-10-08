-- As views/tabelas são registradas pelo pipeline somente após validar proveniência train.
-- name: product_totals
SELECT product_id,sum(sale_amount) AS normalized_sales_total,
       count(DISTINCT store_id) AS associated_series
FROM train_sales GROUP BY product_id ORDER BY product_id;

-- name: abc_xyz_matrix
WITH grid AS (
    SELECT a.abc_class,x.xyz_class FROM (VALUES ('A'),('B'),('C')) a(abc_class)
    CROSS JOIN (VALUES ('X'),('Y'),('Z')) x(xyz_class)
), grouped AS (
    SELECT abc_class,xyz_class,count(*) AS n_series,count(DISTINCT product_id) AS n_products,
           sum(total_demand) AS normalized_sales_total,
           avg(stockout_rate) AS mean_stockout_rate,median(stockout_rate) AS median_stockout_rate,
           count(*) FILTER(WHERE censoring_risk_flag) AS censoring_risk_count,
           avg(censoring_risk_flag::INTEGER) AS censoring_risk_share,
           count(*) FILTER(WHERE stockout_exposure='HIGH') AS high_exposure_count
    FROM operational GROUP BY abc_class,xyz_class
)
SELECT grid.*,coalesce(n_series,0) AS n_series,coalesce(n_products,0) AS n_products,
       coalesce(normalized_sales_total,0) AS normalized_sales_total,
       coalesce(normalized_sales_total,0)/(SELECT sum(total_demand) FROM operational) AS normalized_sales_share,
       mean_stockout_rate,median_stockout_rate,coalesce(censoring_risk_count,0) AS censoring_risk_count,
       censoring_risk_share,coalesce(high_exposure_count,0) AS high_exposure_count
FROM grid LEFT JOIN grouped USING(abc_class,xyz_class) ORDER BY abc_class,xyz_class;

-- name: exposure_cube
SELECT abc_class,xyz_class,stockout_exposure,count(*) AS n_series,
       sum(total_demand) AS normalized_sales_total,
       sum(total_demand)/(SELECT sum(total_demand) FROM operational) AS normalized_sales_share,
       avg(stockout_rate) AS mean_stockout_rate,
       count(*) FILTER(WHERE censoring_risk_flag) AS censoring_risk_count
FROM operational GROUP BY abc_class,xyz_class,stockout_exposure
ORDER BY abc_class,xyz_class,stockout_exposure;
