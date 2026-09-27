"""Typed request, response, and internal data models."""

from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class SQLDraft(BaseModel):
    sql: str = Field(description="Exactly one read-only SQLite query")
    rationale: str = Field(description="A short explanation of how the query answers the question")


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    elapsed_ms: float


class AskResponse(BaseModel):
    question: str
    answer: str
    sql: str
    rationale: str
    result: QueryResult


class HealthResponse(BaseModel):
    status: str
    database: str
    llm_configured: bool
    llm_provider: str
    llm_model: str
