SELECT
    source_row_number,
    invoice_no,
    stock_code,
    description,
    quantity,
    invoice_date,
    unit_price,
    customer_id,
    country,
    quantity * unit_price AS line_revenue
FROM {{ ref('int_sales_line_flags') }}
WHERE NOT is_cancellation
  AND NOT is_invalid_quantity
  AND NOT is_invalid_price
  AND NOT is_missing_sku
  AND NOT is_missing_invoice_date
  AND duplicate_rank = 1
