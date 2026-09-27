#!/usr/bin/env python3
"""Build the seven-table Olist retail star schema from the public source CSVs."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
EXPECTED_COUNTS = {
    "fact_order_items": 112_650,
    "fact_payments": 103_886,
    "fact_reviews": 99_224,
    "dim_customers": 99_441,
    "dim_products": 32_951,
    "dim_sellers": 3_095,
    "dim_date": 634,
}


def read_csv(path: Path) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def required_files(input_dir: Path) -> dict[str, Path]:
    names = {
        "customers": "olist_customers_dataset.csv",
        "items": "olist_order_items_dataset.csv",
        "payments": "olist_order_payments_dataset.csv",
        "reviews": "olist_order_reviews_dataset.csv",
        "orders": "olist_orders_dataset.csv",
        "products": "olist_products_dataset.csv",
        "sellers": "olist_sellers_dataset.csv",
        "translations": "product_category_name_translation.csv",
    }
    paths = {key: input_dir / name for key, name in names.items()}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required CSV files:\n" + "\n".join(missing))
    return paths


def optional_int(value: str) -> int | None:
    return int(float(value)) if value else None


def optional_float(value: str) -> float | None:
    return float(value) if value else None


def parse_timestamp(value: str) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def date_key(timestamp: str) -> int:
    return int(timestamp[:10].replace("-", ""))


def create_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE dim_customers (
            customer_key INTEGER PRIMARY KEY,
            customer_id TEXT NOT NULL,
            customer_unique_id TEXT NOT NULL,
            customer_city TEXT NOT NULL,
            customer_state TEXT NOT NULL,
            customer_zip_code_prefix INTEGER NOT NULL
        );

        CREATE TABLE dim_products (
            product_key INTEGER PRIMARY KEY,
            product_id TEXT NOT NULL,
            product_category_name TEXT,
            product_category_name_english TEXT,
            product_weight_g REAL,
            product_length_cm REAL,
            product_height_cm REAL,
            product_width_cm REAL,
            product_photos_qty INTEGER
        );

        CREATE TABLE dim_sellers (
            seller_key INTEGER PRIMARY KEY,
            seller_id TEXT NOT NULL,
            seller_city TEXT NOT NULL,
            seller_state TEXT NOT NULL,
            seller_zip_code_prefix INTEGER NOT NULL
        );

        CREATE TABLE dim_date (
            date_key INTEGER PRIMARY KEY,
            full_date TEXT NOT NULL UNIQUE,
            year INTEGER NOT NULL,
            quarter INTEGER NOT NULL,
            month INTEGER NOT NULL,
            month_name TEXT NOT NULL,
            day INTEGER NOT NULL,
            weekday INTEGER NOT NULL,
            weekday_name TEXT NOT NULL,
            is_weekend INTEGER NOT NULL CHECK (is_weekend IN (0, 1))
        );

        CREATE TABLE fact_order_items (
            order_key INTEGER NOT NULL,
            order_item_id INTEGER NOT NULL,
            customer_key INTEGER NOT NULL,
            product_key INTEGER NOT NULL,
            seller_key INTEGER NOT NULL,
            purchase_date_key INTEGER NOT NULL,
            order_status TEXT NOT NULL,
            price REAL NOT NULL,
            freight_value REAL NOT NULL,
            delivery_days REAL,
            is_late INTEGER CHECK (is_late IN (0, 1) OR is_late IS NULL),
            PRIMARY KEY (order_key, order_item_id),
            FOREIGN KEY (customer_key) REFERENCES dim_customers(customer_key),
            FOREIGN KEY (product_key) REFERENCES dim_products(product_key),
            FOREIGN KEY (seller_key) REFERENCES dim_sellers(seller_key),
            FOREIGN KEY (purchase_date_key) REFERENCES dim_date(date_key)
        ) WITHOUT ROWID;

        CREATE TABLE fact_payments (
            order_key INTEGER NOT NULL,
            payment_sequential INTEGER NOT NULL,
            customer_key INTEGER NOT NULL,
            purchase_date_key INTEGER NOT NULL,
            payment_type TEXT NOT NULL,
            payment_installments INTEGER NOT NULL,
            payment_value REAL NOT NULL,
            PRIMARY KEY (order_key, payment_sequential),
            FOREIGN KEY (customer_key) REFERENCES dim_customers(customer_key),
            FOREIGN KEY (purchase_date_key) REFERENCES dim_date(date_key)
        ) WITHOUT ROWID;

        CREATE TABLE fact_reviews (
            review_key INTEGER PRIMARY KEY,
            order_key INTEGER NOT NULL,
            customer_key INTEGER NOT NULL,
            purchase_date_key INTEGER NOT NULL,
            review_score INTEGER NOT NULL CHECK (review_score BETWEEN 1 AND 5),
            review_creation_date TEXT NOT NULL,
            review_answer_timestamp TEXT NOT NULL,
            FOREIGN KEY (customer_key) REFERENCES dim_customers(customer_key),
            FOREIGN KEY (purchase_date_key) REFERENCES dim_date(date_key)
        );
        """
    )


def insert_dimensions(
    connection: sqlite3.Connection, paths: dict[str, Path]
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    translations = {
        row["product_category_name"]: row["product_category_name_english"]
        for row in read_csv(paths["translations"])
    }

    customer_rows = []
    customer_keys: dict[str, int] = {}
    for key, row in enumerate(read_csv(paths["customers"]), start=1):
        customer_keys[row["customer_id"]] = key
        customer_rows.append(
            (
                key,
                row["customer_id"],
                row["customer_unique_id"],
                row["customer_city"],
                row["customer_state"],
                int(row["customer_zip_code_prefix"]),
            )
        )
    connection.executemany("INSERT INTO dim_customers VALUES (?, ?, ?, ?, ?, ?)", customer_rows)

    product_rows = []
    product_keys: dict[str, int] = {}
    for key, row in enumerate(read_csv(paths["products"]), start=1):
        product_keys[row["product_id"]] = key
        product_rows.append(
            (
                key,
                row["product_id"],
                row["product_category_name"] or None,
                translations.get(row["product_category_name"]),
                optional_float(row["product_weight_g"]),
                optional_float(row["product_length_cm"]),
                optional_float(row["product_height_cm"]),
                optional_float(row["product_width_cm"]),
                optional_int(row["product_photos_qty"]),
            )
        )
    connection.executemany(
        "INSERT INTO dim_products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        product_rows,
    )

    seller_rows = []
    seller_keys: dict[str, int] = {}
    for key, row in enumerate(read_csv(paths["sellers"]), start=1):
        seller_keys[row["seller_id"]] = key
        seller_rows.append(
            (
                key,
                row["seller_id"],
                row["seller_city"],
                row["seller_state"],
                int(row["seller_zip_code_prefix"]),
            )
        )
    connection.executemany("INSERT INTO dim_sellers VALUES (?, ?, ?, ?, ?)", seller_rows)
    return customer_keys, product_keys, seller_keys


OrderLookup = dict[str, dict[str, Any]]


def insert_dates_and_load_orders(
    connection: sqlite3.Connection,
    orders_path: Path,
    customer_keys: dict[str, int],
) -> OrderLookup:
    orders: OrderLookup = {}
    dates: set[str] = set()
    for order_key, row in enumerate(read_csv(orders_path), start=1):
        purchase_timestamp = row["order_purchase_timestamp"]
        purchase_date = purchase_timestamp[:10]
        dates.add(purchase_date)
        purchased = parse_timestamp(purchase_timestamp)
        delivered = parse_timestamp(row["order_delivered_customer_date"])
        estimated = parse_timestamp(row["order_estimated_delivery_date"])
        delivery_days = None
        is_late = None
        if purchased and delivered:
            delivery_days = round((delivered - purchased).total_seconds() / 86_400, 3)
        if delivered and estimated:
            is_late = int(delivered > estimated)
        orders[row["order_id"]] = {
            "order_key": order_key,
            "customer_key": customer_keys[row["customer_id"]],
            "date_key": date_key(purchase_timestamp),
            "order_status": row["order_status"],
            "delivery_days": delivery_days,
            "is_late": is_late,
        }

    date_rows = []
    for value in sorted(dates):
        day = datetime.fromisoformat(value)
        date_rows.append(
            (
                int(value.replace("-", "")),
                value,
                day.year,
                ((day.month - 1) // 3) + 1,
                day.month,
                day.strftime("%B"),
                day.day,
                day.weekday(),
                day.strftime("%A"),
                int(day.weekday() >= 5),
            )
        )
    connection.executemany("INSERT INTO dim_date VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", date_rows)
    return orders


def insert_facts(
    connection: sqlite3.Connection,
    paths: dict[str, Path],
    orders: OrderLookup,
    product_keys: dict[str, int],
    seller_keys: dict[str, int],
) -> None:
    connection.executemany(
        "INSERT INTO fact_order_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            (
                orders[row["order_id"]]["order_key"],
                int(row["order_item_id"]),
                orders[row["order_id"]]["customer_key"],
                product_keys[row["product_id"]],
                seller_keys[row["seller_id"]],
                orders[row["order_id"]]["date_key"],
                orders[row["order_id"]]["order_status"],
                float(row["price"]),
                float(row["freight_value"]),
                orders[row["order_id"]]["delivery_days"],
                orders[row["order_id"]]["is_late"],
            )
            for row in read_csv(paths["items"])
        ),
    )
    connection.executemany(
        "INSERT INTO fact_payments VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            (
                orders[row["order_id"]]["order_key"],
                int(row["payment_sequential"]),
                orders[row["order_id"]]["customer_key"],
                orders[row["order_id"]]["date_key"],
                row["payment_type"],
                int(row["payment_installments"]),
                float(row["payment_value"]),
            )
            for row in read_csv(paths["payments"])
        ),
    )
    connection.executemany(
        "INSERT INTO fact_reviews VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            (
                review_key,
                orders[row["order_id"]]["order_key"],
                orders[row["order_id"]]["customer_key"],
                orders[row["order_id"]]["date_key"],
                int(row["review_score"]),
                row["review_creation_date"],
                row["review_answer_timestamp"],
            )
            for review_key, row in enumerate(read_csv(paths["reviews"]), start=1)
        ),
    )


def create_indexes(connection: sqlite3.Connection) -> None:
    statements: Iterable[str] = (
        "CREATE INDEX idx_items_customer ON fact_order_items(customer_key)",
        "CREATE INDEX idx_items_product ON fact_order_items(product_key)",
        "CREATE INDEX idx_items_seller ON fact_order_items(seller_key)",
        "CREATE INDEX idx_items_date ON fact_order_items(purchase_date_key)",
        "CREATE INDEX idx_payments_customer ON fact_payments(customer_key)",
        "CREATE INDEX idx_payments_date ON fact_payments(purchase_date_key)",
        "CREATE INDEX idx_reviews_order ON fact_reviews(order_key)",
        "CREATE INDEX idx_reviews_customer ON fact_reviews(customer_key)",
        "CREATE INDEX idx_reviews_date ON fact_reviews(purchase_date_key)",
        "CREATE INDEX idx_products_category ON dim_products(product_category_name_english)",
        "CREATE INDEX idx_customers_state ON dim_customers(customer_state)",
        "CREATE INDEX idx_sellers_state ON dim_sellers(seller_state)",
    )
    for statement in statements:
        connection.execute(statement)


def validate_database(connection: sqlite3.Connection) -> None:
    actual = {
        table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in EXPECTED_COUNTS
    }
    if actual != EXPECTED_COUNTS:
        raise RuntimeError(f"Unexpected row counts. Expected {EXPECTED_COUNTS}; got {actual}")

    violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"Foreign key violations detected: {violations[:5]}")

    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"SQLite integrity check failed: {integrity}")


def build_database(input_dir: Path, output_path: Path, *, with_indexes: bool = True) -> None:
    paths = required_files(input_dir.resolve())
    output = output_path.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    connection = sqlite3.connect(output)
    try:
        connection.execute("PRAGMA journal_mode = OFF")
        connection.execute("PRAGMA synchronous = OFF")
        connection.execute("PRAGMA temp_store = MEMORY")
        with connection:
            create_tables(connection)
            customer_keys, product_keys, seller_keys = insert_dimensions(connection, paths)
            orders = insert_dates_and_load_orders(connection, paths["orders"], customer_keys)
            insert_facts(connection, paths, orders, product_keys, seller_keys)
            if with_indexes:
                create_indexes(connection)
            validate_database(connection)
            connection.execute("ANALYZE")
        connection.execute("VACUUM")
        validate_database(connection)
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw",
        help="Directory containing the Olist source CSVs",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "retail_star_schema.db",
        help="Destination SQLite database",
    )
    parser.add_argument(
        "--skip-indexes",
        action="store_true",
        help="Build without analytical indexes (smaller, slower database)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    build_database(arguments.input_dir, arguments.output, with_indexes=not arguments.skip_indexes)
    size_mb = arguments.output.resolve().stat().st_size / (1024 * 1024)
    print(f"Built {arguments.output.resolve()} ({size_mb:.2f} MiB)")
