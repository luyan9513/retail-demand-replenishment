"""使用合成交易数据验证 Excel/CSV 导入、dbt build、训练和候选重复敏感性链路。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd

from src.ingest import ingest_to_duckdb, read_source
from src.run_pipeline import export_quality_audit
from src.train import run_training


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _synthetic_transactions() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    dates = pd.date_range("2024-01-01", periods=70, freq="D")
    for sku, multiplier in (("A", 1), ("B", 2)):
        for index, date in enumerate(dates):
            rows.append({
                "Invoice": f"{sku}{index:04d}", "StockCode": sku, "Description": f"SKU {sku}",
                "Quantity": (index % 5 + 1) * multiplier, "InvoiceDate": date,
                "Price": 2.0, "Customer ID": 1000 + index, "Country": "United Kingdom",
            })
    rows.append(rows[0].copy())  # 候选重复：默认口径保留，严格口径排除。
    rows.append({"Invoice": "C0001", "StockCode": "A", "Description": "cancel", "Quantity": -2,
                 "InvoiceDate": dates[0], "Price": 2.0, "Customer ID": 1, "Country": "United Kingdom"})
    return pd.DataFrame(rows)


def _profile(database_path: Path) -> str:
    return f"""retail_demand:
  target: test
  outputs:
    test:
      type: duckdb
      path: {database_path.as_posix()}
      schema: main
      threads: 1
"""


def test_ingest_reads_all_excel_sheets(tmp_path):
    workbook = tmp_path / "input.xlsx"
    with pd.ExcelWriter(workbook) as writer:
        _synthetic_transactions().head(2).to_excel(writer, sheet_name="year_one", index=False)
        _synthetic_transactions().tail(2).to_excel(writer, sheet_name="year_two", index=False)
    frame = read_source(workbook)
    assert len(frame) == 4
    assert set(frame["source_sheet"]) == {"year_one", "year_two"}


def test_synthetic_end_to_end_data_to_forecast_pipeline(tmp_path):
    raw_path = tmp_path / "transactions.csv"
    database_path = tmp_path / "retail.duckdb"
    output_dir = tmp_path / "processed"
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    _synthetic_transactions().to_csv(raw_path, index=False)
    assert ingest_to_duckdb(raw_path, database_path) == 142
    (profile_dir / "profiles.yml").write_text(_profile(database_path), encoding="utf-8")
    dbt = Path(sys.executable).parent / "dbt"
    subprocess.run(
        [str(dbt), "build", "--project-dir", str(PROJECT_ROOT / "dbt"), "--profiles-dir", str(profile_dir)],
        check=True, cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    result = run_training(database_path, output_dir, top_skus=2)
    assert result["candidate_skus"] == 2
    assert result["future_rows"] == 14
    assert (output_dir / "model_metrics.csv").exists()
    sensitivity_rows = export_quality_audit(database_path, PROJECT_ROOT / "sql/03_duplicate_sensitivity.sql", output_dir / "duplicate_sensitivity.csv")
    assert sensitivity_rows == 9
    audit = pd.read_csv(output_dir / "duplicate_sensitivity.csv").set_index("metric")
    assert audit.loc["candidate_duplicate_row_impact", "value"] == 1
    with duckdb.connect(str(database_path), read_only=True) as connection:
        assert connection.execute("select count(*) from int_valid_sales_lines").fetchone()[0] == 141
        assert connection.execute("select count(*) from int_valid_sales_lines_deduped").fetchone()[0] == 140
