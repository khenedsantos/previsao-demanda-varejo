-- Fase 2: a tabela train já está limitada ao arquivo train e à data de corte.
-- Nenhuma consulta deste arquivo abre arquivos ou acessa eval.
-- name: daily_features
SELECT *, isodow(dt)::INTEGER AS weekday, date_trunc('week', dt)::DATE AS week_start,
       stock_hour6_22_cnt > 0 AS stockout,
       lag(sale_amount, 7) OVER series_time AS demand_lag7,
       lag(dt, 7) OVER series_time AS date_lag7,
       sum(CASE WHEN stock_hour6_22_cnt = 0 THEN 1 ELSE 0 END)
           OVER series_time AS stockout_run,
       sum(CASE WHEN sale_amount > 0 THEN 1 ELSE 0 END)
           OVER series_time AS zero_run
FROM train
WINDOW series_time AS (PARTITION BY store_id, product_id ORDER BY dt);

-- name: weekly
SELECT store_id, product_id, week_start, count(*) AS n_days,
       sum(sale_amount) AS weekly_demand, avg(sale_amount) AS mean_daily_demand,
       avg(stockout::INTEGER) AS stockout_rate
FROM daily GROUP BY store_id, product_id, week_start HAVING count(*) = 7;

-- name: weekday
SELECT store_id, product_id, weekday, count(*) AS n_days,
       avg(sale_amount) AS mean_demand,
       avg(stockout::INTEGER) AS stockout_rate,
       avg(activity_flag) AS activity_rate
FROM daily GROUP BY store_id, product_id, weekday;

-- name: stability
-- Cada semana completa é normalizada pela própria média: avalia forma, não nível.
WITH ordered AS (
    SELECT *, row_number() OVER (PARTITION BY store_id,product_id ORDER BY week_start) AS week_number,
           count(*) OVER (PARTITION BY store_id,product_id) AS n_weeks
    FROM weekly
), halves AS (
    SELECT d.store_id,d.product_id,d.weekday,
           CASE WHEN w.week_number <= floor(w.n_weeks/2.0) THEN 1 ELSE 2 END AS half,
           avg(d.sale_amount/w.mean_daily_demand) AS relative_mean,
           count(*) AS n_weeks
    FROM daily d JOIN ordered w USING(store_id,product_id,week_start)
    WHERE w.mean_daily_demand > $epsilon
    GROUP BY d.store_id,d.product_id,d.weekday,half
), paired AS (
    SELECT store_id,product_id,weekday,
           max(relative_mean) FILTER(WHERE half=1) AS early,
           max(relative_mean) FILTER(WHERE half=2) AS late,
           coalesce(max(n_weeks) FILTER(WHERE half=1),0) AS early_weeks,
           coalesce(max(n_weeks) FILTER(WHERE half=2),0) AS late_weeks
    FROM halves GROUP BY store_id,product_id,weekday
)
SELECT store_id,product_id,min(early_weeks) AS early_valid_weeks,min(late_weeks) AS late_valid_weeks,
       CASE WHEN count(early)=7 AND count(late)=7 AND min(early_weeks)>=2 AND min(late_weeks)>=2
                 AND stddev_samp(early)>$epsilon AND stddev_samp(late)>$epsilon
            THEN corr(early,late) END AS weekly_pattern_half_correlation,
       CASE WHEN count(early)=7 AND count(late)=7 AND min(early_weeks)>=2 AND min(late_weeks)>=2
            THEN avg(abs(early-late)) END AS weekly_pattern_half_mae
FROM paired GROUP BY store_id,product_id;

-- name: profile
WITH base AS (
    SELECT store_id,product_id,min(dt) AS first_date,max(dt) AS last_date,count(*) AS n_days,
           avg(sale_amount) AS mean_demand,median(sale_amount) AS median_demand,
           stddev_samp(sale_amount) AS std_demand,min(sale_amount) AS min_demand,
           max(sale_amount) AS max_demand,sum(sale_amount) AS total_demand,
           count(*) FILTER(WHERE sale_amount=0) AS zero_days,
           count(*) FILTER(WHERE sale_amount>0) AS positive_days,
           avg((sale_amount=0)::INTEGER) AS zero_ratio,
           avg(sale_amount) FILTER(WHERE sale_amount>0) AS positive_mean_demand,
           stddev_samp(sale_amount) FILTER(WHERE sale_amount>0) AS positive_std_demand,
           count(*) FILTER(WHERE stockout) AS stockout_days,
           avg(stockout::INTEGER) AS stockout_rate,
           sum(stock_hour6_22_cnt) AS total_stockout_hours,
           avg(stock_hour6_22_cnt) FILTER(WHERE stockout) AS mean_stockout_hours_when_affected,
           count(*) FILTER(WHERE sale_amount=0 AND stockout) AS zero_days_with_stockout,
           count(*) FILTER(WHERE sale_amount=0 AND NOT stockout) AS zero_days_without_stockout,
           avg(sale_amount) FILTER(WHERE stockout) AS mean_demand_with_stockout,
           avg(sale_amount) FILTER(WHERE NOT stockout) AS mean_demand_without_stockout,
           sum(activity_flag) AS activity_days,avg(activity_flag) AS activity_rate,
           avg(discount) AS mean_discount,
           count(*) FILTER(WHERE discount>0 AND discount<1) AS discount_days,
           count(*) FILTER(WHERE discount=0) AS discount_zero_days,
           count(*) FILTER(WHERE discount>1) AS discount_above_one_days,
           avg(sale_amount) FILTER(WHERE activity_flag=1) AS mean_demand_with_activity,
           avg(sale_amount) FILTER(WHERE activity_flag=0) AS mean_demand_without_activity,
           avg(stockout::INTEGER) FILTER(WHERE activity_flag=1) AS stockout_rate_with_activity,
           avg(stockout::INTEGER) FILTER(WHERE activity_flag=0) AS stockout_rate_without_activity,
           avg(sale_amount) FILTER(WHERE weekday<=5) AS weekday_mean_demand,
           avg(sale_amount) FILTER(WHERE weekday>=6) AS weekend_mean_demand,
           count(*) FILTER(WHERE date_diff('day',date_lag7,dt)=7) AS lag7_pairs,
           CASE WHEN lag7_pairs>=3
                 AND stddev_samp(sale_amount) FILTER(WHERE date_diff('day',date_lag7,dt)=7)>$epsilon
                 AND stddev_samp(demand_lag7) FILTER(WHERE date_diff('day',date_lag7,dt)=7)>$epsilon
                THEN corr(sale_amount,demand_lag7) FILTER(WHERE date_diff('day',date_lag7,dt)=7)
           END AS autocorrelation_lag7
    FROM daily GROUP BY store_id,product_id
), runs AS (
    SELECT store_id,product_id,max(run_length) AS maximum_consecutive_stockout_days
    FROM (SELECT store_id,product_id,stockout_run,count(*) AS run_length
          FROM daily WHERE stockout GROUP BY store_id,product_id,stockout_run)
    GROUP BY store_id,product_id
), zero_runs AS (
    SELECT store_id,product_id,max(run_length) AS maximum_consecutive_zero_days
    FROM (SELECT store_id,product_id,zero_run,count(*) AS run_length
          FROM daily WHERE sale_amount=0 GROUP BY store_id,product_id,zero_run)
    GROUP BY store_id,product_id
), weeks AS (
    SELECT store_id,product_id,count(*) AS complete_weeks,avg(weekly_demand) AS mean_weekly_demand,
           stddev_samp(weekly_demand) AS std_weekly_demand
    FROM weekly GROUP BY store_id,product_id
), weekday_wide AS (
    SELECT store_id,product_id,
           max(mean_demand) FILTER(WHERE weekday=1) AS mean_demand_monday,
           max(mean_demand) FILTER(WHERE weekday=2) AS mean_demand_tuesday,
           max(mean_demand) FILTER(WHERE weekday=3) AS mean_demand_wednesday,
           max(mean_demand) FILTER(WHERE weekday=4) AS mean_demand_thursday,
           max(mean_demand) FILTER(WHERE weekday=5) AS mean_demand_friday,
           max(mean_demand) FILTER(WHERE weekday=6) AS mean_demand_saturday,
           max(mean_demand) FILTER(WHERE weekday=7) AS mean_demand_sunday
    FROM weekday GROUP BY store_id,product_id
)
SELECT b.*,'train' AS source_split,
       mean_demand<=$epsilon AS near_zero_mean,
       CASE WHEN mean_demand>$epsilon THEN std_demand/mean_demand END AS coefficient_of_variation,
       n_days::DOUBLE/nullif(positive_days,0) AS adi,
       CASE WHEN positive_mean_demand>$epsilon THEN pow(positive_std_demand/positive_mean_demand,2) END AS positive_demand_cv_squared,
       coalesce(r.maximum_consecutive_stockout_days,0) AS maximum_consecutive_stockout_days,
       coalesce(z.maximum_consecutive_zero_days,0) AS maximum_consecutive_zero_days,
       mean_demand_with_stockout-mean_demand_without_stockout AS stockout_demand_difference,
       mean_demand_with_activity-mean_demand_without_activity AS activity_demand_difference,
       stockout_rate_with_activity-stockout_rate_without_activity AS activity_stockout_rate_difference,
       weekend_mean_demand-weekday_mean_demand AS weekend_weekday_difference,
       CASE WHEN weekday_mean_demand>$epsilon THEN weekend_mean_demand/weekday_mean_demand-1 END AS weekend_weekday_relative_difference,
       coalesce(w.complete_weeks,0) AS complete_weeks,w.mean_weekly_demand,w.std_weekly_demand,
       CASE WHEN w.mean_weekly_demand>$epsilon THEN w.std_weekly_demand/w.mean_weekly_demand END AS weekly_coefficient_of_variation,
       coalesce(s.early_valid_weeks,0) AS early_valid_weeks,
       coalesce(s.late_valid_weeks,0) AS late_valid_weeks,s.weekly_pattern_half_correlation,s.weekly_pattern_half_mae,
       wd.* EXCLUDE(store_id,product_id)
FROM base b LEFT JOIN runs r USING(store_id,product_id)
LEFT JOIN zero_runs z USING(store_id,product_id)
LEFT JOIN weeks w USING(store_id,product_id)
LEFT JOIN stability s USING(store_id,product_id)
LEFT JOIN weekday_wide wd USING(store_id,product_id);
