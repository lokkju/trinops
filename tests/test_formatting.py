from trinops.formatting import (
    parse_duration_millis,
    parse_data_size_bytes,
    format_compact_number,
    format_compact_uptime,
)


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


# format_compact_number tests

def test_format_compact_number_small():
    assert format_compact_number(0) == "0"
    assert format_compact_number(999) == "999"


def test_format_compact_number_thousands():
    assert format_compact_number(1_000) == "1.0K"
    assert format_compact_number(5_600) == "5.6K"
    assert format_compact_number(999_999) == "1000.0K"


def test_format_compact_number_millions():
    assert format_compact_number(1_000_000) == "1.0M"
    assert format_compact_number(34_148_040) == "34.1M"


def test_format_compact_number_billions():
    assert format_compact_number(1_200_000_000) == "1.2B"
    assert format_compact_number(5_678_000_000_000) == "5678.0B"


# format_compact_uptime tests

def test_format_compact_uptime_seconds():
    assert format_compact_uptime(45_000) == "45s"


def test_format_compact_uptime_minutes():
    assert format_compact_uptime(312_000) == "5m12s"


def test_format_compact_uptime_hours():
    assert format_compact_uptime(18_720_000) == "5h12m"


def test_format_compact_uptime_days():
    assert format_compact_uptime(266_400_000) == "3d2h"


def test_format_compact_uptime_zero():
    assert format_compact_uptime(0) == "0s"


def test_format_compact_uptime_days_only():
    assert format_compact_uptime(86_400_000) == "1d0h"
