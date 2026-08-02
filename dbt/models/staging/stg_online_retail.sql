SELECT
    CAST(source_row_number AS BIGINT) AS source_row_number,
    trim(CAST(source_sheet AS VARCHAR)) AS source_sheet,
    trim(CAST(invoice_no AS VARCHAR)) AS invoice_no,
    trim(CAST(stock_code AS VARCHAR)) AS stock_code,
    trim(CAST(description AS VARCHAR)) AS description,
    CAST(quantity AS DOUBLE) AS quantity,
    CAST(invoice_date AS TIMESTAMP) AS invoice_date,
    CAST(unit_price AS DOUBLE) AS unit_price,
    trim(CAST(customer_id AS VARCHAR)) AS customer_id,
    trim(CAST(country AS VARCHAR)) AS country
FROM {{ source('raw', 'raw_transactions') }}
