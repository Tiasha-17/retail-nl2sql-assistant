"""FastAPI entry point."""

import logging
import sqlite3

from fastapi import FastAPI, HTTPException
from openai import OpenAIError

from .config import Settings
from .executor import QueryExecutor, QueryTimedOut
from .guardrails import QueryRejected
from .llm import OllamaSQLGenerator, OpenAISQLGenerator, SQLGenerator
from .models import AskRequest, AskResponse, HealthResponse
from .pipeline import NL2SQLPipeline
from .schema import inspect_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(
    settings: Settings | None = None,
    generator: SQLGenerator | None = None,
) -> FastAPI:
    settings = settings or Settings()
    database_path = settings.resolved_database_path()
    schema = inspect_schema(database_path, settings.schema_sample_rows)
    provider = settings.llm_provider.casefold()
    if generator is not None:
        sql_generator = generator
    elif provider == "ollama":
        sql_generator = OllamaSQLGenerator(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    elif provider == "openai":
        sql_generator = OpenAISQLGenerator(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
        )
    else:
        raise ValueError(f"Unsupported RETAIL_LLM_PROVIDER: {settings.llm_provider}")
    pipeline = NL2SQLPipeline(
        schema=schema,
        generator=sql_generator,
        executor=QueryExecutor(
            database_path,
            max_rows=settings.max_rows,
            timeout_ms=settings.query_timeout_ms,
        ),
    )

    application = FastAPI(
        title="Retail NL2SQL Assistant",
        version="0.1.0",
        description="Guarded natural-language analytics over the Olist retail star schema.",
    )

    @application.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"service": "Retail NL2SQL Assistant", "docs": "/docs"}

    @application.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            database=database_path.name,
            llm_configured=provider == "ollama" or bool(settings.openai_api_key),
            llm_provider=provider,
            llm_model=(settings.ollama_model if provider == "ollama" else settings.openai_model),
        )

    @application.post("/ask", response_model=AskResponse)
    def ask(request: AskRequest) -> AskResponse:
        try:
            return pipeline.ask(request.question)
        except QueryRejected as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except QueryTimedOut as error:
            raise HTTPException(status_code=408, detail=str(error)) from error
        except OpenAIError as error:
            raise HTTPException(
                status_code=503, detail="SQL generation service unavailable"
            ) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except sqlite3.Error as error:
            raise HTTPException(
                status_code=422, detail=f"Query execution failed: {error}"
            ) from error

    application.state.pipeline = pipeline
    return application


app = create_app()
