"""Create a table from the inferred schema and bulk-load the CSV with COPY."""
from __future__ import annotations

import csv
import time
from dataclasses import dataclass

import psycopg
from psycopg import sql

from .infer import NULLS, sniff


@dataclass
class LoadResult:
    table: str
    rows: int
    seconds: float
    schema: list[tuple[str, str]]


def create_table(cur, table: str, schema, mode: str) -> None:
    ident = sql.Identifier(*table.split("."))
    cols = sql.SQL(", ").join(sql.SQL("{} {}").format(sql.Identifier(n), sql.SQL(t)) for n, t in schema)
    if mode == "replace":
        cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(ident))
    if mode in ("create", "replace"):
        cur.execute(sql.SQL("CREATE TABLE {} ({})").format(ident, cols))
    elif mode != "append":
        raise ValueError("mode must be create, replace or append")


def load_csv(path: str, dsn: str, table: str, mode: str = "create", sample_rows: int = 5000) -> LoadResult:
    dialect, header, schema = sniff(path, sample_rows)
    t0 = time.perf_counter()
    rows = 0
    # one transaction: a failed load leaves no half-filled table behind
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SET DateStyle = 'ISO, MDY'")
        create_table(cur, table, schema, mode)
        names = sql.SQL(", ").join(sql.Identifier(n) for n, _ in schema)
        copy_sql = sql.SQL("COPY {} ({}) FROM STDIN").format(sql.Identifier(*table.split(".")), names)
        with open(path, newline="", encoding="utf-8-sig") as f, cur.copy(copy_sql) as copy:
            reader = csv.reader(f, dialect)
            next(reader)
            width = len(header)
            for line_no, row in enumerate(reader, start=2):
                if len(row) != width:
                    raise ValueError(f"line {line_no}: expected {width} fields, got {len(row)}")
                copy.write_row([None if v.strip().lower() in NULLS else v for v in row])
                rows += 1
    return LoadResult(table, rows, time.perf_counter() - t0, schema)


def load_with_inserts(path: str, dsn: str, table: str, batch: int = 1000) -> LoadResult:
    """Row-by-row INSERT baseline (executemany), for the benchmark."""
    dialect, header, schema = sniff(path)
    t0 = time.perf_counter()
    rows = 0
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SET DateStyle = 'ISO, MDY'")
        create_table(cur, table, schema, "replace")
        q = sql.SQL("INSERT INTO {} VALUES ({})").format(
            sql.Identifier(*table.split(".")), sql.SQL(", ").join(sql.Placeholder() * len(schema))
        )
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f, dialect)
            next(reader)
            buf = []
            for row in reader:
                buf.append([None if v.strip().lower() in NULLS else v for v in row])
                if len(buf) == batch:
                    cur.executemany(q, buf)
                    rows += len(buf)
                    buf = []
            if buf:
                cur.executemany(q, buf)
                rows += len(buf)
    return LoadResult(table, rows, time.perf_counter() - t0, schema)
