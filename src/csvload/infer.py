"""Infer Postgres column types from a sample of CSV rows.

Each column starts as the narrowest type and widens when a value doesn't fit:
    boolean -> integer/bigint -> numeric -> text
    date -> timestamp -> text
Empty strings and common null markers are ignored while inferring.
"""
from __future__ import annotations

import csv
import re
from datetime import datetime
from typing import Iterable

NULLS = {"", "na", "n/a", "null", "none", "nan", "-"}
BOOLS = {"true", "false", "t", "f", "yes", "no", "y", "n"}
INT_RE = re.compile(r"^[+-]?\d+$")
NUM_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y")
TS_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M")

ORDER = ["boolean", "integer", "bigint", "numeric", "date", "timestamp", "text"]


def _parses(value: str, formats) -> str | None:
    for f in formats:
        try:
            datetime.strptime(value, f)
            return f
        except ValueError:
            pass
    return None


def value_type(v: str) -> str:
    low = v.strip().lower()
    if low in BOOLS:
        return "boolean"
    if INT_RE.match(v.strip()):
        # leading zeros mean an identifier (zip code, phone), not a number
        s = v.strip().lstrip("+-")
        if len(s) > 1 and s.startswith("0"):
            return "text"
        n = int(v)
        # no smallint: a sample of small ids says little about the rest of the file
        if -2**31 <= n < 2**31:
            return "integer"
        if -2**63 <= n < 2**63:
            return "bigint"
        return "numeric"
    if NUM_RE.match(v.strip()):
        return "numeric"
    if _parses(v.strip(), DATE_FORMATS):
        return "date"
    if _parses(v.strip(), TS_FORMATS):
        return "timestamp"
    return "text"


def widen(a: str | None, b: str) -> str:
    if a is None or a == b:
        return b
    numeric = {"integer", "bigint", "numeric"}
    temporal = {"date", "timestamp"}
    if a in numeric and b in numeric:
        return max(a, b, key=ORDER.index)
    if a in temporal and b in temporal:
        return "timestamp"
    return "text"  # mixed families, e.g. a number column with one word in it


def clean_name(name: str, seen: set[str]) -> str:
    n = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip()).strip("_").lower() or "col"
    if n[0].isdigit():
        n = f"c_{n}"
    base, i = n, 2
    while n in seen:
        n = f"{base}_{i}"
        i += 1
    seen.add(n)
    return n


def infer_schema(rows: Iterable[list[str]], header: list[str]) -> list[tuple[str, str]]:
    types: list[str | None] = [None] * len(header)
    for row in rows:
        for i, v in enumerate(row[: len(header)]):
            if v.strip().lower() in NULLS:
                continue
            types[i] = widen(types[i], value_type(v))
    seen: set[str] = set()
    return [(clean_name(h, seen), t or "text") for h, t in zip(header, types)]


def sniff(path: str, sample_rows: int = 5000, encoding: str = "utf-8-sig"):
    with open(path, newline="", encoding=encoding) as f:
        head = f.read(64 * 1024)
        try:
            dialect = csv.Sniffer().sniff(head, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel  # single-column files have no delimiter to detect
        f.seek(0)
        reader = csv.reader(f, dialect)
        header = next(reader)
        sample = [r for _, r in zip(range(sample_rows), reader)]
    return dialect, header, infer_schema(sample, header)
