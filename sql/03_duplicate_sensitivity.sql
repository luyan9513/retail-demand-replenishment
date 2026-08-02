-- 候选重复敏感性：默认口径保留候选重复，严格口径仅保留 duplicate_rank=1。
WITH flags AS (
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
    FROM raw_transactions
), base AS (
    SELECT * FROM flags
    WHERE NOT is_cancellation
      AND NOT is_invalid_quantity
      AND NOT is_invalid_price
      AND NOT is_missing_sku
      AND NOT is_missing_invoice_date
), summary AS (
    SELECT
        count(*)::DOUBLE AS included_rows,
        sum(quantity)::DOUBLE AS included_qty,
        sum(quantity * unit_price)::DOUBLE AS included_revenue,
        count(*) FILTER (WHERE duplicate_rank = 1)::DOUBLE AS strict_rows,
        sum(quantity) FILTER (WHERE duplicate_rank = 1)::DOUBLE AS strict_qty,
        sum(quantity * unit_price) FILTER (WHERE duplicate_rank = 1)::DOUBLE AS strict_revenue
    FROM base
)
SELECT 'default_including_candidate_duplicates_rows' AS metric, included_rows AS value,
       '默认正向需求行数：候选重复保留，等待订单行 ID 或业务确认' AS definition FROM summary
UNION ALL SELECT 'strict_deduped_rows', strict_rows,
       '严格候选去重后行数：仅保留 duplicate_rank=1' FROM summary
UNION ALL SELECT 'candidate_duplicate_row_impact', included_rows - strict_rows,
       '候选重复对正向需求行数的影响' FROM summary
UNION ALL SELECT 'default_including_candidate_duplicates_qty', included_qty,
       '默认口径正向成交量' FROM summary
UNION ALL SELECT 'strict_deduped_qty', strict_qty,
       '严格候选去重后成交量' FROM summary
UNION ALL SELECT 'candidate_duplicate_qty_impact', included_qty - strict_qty,
       '候选重复对成交量的影响；不是确认的重复录入损失' FROM summary
UNION ALL SELECT 'default_including_candidate_duplicates_revenue', included_revenue,
       '默认口径正向成交销售额' FROM summary
UNION ALL SELECT 'strict_deduped_revenue', strict_revenue,
       '严格候选去重后销售额' FROM summary
UNION ALL SELECT 'candidate_duplicate_revenue_impact', included_revenue - strict_revenue,
       '候选重复对销售额的影响；需业务确认后才能选择严格口径' FROM summary;
