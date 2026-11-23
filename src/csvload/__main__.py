import argparse
import os

from .infer import sniff
from .load import load_csv


def main() -> None:
    p = argparse.ArgumentParser(description="Infer a schema from a CSV and bulk-load it into Postgres")
    p.add_argument("csv")
    p.add_argument("table", help="target table, optionally schema.table")
    p.add_argument("--dsn", default=os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/postgres"))
    p.add_argument("--mode", choices=["create", "replace", "append"], default="create")
    p.add_argument("--dry-run", action="store_true", help="print the inferred schema and stop")
    args = p.parse_args()

    if args.dry_run:
        _, _, schema = sniff(args.csv)
        for name, typ in schema:
            print(f"{name:30s} {typ}")
        return
    r = load_csv(args.csv, args.dsn, args.table, args.mode)
    print(f"loaded {r.rows:,} rows into {r.table} in {r.seconds:.2f}s ({r.rows / r.seconds:,.0f} rows/s)")


if __name__ == "__main__":
    main()
