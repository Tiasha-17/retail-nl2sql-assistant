import json

from retail_nl2sql.llm import OllamaSQLGenerator
from retail_nl2sql.schema import SchemaSnapshot


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "message": {
                "content": json.dumps(
                    {
                        "sql": "SELECT COUNT(*) AS orders FROM fact_order_items",
                        "rationale": "Count rows in the order-item fact table.",
                    }
                )
            }
        }


def test_ollama_generator_uses_native_structured_output(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("retail_nl2sql.llm.httpx.post", fake_post)
    generator = OllamaSQLGenerator(model="qwen2.5:7b-instruct")
    draft = generator.generate("How many order items are there?", SchemaSnapshot(tables={}))

    assert draft.sql.startswith("SELECT COUNT")
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["json"]["model"] == "qwen2.5:7b-instruct"
    assert captured["json"]["format"]["required"] == ["sql", "rationale"]
    assert captured["json"]["stream"] is False
