WITH sku_value AS (
    SELECT stock_code, sum(daily_revenue) AS sku_revenue
    FROM {{ ref('int_sku_daily_base') }}
    GROUP BY 1
), selected_skus AS (
    SELECT stock_code, sku_revenue
    FROM sku_value
    ORDER BY sku_revenue DESC
    LIMIT 30
), bounds AS (
    SELECT b.stock_code, min(b.demand_date) AS first_date, max(b.demand_date) AS last_date
    FROM {{ ref('int_sku_daily_base') }} b
    INNER JOIN selected_skus s USING (stock_code)
    GROUP BY 1
), spine AS (
    SELECT b.stock_code, CAST(d.demand_date AS DATE) AS demand_date
    FROM bounds b,
    unnest(generate_series(b.first_date, b.last_date, INTERVAL 1 DAY)) AS d(demand_date)
), daily AS (
    SELECT
        s.stock_code,
        s.demand_date,
        coalesce(b.daily_qty, 0.0) AS daily_qty,
        coalesce(b.daily_revenue, 0.0) AS daily_revenue,
        coalesce(b.daily_orders, 0) AS daily_orders
    FROM spine s
    LEFT JOIN {{ ref('int_sku_daily_base') }} b USING (stock_code, demand_date)
), with_lag AS (
    SELECT *, lag(daily_qty, 7) OVER (PARTITION BY stock_code ORDER BY demand_date) AS lag_7_qty
    FROM daily
), gap_source AS (
    SELECT stock_code, demand_date,
           lag(demand_date) OVER (PARTITION BY stock_code ORDER BY demand_date) AS previous_nonzero_date
    FROM daily WHERE daily_qty > 0
), gap_stats AS (
    SELECT stock_code, avg(date_diff('day', previous_nonzero_date, demand_date)) AS avg_nonzero_gap_days
    FROM gap_source GROUP BY 1
), sku_stats AS (
    SELECT
        d.stock_code,
        max(s.sku_revenue) AS sku_revenue,
        avg(CASE WHEN d.daily_qty > 0 THEN 1.0 ELSE 0.0 END) AS nonzero_day_rate,
        avg(d.daily_qty) AS daily_qty_mean,
        stddev_pop(d.daily_qty) AS daily_qty_std,
        stddev_pop(d.daily_qty) / nullif(avg(d.daily_qty), 0) AS demand_cv,
        corr(d.daily_qty, d.lag_7_qty) AS lag7_correlation,
        max(g.avg_nonzero_gap_days) AS avg_nonzero_gap_days
    FROM with_lag d
    INNER JOIN selected_skus s USING (stock_code)
    LEFT JOIN gap_stats g USING (stock_code)
    GROUP BY 1
), thresholds AS (
    SELECT quantile_cont(sku_revenue, 0.75) AS high_value_revenue_cutoff FROM sku_stats
), classified AS (
    SELECT
        ss.*,
        CASE
            WHEN nonzero_day_rate < 0.30 OR coalesce(avg_nonzero_gap_days, 999) > 5 THEN '间歇/长尾型'
            WHEN sku_revenue >= t.high_value_revenue_cutoff AND demand_cv >= 1.20 THEN '高价值高波动型'
            WHEN lag7_correlation >= 0.35 THEN '周期型'
            ELSE '稳定型'
        END AS demand_segment
    FROM sku_stats ss CROSS JOIN thresholds t
)
SELECT
    d.*,
    dayofweek(d.demand_date) AS day_of_week,
    month(d.demand_date) AS month,
    c.sku_revenue,
    c.nonzero_day_rate,
    c.avg_nonzero_gap_days,
    c.daily_qty_mean,
    c.daily_qty_std,
    c.demand_cv,
    c.lag7_correlation,
    c.demand_segment
FROM daily d
INNER JOIN classified c USING (stock_code)
