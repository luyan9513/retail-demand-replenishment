"""提供显式、可复现的数据质量导出与项目运行入口。"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from src.train import run_training


def export_quality_audit(database_path: Path, sql_path: Path, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    query = sql_path.read_text(encoding="utf-8")
    with duckdb.connect(str(database_path), read_only=True) as connection:
        audit = connection.execute(query).fetchdf()
    audit.to_csv(output_path, index=False)
    return len(audit)


def main() -> None:
    parser = argparse.ArgumentParser(description="导出审计并执行预测训练；导入与 dbt run 需先分别完成")
    parser.add_argument("--database", type=Path, default=Path("data/retail.duckdb"))
    parser.add_argument("--quality-sql", type=Path, default=Path("sql/01_quality_checks.sql"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--top-skus", type=int, default=30, choices=range(20, 51))
    args = parser.parse_args()
    audit_count = export_quality_audit(args.database, args.quality_sql, args.output_dir / "quality_audit.csv")
    result = run_training(args.database, args.output_dir, args.top_skus)
    print(f"质量审计指标={audit_count}; " + ", ".join(f"{key}={value}" for key, value in result.items()))


if __name__ == "__main__":
    main()
