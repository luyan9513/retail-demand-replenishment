WITH base AS (
    SELECT * FROM {{ ref('stg_online_retail') }}
)
SELECT
    *,
    starts_with(upper(coalesce(invoice_no, '')), 'C') AS is_cancellation,
    quantity IS NULL OR quantity <= 0 AS is_invalid_quantity,
    unit_price IS NULL OR unit_price <= 0 AS is_invalid_price,
    stock_code IS NULL OR stock_code = '' AS is_missing_sku,
    invoice_date IS NULL AS is_missing_invoice_date,
    row_number() OVER (
        PARTITION BY invoice_no, stock_code, description, quantity, invoice_date, unit_price, customer_id, country
        ORDER BY source_row_number
    ) AS duplicate_rank
FROM base
