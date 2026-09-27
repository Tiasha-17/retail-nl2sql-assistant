# Data

The application uses the **Brazilian E-Commerce Public Dataset by Olist**, published on
Kaggle: <https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>.

`retail_star_schema.db` is a derived SQLite artifact purpose-built for this project. It
contains seven tables at three fact grains: order line items, payment records, and reviews.
The raw CSVs are intentionally excluded from Git.

To rebuild the database:

```bash
kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip
python build_star_schema.py
```

The builder validates the expected source row counts, foreign keys, and SQLite integrity
before completing. Paths are resolved from the script location, so the command does not
depend on the caller's current working directory.

