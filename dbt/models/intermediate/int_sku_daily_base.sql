SELECT
    stock_code,
    CAST(invoice_date AS DATE) AS demand_date,
    sum(quantity) AS daily_qty,
    sum(line_revenue) AS daily_revenue,
    count(DISTINCT invoice_no) AS daily_orders
FROM {{ ref('int_valid_sales_lines') }}
GROUP BY 1, 2
