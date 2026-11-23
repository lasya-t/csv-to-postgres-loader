# CSV to Postgres Loader

A CLI that looks at a CSV, works out a Postgres schema, creates the table, and bulk-loads the file with `COPY`. If anything fails, nothing is left half-loaded.

## What it does

1. **Sniffs the file**: delimiter (`,` `;` tab `|`), header, and a byte-order mark from Excel exports.
2. **Infers types from a sample** (5,000 rows by default). Each column starts at the narrowest type and widens when a value doesn't fit:
   - `boolean → integer → bigint → numeric → text`
   - `date → timestamp → text`
   - Values with leading zeros like `02139` stay **text**, so ZIP codes and phone numbers keep their zeros.
   - `""`, `NA`, `null` and `-` become SQL `NULL`.
3. **Cleans column names**: `Order ID` → `order_id`, duplicates get `_2`, and names starting with a digit get a prefix.
4. **Loads with `COPY ... FROM STDIN`** in a single transaction. A malformed row raises an error with its line number and rolls back the whole load, so no partial table is left behind.
5. **Modes**: `create`, `replace` or `append`.

## Benchmark: 1M rows (43 MB)

```
inferred schema: order_id integer, customer_id integer, order_date date, state text,
                 amount numeric, promo_code text, shipped boolean

COPY                1.92s     519,814 rows/s
INSERT (batched)   13.76s      72,673 rows/s
COPY is 7x faster
```

The INSERT baseline is already well optimized: psycopg 3's `executemany` uses pipeline mode, in batches of 1,000. Plain one-row-at-a-time inserts are far slower.

## Bugs the integration tests caught

Two bugs turned up while testing against a real Postgres, and each fix is its own commit:
- **Sample-based integer types were too narrow.** The first version could pick `smallint` when the first 5,000 IDs were small, and then row 40,000 overflowed it. The loader now never picks `smallint`.
- **Single-column files crashed the delimiter sniffer.** It now falls back to the standard comma dialect.

## How to run

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql://postgres@localhost:5432/postgres

PYTHONPATH=src python -m csvload orders.csv staging.orders --dry-run       # just show the schema
PYTHONPATH=src python -m csvload orders.csv staging.orders --mode replace
PYTHONPATH=src python benchmark.py --rows 1000000
```

Tests: the unit tests always run. The integration tests run when `TEST_DATABASE_URL` points at a Postgres database. In CI, GitHub Actions starts a `postgres:16` service container for them.

## Next steps
- Use the type of the widest value seen while loading, not just in the sample, with a fallback to `text`
- Load gzipped files and S3 objects
