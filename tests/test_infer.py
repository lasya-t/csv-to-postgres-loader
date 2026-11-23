from csvload import infer_schema, value_type


def test_value_types():
    assert value_type("yes") == "boolean"
    assert value_type("3000000000") == "bigint"
    assert value_type("1e5") == "numeric"
    assert value_type("2025-03-01") == "date"
    assert value_type("2025-03-01T08:30:00") == "timestamp"
    assert value_type("hello") == "text"


def test_leading_zeros_stay_text():
    assert value_type("02139") == "text"
    assert value_type("0") != "text"


def test_widening_and_nulls():
    rows = [["1", "2025-01-01", "5", "NA"], ["2.5", "2025-01-01 10:00", "x", ""]]
    schema = infer_schema(rows, ["a", "b", "c", "d"])
    assert schema == [("a", "numeric"), ("b", "timestamp"), ("c", "text"), ("d", "text")]


def test_column_names_cleaned_and_deduped():
    schema = infer_schema([["1", "2", "3"]], ["Order ID", "order id", "2024 Sales"])
    assert [n for n, _ in schema] == ["order_id", "order_id_2", "c_2024_sales"]
