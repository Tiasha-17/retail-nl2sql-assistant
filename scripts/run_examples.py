#!/usr/bin/env python3
"""Run five fixed questions through the actual validation and execution pipeline."""

import json
from pathlib import Path

from retail_nl2sql.examples import EXAMPLES, CuratedGenerator
from retail_nl2sql.executor import QueryExecutor
from retail_nl2sql.pipeline import NL2SQLPipeline
from retail_nl2sql.schema import inspect_schema

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = PROJECT_ROOT / "data" / "retail_star_schema.db"


def main() -> None:
    schema = inspect_schema(DATABASE, sample_rows=2)
    pipeline = NL2SQLPipeline(
        schema=schema,
        generator=CuratedGenerator(),
        executor=QueryExecutor(DATABASE, max_rows=100, timeout_ms=2000),
    )
    for example in EXAMPLES:
        response = pipeline.ask(example.question)
        print(f"\n## {response.question}\n")
        print("```sql")
        print(response.sql)
        print("```")
        print(json.dumps(response.result.rows, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
