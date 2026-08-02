SELECT stock_code, demand_date, count(*) AS duplicate_count
FROM {{ ref('mart_sku_daily_demand') }}
GROUP BY 1, 2
HAVING count(*) > 1
