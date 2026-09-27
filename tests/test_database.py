import sqlite3

EXPECTED_COUNTS = {
    "fact_order_items": 112_650,
    "fact_payments": 103_886,
    "fact_reviews": 99_224,
    "dim_customers": 99_441,
    "dim_products": 32_951,
    "dim_sellers": 3_095,
    "dim_date": 634,
}


def test_database_counts_and_foreign_keys(database_path):
    with sqlite3.connect(database_path) as connection:
        counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in EXPECTED_COUNTS
        }
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()

    assert counts == EXPECTED_COUNTS
    assert violations == []


def test_database_stays_below_repository_limit(database_path):
    assert database_path.stat().st_size < 50 * 1024 * 1024
