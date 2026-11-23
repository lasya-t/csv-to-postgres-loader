"""COPY vs batched INSERT on the same generated CSV."""
import argparse
import csv
import os
import random
from datetime import date, timedelta

from csvload.load import load_csv, load_with_inserts


def make_csv(path, n, seed=0):
    rnd = random.Random(seed)
    start = date(2024, 1, 1)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Order ID", "Customer ID", "Order Date", "State", "Amount", "Promo Code", "Shipped"])
        for i in range(1, n + 1):
            w.writerow([
                i, rnd.randint(1, 50_000), start + timedelta(days=rnd.randint(0, 600)),
                rnd.choice(["PA", "NJ", "NY", "DE"]), f"{rnd.uniform(5, 1500):.2f}",
                rnd.choice(["", "", "", "SAVE10", "BOGO"]), rnd.choice(["true", "false"]),
            ])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, default=1_000_000)
    p.add_argument("--dsn", default=os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/postgres"))
    args = p.parse_args()

    path = "bench_orders.csv"
    make_csv(path, args.rows)
    size_mb = os.path.getsize(path) / 1e6
    print(f"{args.rows:,} rows, {size_mb:.0f} MB\n")

    r = load_csv(path, args.dsn, "bench_copy", mode="replace")
    print("inferred schema:", ", ".join(f"{n} {t}" for n, t in r.schema))
    print(f"\nCOPY             {r.seconds:7.2f}s  {r.rows / r.seconds:>10,.0f} rows/s")
    r2 = load_with_inserts(path, args.dsn, "bench_insert")
    print(f"INSERT (batched) {r2.seconds:7.2f}s  {r2.rows / r2.seconds:>10,.0f} rows/s")
    print(f"\nCOPY is {r2.seconds / r.seconds:.0f}x faster")
    os.remove(path)


if __name__ == "__main__":
    main()
