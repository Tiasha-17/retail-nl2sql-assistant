from pathlib import Path

import pytest

from retail_nl2sql.examples import CuratedGenerator
from retail_nl2sql.executor import QueryExecutor
from retail_nl2sql.pipeline import NL2SQLPipeline
from retail_nl2sql.schema import inspect_schema

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = PROJECT_ROOT / "data" / "retail_star_schema.db"


@pytest.fixture(scope="session")
def database_path() -> Path:
    assert DATABASE.is_file(), "Run build_star_schema.py before the test suite"
    return DATABASE


@pytest.fixture(scope="session")
def schema(database_path: Path):
    return inspect_schema(database_path, sample_rows=2)


@pytest.fixture()
def pipeline(database_path: Path, schema):
    return NL2SQLPipeline(
        schema=schema,
        generator=CuratedGenerator(),
        executor=QueryExecutor(database_path, max_rows=100, timeout_ms=2000),
    )
