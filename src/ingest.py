"""将 UCI Online Retail II 文件标准化后写入本项目 DuckDB。"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import pandas as pd


CANONICAL_COLUMNS = {
    "invoice": "invoice_no", "invoiceno": "invoice_no", "invoice_no": "invoice_no",
    "stockcode": "stock_code", "stock_code": "stock_code",
    "description": "description",
    "quantity": "quantity",
    "invoicedate": "invoice_date", "invoice_date": "invoice_date",
    "price": "unit_price", "unitprice": "unit_price", "unit_price": "unit_price",
    "customerid": "customer_id", "customer_id": "customer_id",
    "country": "country",
}
REQUIRED_COLUMNS = {"invoice_no", "stock_code", "quantity", "invoice_date", "unit_price"}


def normalize_name(name: str) -> str:
    return "".join(char.lower() for char in str(name) if char.isalnum() or char == "_")


def read_source(path: Path, sheet_name: str | int | None = None) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=sheet_name if sheet_name is not None else None)
        if isinstance(sheets, dict):
            source = pd.concat(
                [frame.assign(source_sheet=str(name)) for name, frame in sheets.items()],
                ignore_index=True,
            )
        else:
            source = sheets.assign(source_sheet=str(sheet_name))
    elif path.suffix.lower() == ".csv":
        source = pd.read_csv(path).assign(source_sheet="csv")
    else:
        raise ValueError("仅支持 .xlsx、.xls 或 .csv 数据文件")
    rename_map = {column: CANONICAL_COLUMNS.get(normalize_name(column), normalize_name(column)) for column in source.columns}
    source = source.rename(columns=rename_map)
    missing = REQUIRED_COLUMNS - set(source.columns)
    if missing:
        raise ValueError(f"文件缺少必要字段：{sorted(missing)}；实际字段为：{list(source.columns)}")
    source.insert(0, "source_row_number", range(1, len(source) + 1))
    for column in ("invoice_no", "stock_code", "description", "customer_id", "country"):
        if column not in source:
            source[column] = None
    source["invoice_no"] = source["invoice_no"].astype("string").str.strip()
    source["stock_code"] = source["stock_code"].astype("string").str.strip()
    source["invoice_date"] = pd.to_datetime(source["invoice_date"], errors="coerce")
    source["quantity"] = pd.to_numeric(source["quantity"], errors="coerce")
    source["unit_price"] = pd.to_numeric(source["unit_price"], errors="coerce")
    return source[["source_row_number", "source_sheet", "invoice_no", "stock_code", "description", "quantity", "invoice_date", "unit_price", "customer_id", "country"]]


def ingest_to_duckdb(input_path: Path, database_path: Path, sheet_name: str | int | None = None) -> int:
    frame = read_source(input_path, sheet_name)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database_path)) as connection:
        connection.register("source_frame", frame)
        connection.execute("CREATE OR REPLACE TABLE raw_transactions AS SELECT * FROM source_frame")
        connection.execute("CREATE OR REPLACE TABLE raw_ingestion_metadata AS SELECT ? AS input_path, ? AS ingested_at, ? AS row_count", [str(input_path), pd.Timestamp.utcnow(), len(frame)])
    return len(frame)


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 UCI Online Retail II 到 DuckDB")
    parser.add_argument("--input", required=True, type=Path, help="UCI 数据文件路径（Excel 或 CSV）")
    parser.add_argument("--database", type=Path, default=Path("data/retail.duckdb"))
    parser.add_argument("--sheet", default=None, help="Excel sheet 名或序号；默认第一张")
    args = parser.parse_args()
    sheet: str | int | None = int(args.sheet) if args.sheet and args.sheet.isdigit() else args.sheet
    row_count = ingest_to_duckdb(args.input, args.database, sheet)
    print(f"已导入 {row_count:,} 行到 {args.database}")


if __name__ == "__main__":
    main()
