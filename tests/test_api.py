from fastapi.testclient import TestClient

from retail_nl2sql.api import create_app
from retail_nl2sql.config import Settings
from retail_nl2sql.examples import EXAMPLES, CuratedGenerator


def test_health(database_path):
    app = create_app(
        Settings(database_path=database_path, schema_sample_rows=0),
        generator=CuratedGenerator(),
    )
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ask_returns_answer_sql_and_rows(database_path):
    app = create_app(
        Settings(database_path=database_path, schema_sample_rows=1),
        generator=CuratedGenerator(),
    )
    response = TestClient(app).post("/ask", json={"question": EXAMPLES[0].question})

    assert response.status_code == 200
    payload = response.json()
    assert payload["sql"].startswith("SELECT")
    assert payload["result"]["rows"][0]["category"] == "health_beauty"


def test_blank_question_is_validation_error(database_path):
    app = create_app(
        Settings(database_path=database_path, schema_sample_rows=0),
        generator=CuratedGenerator(),
    )
    response = TestClient(app).post("/ask", json={"question": ""})
    assert response.status_code == 422
