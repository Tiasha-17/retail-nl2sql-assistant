import sqlite3

import pytest

from retail_nl2sql.executor import QueryExecutor, QueryTimedOut
from retail_nl2sql.guardrails import QueryRejected, validate_read_only_query
from retail_nl2sql.models import SQLDraft
from retail_nl2sql.pipeline import NL2SQLPipeline


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM fact_order_items",
        "DROP TABLE fact_order_items",
        "SELECT 1; DELETE FROM fact_order_items",
        "PRAGMA table_info(fact_order_items)",
        "SELECT * FROM sqlite_master",
    ],
)
def test_rejects_non_allow_listed_sql(schema, sql):
    with pytest.raises(QueryRejected):
        validate_read_only_query(sql, schema.table_names)


def test_allows_a_read_only_cte(schema):
    validated = validate_read_only_query(
        "WITH totals AS (SELECT SUM(price) AS revenue FROM fact_order_items) "
        "SELECT revenue FROM totals",
        schema.table_names,
    )
    assert validated.sql.startswith("WITH")


class DestructiveGenerator:
    def generate(self, question, schema):
        del question, schema
        return SQLDraft(sql="DELETE FROM fact_order_items", rationale="destructive test")


class FailingExecutor:
    def execute(self, sql):
        raise AssertionError(f"Executor must never be called; received {sql}")


def test_destructive_prompt_is_rejected_before_database(schema):
    pipeline = NL2SQLPipeline(
        schema=schema,
        generator=DestructiveGenerator(),
        executor=FailingExecutor(),
    )
    with pytest.raises(QueryRejected):
        pipeline.ask("delete all late orders")


def test_database_connection_is_read_only(database_path):
    executor = QueryExecutor(database_path, max_rows=10, timeout_ms=1000)
    with executor._connect() as connection, pytest.raises(sqlite3.OperationalError):
        connection.execute("DELETE FROM fact_order_items")


def test_result_size_is_capped(database_path):
    result = QueryExecutor(database_path, max_rows=7, timeout_ms=1000).execute(
        "SELECT order_key FROM fact_order_items"
    )
    assert result.row_count == 7
    assert result.truncated is True


def test_runaway_query_times_out(database_path):
    executor = QueryExecutor(database_path, max_rows=10, timeout_ms=10)
    with pytest.raises(QueryTimedOut):
        executor.execute(
            "SELECT COUNT(*) FROM fact_order_items AS a CROSS JOIN fact_order_items AS b"
        )
