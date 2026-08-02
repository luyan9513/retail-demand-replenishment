-- DuckDB 数据质量审计：每条规则都保留为可输出指标，而非静默过滤。
WITH raw AS (
    SELECT * FROM raw_transactions
), flags AS (
    SELECT
        *,
        starts_with(upper(coalesce(invoice_no, '')), 'C') AS is_cancellation,
        quantity IS NULL OR quantity <= 0 AS is_invalid_quantity,
        unit_price IS NULL OR unit_price <= 0 AS is_invalid_price,
        stock_code IS NULL OR trim(stock_code) = '' AS is_missing_sku,
        invoice_date IS NULL AS is_missing_invoice_date,
        row_number() OVER (
            PARTITION BY invoice_no, stock_code, description, quantity, invoice_date, unit_price, customer_id, country
            ORDER BY source_row_number
        ) AS duplicate_rank
    FROM raw
), valid_dates AS (
    SELECT DISTINCT CAST(invoice_date AS DATE) AS demand_date
    FROM flags
    WHERE NOT is_cancellation AND NOT is_invalid_quantity AND NOT is_invalid_price
      AND NOT is_missing_sku AND NOT is_missing_invoice_date AND duplicate_rank = 1
), date_coverage AS (
    SELECT
        CASE WHEN count(*) = 0 THEN 0
             ELSE date_diff('day', min(demand_date), max(demand_date)) + 1 - count(*) END AS missing_calendar_dates
    FROM valid_dates
), valid_sales AS (
    SELECT * FROM flags
    WHERE NOT is_cancellation AND NOT is_invalid_quantity AND NOT is_invalid_price
      AND NOT is_missing_sku AND NOT is_missing_invoice_date AND duplicate_rank = 1
), sku_daily AS (
    SELECT stock_code, CAST(invoice_date AS DATE) AS demand_date, sum(quantity) AS daily_qty
    FROM valid_sales GROUP BY 1, 2
), sku_span AS (
    SELECT stock_code, count(*) AS observed_days,
           date_diff('day', min(demand_date), max(demand_date)) + 1 AS calendar_days
    FROM sku_daily GROUP BY 1
)
SELECT 'raw_rows' AS metric, count(*)::DOUBLE AS value, '全部导入行数' AS definition FROM flags
UNION ALL SELECT 'cancellation_rows', count(*)::DOUBLE, 'Invoice 以 C 开头的取消单行数' FROM flags WHERE is_cancellation
UNION ALL SELECT 'cancellation_row_rate', count(*) FILTER (WHERE is_cancellation)::DOUBLE / nullif(count(*), 0), '取消单行数/全部导入行数' FROM flags
UNION ALL SELECT 'invalid_quantity_rows', count(*)::DOUBLE, '数量为空或小于等于 0 的行数' FROM flags WHERE is_invalid_quantity
UNION ALL SELECT 'invalid_price_rows', count(*)::DOUBLE, '单价为空或小于等于 0 的行数' FROM flags WHERE is_invalid_price
UNION ALL SELECT 'missing_sku_rows', count(*)::DOUBLE, 'SKU 为空的行数' FROM flags WHERE is_missing_sku
UNION ALL SELECT 'missing_invoice_date_rows', count(*)::DOUBLE, '交易日期为空的行数' FROM flags WHERE is_missing_invoice_date
UNION ALL SELECT 'candidate_duplicate_rows', count(*)::DOUBLE, '同一候选业务键重复的额外行数；需结合业务确认是否为重复录入' FROM flags WHERE duplicate_rank > 1
UNION ALL SELECT 'valid_positive_sales_rows', count(*)::DOUBLE, '进入正向需求计算的有效行数' FROM valid_sales
UNION ALL SELECT 'missing_calendar_dates', missing_calendar_dates::DOUBLE, '有效销售全局日期范围内未出现交易的日期数（不等于 SKU 补零后缺失）' FROM date_coverage
UNION ALL SELECT 'sparse_sku_count_30pct', count(*)::DOUBLE, '非零天占比低于 30% 的 SKU 数' FROM sku_span WHERE observed_days::DOUBLE / nullif(calendar_days, 0) < 0.30;
