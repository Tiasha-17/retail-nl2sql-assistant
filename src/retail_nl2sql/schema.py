"""Read a compact, LLM-friendly schema snapshot from SQLite."""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXPECTED_TABLES = frozenset(
    {
        "fact_order_items",
        "fact_payments",
        "fact_reviews",
        "dim_customers",
        "dim_products",
        "dim_sellers",
        "dim_date",
    }
)


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


@dataclass(frozen=True)
class SchemaSnapshot:
    tables: dict[str, dict[str, Any]]

    @property
    def table_names(self) -> frozenset[str]:
        return frozenset(self.tables)

    def to_prompt(self) -> str:
        return json.dumps(self.tables, indent=2, ensure_ascii=True, default=str)


def _read_only_uri(database_path: Path) -> str:
    return f"{database_path.resolve().as_uri()}?mode=ro"


def inspect_schema(database_path: Path, sample_rows: int = 2) -> SchemaSnapshot:
    """Inspect only the seven application tables and a few representative rows."""

    path = database_path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Database not found: {path}")

    tables: dict[str, dict[str, Any]] = {}
    with sqlite3.connect(_read_only_uri(path), uri=True) as connection:
        connection.row_factory = sqlite3.Row
        found = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        missing = EXPECTED_TABLES - found
        if missing:
            raise ValueError(f"Database is missing required tables: {sorted(missing)}")

        for table_name in sorted(EXPECTED_TABLES):
            quoted = quote_identifier(table_name)
            columns = [
                {
                    "name": row[1],
                    "type": row[2] or "ANY",
                    "nullable": not bool(row[3]),
                    "primary_key_position": row[5],
                }
                for row in connection.execute(f"PRAGMA table_info({quoted})")
            ]
            foreign_keys = [
                {"from": row[3], "to_table": row[2], "to_column": row[4]}
                for row in connection.execute(f"PRAGMA foreign_key_list({quoted})")
            ]
            examples: list[dict[str, Any]] = []
            if sample_rows:
                examples = [
                    dict(row)
                    for row in connection.execute(f"SELECT * FROM {quoted} LIMIT ?", (sample_rows,))
                ]
            tables[table_name] = {
                "columns": columns,
                "foreign_keys": foreign_keys,
                "example_rows": examples,
            }

    return SchemaSnapshot(tables=tables)
