"""Curated questions used to verify the real pipeline without spending API credits."""

from dataclasses import dataclass

from .models import SQLDraft
from .schema import SchemaSnapshot


@dataclass(frozen=True)
class CuratedExample:
    question: str
    sql: str
    rationale: str


EXAMPLES = (
    CuratedExample(
        question="Which five product categories generated the most item revenue?",
        sql="""
            SELECT
                COALESCE(p.product_category_name_english, 'unknown') AS category,
                ROUND(SUM(i.price), 2) AS revenue
            FROM fact_order_items AS i
            JOIN dim_products AS p USING (product_key)
            GROUP BY category
            ORDER BY revenue DESC
            LIMIT 5
        """,
        rationale="Sum item price by translated product category and rank descending.",
    ),
    CuratedExample(
        question="Which five seller states have the highest average review score?",
        sql="""
            WITH seller_reviews AS (
                SELECT DISTINCT r.review_key, i.seller_key, r.review_score
                FROM fact_reviews AS r
                JOIN fact_order_items AS i USING (order_key)
            )
            SELECT
                s.seller_state,
                ROUND(AVG(sr.review_score), 2) AS avg_review_score,
                COUNT(*) AS reviews
            FROM seller_reviews AS sr
            JOIN dim_sellers AS s USING (seller_key)
            GROUP BY s.seller_state
            ORDER BY avg_review_score DESC, reviews DESC
            LIMIT 5
        """,
        rationale="Deduplicate review-seller pairs before averaging scores by seller state.",
    ),
    CuratedExample(
        question="What was item revenue by month in 2018?",
        sql="""
            SELECT
                d.year,
                d.month,
                d.month_name,
                ROUND(SUM(i.price), 2) AS revenue
            FROM fact_order_items AS i
            JOIN dim_date AS d ON d.date_key = i.purchase_date_key
            WHERE d.year = 2018
            GROUP BY d.year, d.month, d.month_name
            ORDER BY d.month
        """,
        rationale="Join the date dimension and aggregate item price for each 2018 month.",
    ),
    CuratedExample(
        question="Which customer states have the highest late-delivery rate with 500+ items?",
        sql="""
            SELECT
                c.customer_state,
                COUNT(*) AS delivered_items,
                ROUND(100.0 * AVG(i.is_late), 2) AS late_delivery_pct
            FROM fact_order_items AS i
            JOIN dim_customers AS c USING (customer_key)
            WHERE i.is_late IS NOT NULL
            GROUP BY c.customer_state
            HAVING COUNT(*) >= 500
            ORDER BY late_delivery_pct DESC
            LIMIT 5
        """,
        rationale="Average the binary late flag by customer state after a volume threshold.",
    ),
    CuratedExample(
        question="How much payment value came through each payment type?",
        sql="""
            SELECT
                payment_type,
                COUNT(*) AS payment_records,
                ROUND(SUM(payment_value), 2) AS payment_value
            FROM fact_payments
            GROUP BY payment_type
            ORDER BY payment_value DESC
        """,
        rationale="Aggregate payment record count and value by payment type.",
    ),
)


class CuratedGenerator:
    """A deterministic generator for repeatable demos and end-to-end tests."""

    def __init__(self, examples: tuple[CuratedExample, ...] = EXAMPLES) -> None:
        self._examples = {example.question: example for example in examples}

    def generate(self, question: str, schema: SchemaSnapshot) -> SQLDraft:
        del schema
        try:
            example = self._examples[question]
        except KeyError as error:
            raise ValueError(f"No curated query is available for: {question}") from error
        return SQLDraft(sql=example.sql, rationale=example.rationale)
