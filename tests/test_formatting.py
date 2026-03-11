from trinops.formatting import parse_duration_millis, parse_data_size_bytes


def test_parse_duration_seconds():
    assert parse_duration_millis("5.23s") == 5230


def test_parse_duration_minutes():
    assert parse_duration_millis("34.00m") == 2040000


def test_parse_duration_hours():
    assert parse_duration_millis("1.50h") == 5400000


def test_parse_duration_millis():
    assert parse_duration_millis("500.00ms") == 500


def test_parse_duration_microseconds():
    assert parse_duration_millis("100.00us") == 0


def test_parse_duration_nanoseconds():
    assert parse_duration_millis("0.00ns") == 0


def test_parse_duration_days():
    assert parse_duration_millis("1.00d") == 86400000


def test_parse_data_size_bytes():
    assert parse_data_size_bytes("4194304B") == 4194304


def test_parse_data_size_zero():
    assert parse_data_size_bytes("0B") == 0


def test_parse_data_size_large():
    assert parse_data_size_bytes("24696061952B") == 24696061952
