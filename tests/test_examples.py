import pytest

from retail_nl2sql.examples import EXAMPLES


@pytest.mark.parametrize(
    ("question", "first_row"),
    [
        (
            EXAMPLES[0].question,
            {"category": "health_beauty", "revenue": 1_258_681.34},
        ),
        (
            EXAMPLES[1].question,
            {"seller_state": "PA", "avg_review_score": 4.5, "reviews": 8},
        ),
        (
            EXAMPLES[2].question,
            {"year": 2018, "month": 1, "month_name": "January", "revenue": 950_030.36},
        ),
        (
            EXAMPLES[3].question,
            {"customer_state": "MA", "delivered_items": 800, "late_delivery_pct": 20.38},
        ),
        (
            EXAMPLES[4].question,
            {
                "payment_type": "credit_card",
                "payment_records": 76_795,
                "payment_value": 12_542_084.19,
            },
        ),
    ],
)
def test_curated_questions_run_end_to_end(pipeline, question, first_row):
    response = pipeline.ask(question)

    assert response.result.rows[0] == first_row
    assert response.sql.lstrip().upper().startswith(("SELECT", "WITH"))
    assert response.answer.startswith("The query returned")
