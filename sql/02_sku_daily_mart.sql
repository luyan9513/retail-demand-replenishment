-- mart 生成后的核验查询：每个 SKU×日应至多一行，并显示分层关键统计。
SELECT
    stock_code,
    min(demand_date) AS first_demand_date,
    max(demand_date) AS last_demand_date,
    count(*) AS calendar_days,
    sum(CASE WHEN daily_qty > 0 THEN 1 ELSE 0 END) AS nonzero_days,
    sum(daily_qty) AS total_qty,
    sum(daily_revenue) AS total_revenue,
    max(demand_segment) AS demand_segment,
    max(nonzero_day_rate) AS nonzero_day_rate,
    max(demand_cv) AS demand_cv
FROM mart_sku_daily_demand
GROUP BY stock_code
ORDER BY total_revenue DESC;
