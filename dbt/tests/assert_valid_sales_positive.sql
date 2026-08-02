SELECT *
FROM {{ ref('int_valid_sales_lines') }}
WHERE quantity <= 0 OR unit_price <= 0
