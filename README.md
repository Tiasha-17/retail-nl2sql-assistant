# Retail NL2SQL Assistant

Ask plain-English retail questions and receive guarded SQL, a readable answer, and the
supporting rows from a purpose-built Olist star schema.

```bash
ollama pull qwen2.5:7b-instruct
cp .env.example .env
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .
.venv/bin/uvicorn retail_nl2sql.api:app --reload
```

Open <http://127.0.0.1:8000/docs> for the interactive API documentation.

## What it does

The service turns a retail analytics question into one schema-aware SQLite query, validates
the query before execution, runs it against a read-only connection, and returns:

- a plain-English summary;
- the normalized SQL, so the result is auditable;
- the model's short rationale; and
- column names, result rows, truncation state, and query time.

Only table definitions, relationships, column types, and two example rows per table are sent
to the model. The raw CSV files are never placed in the prompt.

## Example questions and answers

These are copied from real runs of `python scripts/run_examples.py`. The script uses a fixed
SQL generator so the same five questions exercise the real schema inspection, parser,
guardrails, read-only executor, logging, and result formatter without API cost.

### 1. Which five product categories generated the most item revenue?

```sql
SELECT
  COALESCE(p.product_category_name_english, 'unknown') AS category,
  ROUND(SUM(i.price), 2) AS revenue
FROM fact_order_items AS i
JOIN dim_products AS p USING (product_key)
GROUP BY category
ORDER BY revenue DESC
LIMIT 5
```

Health and beauty led with **$1,258,681.34** in item revenue.

| category | revenue |
|---|---:|
| health_beauty | 1,258,681.34 |
| watches_gifts | 1,205,005.68 |
| bed_bath_table | 1,036,988.68 |
| sports_leisure | 988,048.97 |
| computers_accessories | 911,954.32 |

### 2. Which five seller states have the highest average review score?

```sql
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
```

PA ranked first at 4.50, although its sample was only eight reviews.

| seller_state | avg_review_score | reviews |
|---|---:|---:|
| PA | 4.50 | 8 |
| MS | 4.46 | 48 |
| GO | 4.31 | 461 |
| RS | 4.28 | 1,984 |
| RN | 4.27 | 51 |

### 3. What was item revenue by month in 2018?

```sql
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
```

April was the highest complete month at **$996,647.75**, closely followed by May. September
contains only $145 because the public order history ends in 2018.

### 4. Which customer states have the highest late-delivery rate with 500+ items?

```sql
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
```

MA had the highest qualifying late-delivery rate at **20.38%** across 800 delivered items.

| customer_state | delivered_items | late_delivery_pct |
|---|---:|---:|
| MA | 800 | 20.38% |
| PI | 523 | 15.49% |
| CE | 1,426 | 15.29% |
| BA | 3,683 | 13.68% |
| RJ | 14,146 | 12.97% |

### 5. How much payment value came through each payment type?

```sql
SELECT
  payment_type,
  COUNT(*) AS payment_records,
  ROUND(SUM(payment_value), 2) AS payment_value
FROM fact_payments
GROUP BY payment_type
ORDER BY payment_value DESC
```

Credit cards dominated with **$12,542,084.19** across 76,795 payment records.

| payment_type | payment_records | payment_value |
|---|---:|---:|
| credit_card | 76,795 | 12,542,084.19 |
| boleto | 19,784 | 2,869,361.27 |
| voucher | 5,775 | 379,436.87 |
| debit_card | 1,529 | 217,989.79 |
| not_defined | 3 | 0.00 |

## Engineering decisions

The safety boundary does not rely on the model behaving well:

1. **Structured generation.** Local Ollama is the default provider and enforces the Pydantic
   `SQLDraft` JSON schema through its native structured-output endpoint. An optional OpenAI
   adapter uses the Responses API. Provider and model selection are environment-controlled.
2. **Parse and allow-list.** `sqlglot` must parse exactly one SQLite query. The root must be a
   query, mutating AST nodes are rejected, CTE names are resolved, and every physical table
   must belong to the seven-table allow-list. `sqlite_master`, PRAGMAs, and second statements
   are rejected.
3. **Read-only execution.** SQLite opens the database with `mode=ro` and also enables
   `PRAGMA query_only`. A write still fails at the database layer if an earlier check regresses.
4. **Bounded work.** Every query is wrapped in an outer limit and fetched with one sentinel
   row, producing an honest `truncated` flag. A SQLite progress handler interrupts work after
   `RETAIL_QUERY_TIMEOUT_MS`.
5. **Auditable output.** Each successful request logs the question, normalized SQL, returned
   row count, truncation state, and execution time. API responses include the SQL and rows.
6. **Physical star design.** Integer surrogate keys prevent long source identifiers from being
   repeated through fact tables. The fully indexed database is 41 MiB, below the 50 MiB target.

The local adapter follows Ollama's structured-output design:
<https://docs.ollama.com/capabilities/structured-outputs>.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Database and API-key readiness |
| `POST` | `/ask` | Generate, validate, and execute one analytics query |
| `GET` | `/docs` | Interactive OpenAPI documentation |

Request:

```bash
curl -s http://127.0.0.1:8000/ask \
  -H 'content-type: application/json' \
  -d '{"question":"Which five product categories generated the most item revenue?"}'
```

Response shape:

```json
{
  "question": "Which five product categories generated the most item revenue?",
  "answer": "The query returned 5 rows. The first row is category=health_beauty, revenue=1258681.34.",
  "sql": "SELECT ...",
  "rationale": "Sum item price by translated product category and rank descending.",
  "result": {
    "columns": ["category", "revenue"],
    "rows": [{"category": "health_beauty", "revenue": 1258681.34}],
    "row_count": 5,
    "truncated": false,
    "elapsed_ms": 22.4
  }
}
```

## Tech stack

- Python 3.11+
- FastAPI and Uvicorn
- Local Ollama structured outputs, with optional OpenAI Responses support
- SQLite in read-only mode
- sqlglot for AST validation
- pytest and Ruff
- Docker and GitHub Actions

All Python package versions are pinned in `requirements.txt`.

## Repository layout

```text
.
├── .github/workflows/ci.yml
├── data/
│   ├── README.md
│   └── retail_star_schema.db
├── scripts/run_examples.py
├── src/retail_nl2sql/
│   ├── api.py
│   ├── executor.py
│   ├── guardrails.py
│   ├── llm.py
│   ├── pipeline.py
│   └── schema.py
├── tests/
├── build_star_schema.py
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

## Running it

### Local API

Use the quickstart at the top of this README. The default configuration talks to Ollama at
`http://127.0.0.1:11434` and requires no paid API key. To use OpenAI instead, set
`RETAIL_LLM_PROVIDER=openai`, `OPENAI_API_KEY`, and `OPENAI_MODEL` in `.env`.

```bash
.venv/bin/python scripts/run_examples.py
.venv/bin/pytest tests/ -v
.venv/bin/ruff check .
```

### Docker

```bash
docker build -t retail-nl2sql .
docker run --rm -p 8000:8000 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  --env-file .env retail-nl2sql
```

The host override is required because `127.0.0.1` inside Docker refers to the container,
not the host running Ollama.

### Rebuild the data

Place the eight required Olist CSVs plus the category translation CSV in `data/raw/`, then:

```bash
.venv/bin/python build_star_schema.py
```

The builder recreates the database, restores indexes, validates exact row counts and foreign
keys, runs `PRAGMA integrity_check`, and compacts the file.

## What I would do next

- Add a small Streamlit client that renders the answer, SQL, and result table side by side.
- Store an evaluation set and track execution accuracy separately from exact SQL matching.
- Add per-client rate limits and authenticated request tracing before public deployment.
- Extend the semantic layer with metric definitions for revenue, orders, and delivery SLAs.

## Data

The source is the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
This repository ships a derived, purpose-built seven-table SQLite star schema; raw CSVs are
gitignored. See `data/README.md` for reproduction details.

## Licence

Code is released under the [MIT License](LICENSE). The Olist dataset remains subject to its
source terms.
