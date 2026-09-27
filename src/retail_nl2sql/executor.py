"""Bounded query execution over a defense-in-depth read-only SQLite connection."""

import sqlite3
import time
from pathlib import Path
from typing import Any

from .models import QueryResult


class QueryTimedOut(TimeoutError):
    """Raised when SQLite exceeds the configured execution deadline."""


class QueryExecutor:
    def __init__(self, database_path: Path, *, max_rows: int, timeout_ms: int) -> None:
        self.database_path = database_path.resolve()
        self.max_rows = max_rows
        self.timeout_ms = timeout_ms
        if not self.database_path.is_file():
            raise FileNotFoundError(f"Database not found: {self.database_path}")

    def _connect(self) -> sqlite3.Connection:
        uri = f"{self.database_path.as_uri()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    def execute(self, sql: str) -> QueryResult:
        started = time.monotonic()
        deadline = started + (self.timeout_ms / 1000)
        wrapped = f"SELECT * FROM ({sql.rstrip().rstrip(';')}) AS bounded_query LIMIT ?"

        with self._connect() as connection:
            connection.set_progress_handler(
                lambda: 1 if time.monotonic() >= deadline else 0,
                1000,
            )
            try:
                cursor = connection.execute(wrapped, (self.max_rows + 1,))
                fetched = cursor.fetchall()
            except sqlite3.OperationalError as error:
                if "interrupted" in str(error).casefold():
                    raise QueryTimedOut(
                        f"Query exceeded the {self.timeout_ms} ms execution limit"
                    ) from error
                raise
            finally:
                connection.set_progress_handler(None, 0)

        elapsed_ms = (time.monotonic() - started) * 1000
        truncated = len(fetched) > self.max_rows
        rows = fetched[: self.max_rows]
        columns = [description[0] for description in cursor.description or []]
        serialized: list[dict[str, Any]] = [dict(row) for row in rows]
        return QueryResult(
            columns=columns,
            rows=serialized,
            row_count=len(serialized),
            truncated=truncated,
            elapsed_ms=round(elapsed_ms, 2),
        )
