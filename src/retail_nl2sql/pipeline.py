"""End-to-end question, generation, validation, execution, and answer pipeline."""

import json
import logging

from .executor import QueryExecutor
from .guardrails import validate_read_only_query
from .llm import SQLGenerator
from .models import AskResponse, QueryResult
from .schema import SchemaSnapshot

logger = logging.getLogger("retail_nl2sql.query")


def format_answer(result: QueryResult) -> str:
    if not result.rows:
        return "No matching rows were found."
    if result.row_count == 1 and len(result.columns) == 1:
        value = result.rows[0][result.columns[0]]
        return f"The result is {value}."

    qualifier = "at least " if result.truncated else ""
    first_row = result.rows[0]
    preview = ", ".join(f"{column}={first_row[column]}" for column in result.columns[:3])
    suffix = " The displayed table is capped." if result.truncated else ""
    return (
        f"The query returned {qualifier}{result.row_count} rows. "
        f"The first row is {preview}.{suffix}"
    )


class NL2SQLPipeline:
    def __init__(
        self,
        *,
        schema: SchemaSnapshot,
        generator: SQLGenerator,
        executor: QueryExecutor,
    ) -> None:
        self.schema = schema
        self.generator = generator
        self.executor = executor

    def ask(self, question: str) -> AskResponse:
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("Question must not be blank")

        draft = self.generator.generate(clean_question, self.schema)
        validated = validate_read_only_query(draft.sql, self.schema.table_names)
        result = self.executor.execute(validated.sql)
        answer = format_answer(result)

        logger.info(
            "nl2sql_query %s",
            json.dumps(
                {
                    "question": clean_question,
                    "sql": validated.sql,
                    "row_count": result.row_count,
                    "truncated": result.truncated,
                    "elapsed_ms": result.elapsed_ms,
                },
                ensure_ascii=True,
            ),
        )
        return AskResponse(
            question=clean_question,
            answer=answer,
            sql=validated.sql,
            rationale=draft.rationale,
            result=result,
        )
