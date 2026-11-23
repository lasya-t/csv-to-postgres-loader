"""Integration tests against a real Postgres. Set TEST_DATABASE_URL to run them."""
import csv
import os

import psycopg
import pytest

from csvload import load_csv

DSN = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL not set")


def _write(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return str(path)


def _fetch(q):
    with psycopg.connect(DSN) as c:
        return c.execute(q).fetchall()


def test_round_trip(tmp_path):
    p = _write(tmp_path / "a.csv", ["id", "zip", "amount", "day"],
               [[1, "02139", "9.50", "2025-01-02"], [2, "10001", "", "01/03/2025"]])
    r = load_csv(p, DSN, "t_round_trip", mode="replace")
    assert r.rows == 2
    rows = _fetch("SELECT zip, amount, day::text FROM t_round_trip ORDER BY id")
    assert rows[0][0] == "02139" and rows[1][1] is None and rows[1][2] == "2025-01-03"


def test_ids_beyond_the_sample_still_load(tmp_path):
    # the first 5,000 ids are small, later ones are not: a sample-based guess must not be too narrow
    rows = [[i, f"name{i}"] for i in range(1, 50_001)]
    p = _write(tmp_path / "b.csv", ["id", "name"], rows)
    r = load_csv(p, DSN, "t_wide_ids", mode="replace", sample_rows=5000)
    assert r.rows == 50_000
    assert _fetch("SELECT max(id) FROM t_wide_ids")[0][0] == 50_000


def test_bad_row_rolls_back(tmp_path):
    p = _write(tmp_path / "c.csv", ["id", "name"], [[1, "a"], [2, "b", "extra"]])
    with pytest.raises(ValueError, match="line 3"):
        load_csv(p, DSN, "t_bad", mode="replace")
    assert _fetch("SELECT to_regclass('t_bad')")[0][0] is None


def test_append_mode(tmp_path):
    p = _write(tmp_path / "d.csv", ["id"], [[1], [2]])
    load_csv(p, DSN, "t_append", mode="replace")
    load_csv(p, DSN, "t_append", mode="append")
    assert _fetch("SELECT count(*) FROM t_append")[0][0] == 4
