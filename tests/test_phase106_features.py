"""Tests for Phase 106: SpryDate mutator methods, UTC getters/setters, and comparison operators."""
from __future__ import annotations

from typing import Any

from sprycode.interpreter import Interpreter
from sprycode.lexer import Lexer
from sprycode.parser import Parser


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str = "v") -> Any:
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# getDay() — JS-compatible weekday (0=Sunday, 6=Saturday)
# ---------------------------------------------------------------------------

class TestGetDayJsCompatible:
    def test_sunday_returns_zero(self):
        # 2024-01-07 is a Sunday
        i = run("let v = new Date(2024, 0, 7).getDay();")
        assert val(i) == 0

    def test_monday_returns_one(self):
        # 2024-01-08 is a Monday
        i = run("let v = new Date(2024, 0, 8).getDay();")
        assert val(i) == 1

    def test_saturday_returns_six(self):
        # 2024-01-06 is a Saturday
        i = run("let v = new Date(2024, 0, 6).getDay();")
        assert val(i) == 6


# ---------------------------------------------------------------------------
# Date string conversions
# ---------------------------------------------------------------------------

class TestDateStringConversions:
    def test_to_date_string_is_string(self):
        i = run("let v = typeof new Date(2024, 0, 15).toDateString();")
        assert val(i) == "string"

    def test_to_date_string_not_empty(self):
        i = run("let v = new Date(2024, 0, 15).toDateString().length > 0;")
        assert val(i) is True

    def test_to_date_string_contains_year(self):
        i = run('let s = new Date(2024, 0, 15).toDateString(); let v = s.includes("2024");')
        assert val(i) is True

    def test_to_time_string_is_string(self):
        i = run("let v = typeof new Date(2024, 0, 15, 10, 30, 0).toTimeString();")
        assert val(i) == "string"

    def test_to_time_string_contains_hours(self):
        i = run('let s = new Date(2024, 0, 15, 10, 30, 0).toTimeString(); let v = s.includes("10");')
        assert val(i) is True

    def test_to_utc_string_is_string(self):
        i = run("let v = typeof new Date(2024, 0, 15).toUTCString();")
        assert val(i) == "string"

    def test_to_utc_string_contains_gmt(self):
        i = run('let s = new Date(2024, 0, 15).toUTCString(); let v = s.includes("GMT");')
        assert val(i) is True

    def test_to_json_is_string(self):
        i = run("let v = typeof new Date(2024, 0, 15).toJSON();")
        assert val(i) == "string"

    def test_to_json_same_as_iso_string(self):
        i = run("""
let d = new Date(2024, 0, 15, 10, 30, 0);
let v = d.toJSON() === d.toISOString();
""")
        assert val(i) is True


# ---------------------------------------------------------------------------
# Setter methods
# ---------------------------------------------------------------------------

class TestSetFullYear:
    def test_set_full_year_changes_year(self):
        i = run("let d = new Date(2024, 0, 15); d.setFullYear(2025); let v = d.getFullYear();")
        assert val(i) == 2025

    def test_set_full_year_returns_timestamp(self):
        i = run("let d = new Date(2024, 0, 15); let v = typeof d.setFullYear(2025);")
        assert val(i) == "number"

    def test_set_full_year_with_month(self):
        i = run("let d = new Date(2024, 0, 15); d.setFullYear(2025, 5); let v = d.getMonth();")
        assert val(i) == 5

    def test_set_full_year_with_day(self):
        i = run("let d = new Date(2024, 0, 15); d.setFullYear(2025, 5, 20); let v = d.getDate();")
        assert val(i) == 20


class TestSetMonth:
    def test_set_month_changes_month(self):
        i = run("let d = new Date(2024, 0, 15); d.setMonth(6); let v = d.getMonth();")
        assert val(i) == 6

    def test_set_month_returns_timestamp(self):
        i = run("let d = new Date(2024, 0, 15); let v = typeof d.setMonth(6);")
        assert val(i) == "number"

    def test_set_month_with_day(self):
        i = run("let d = new Date(2024, 0, 15); d.setMonth(6, 20); let v = d.getDate();")
        assert val(i) == 20


class TestSetDate:
    def test_set_date_changes_day(self):
        i = run("let d = new Date(2024, 0, 15); d.setDate(25); let v = d.getDate();")
        assert val(i) == 25

    def test_set_date_returns_timestamp(self):
        i = run("let d = new Date(2024, 0, 15); let v = typeof d.setDate(25);")
        assert val(i) == "number"


class TestSetHours:
    def test_set_hours_changes_hours(self):
        i = run("let d = new Date(2024, 0, 15, 0, 0, 0); d.setHours(14); let v = d.getHours();")
        assert val(i) == 14

    def test_set_hours_with_minutes(self):
        i = run("let d = new Date(2024, 0, 15, 0, 0, 0); d.setHours(14, 30); let v = d.getMinutes();")
        assert val(i) == 30

    def test_set_hours_with_seconds(self):
        i = run("let d = new Date(2024, 0, 15, 0, 0, 0); d.setHours(14, 30, 45); let v = d.getSeconds();")
        assert val(i) == 45

    def test_set_hours_with_ms(self):
        i = run("let d = new Date(2024, 0, 15, 0, 0, 0, 0); d.setHours(14, 30, 45, 500); let v = d.getMilliseconds();")
        assert val(i) == 500


class TestSetMinutes:
    def test_set_minutes_changes_minutes(self):
        i = run("let d = new Date(2024, 0, 15, 10, 0, 0); d.setMinutes(45); let v = d.getMinutes();")
        assert val(i) == 45

    def test_set_minutes_with_seconds(self):
        i = run("let d = new Date(2024, 0, 15, 10, 0, 0); d.setMinutes(45, 30); let v = d.getSeconds();")
        assert val(i) == 30


class TestSetSeconds:
    def test_set_seconds_changes_seconds(self):
        i = run("let d = new Date(2024, 0, 15, 10, 30, 0); d.setSeconds(55); let v = d.getSeconds();")
        assert val(i) == 55

    def test_set_seconds_with_ms(self):
        i = run("let d = new Date(2024, 0, 15, 10, 30, 0, 0); d.setSeconds(55, 250); let v = d.getMilliseconds();")
        assert val(i) == 250


class TestSetMilliseconds:
    def test_set_milliseconds_changes_ms(self):
        i = run("let d = new Date(2024, 0, 15, 10, 30, 0, 0); d.setMilliseconds(999); let v = d.getMilliseconds();")
        assert val(i) == 999

    def test_set_milliseconds_returns_timestamp(self):
        i = run("let d = new Date(2024, 0, 15); let v = typeof d.setMilliseconds(100);")
        assert val(i) == "number"


class TestSetTime:
    def test_set_time_changes_date(self):
        # epoch + 0 ms = Jan 1 1970
        i = run("let d = new Date(2024, 0, 15); d.setTime(0); let v = d.getFullYear();")
        assert val(i) == 1970

    def test_set_time_returns_timestamp(self):
        i = run("let d = new Date(2024, 0, 15); let v = typeof d.setTime(0);")
        assert val(i) == "number"

    def test_set_time_round_trip(self):
        i = run("""
let d = new Date(2024, 0, 15, 10, 30, 0);
let ms = d.getTime();
d.setTime(ms);
let v = d.getFullYear();
""")
        assert val(i) == 2024


# ---------------------------------------------------------------------------
# UTC getters
# ---------------------------------------------------------------------------

class TestUTCGetters:
    def test_get_utc_full_year(self):
        i = run("let v = new Date(2024, 0, 15).getUTCFullYear();")
        assert val(i) == 2024

    def test_get_utc_month(self):
        i = run("let v = new Date(2024, 5, 15).getUTCMonth();")
        assert val(i) == 5

    def test_get_utc_date(self):
        i = run("let v = new Date(2024, 0, 20).getUTCDate();")
        assert val(i) == 20

    def test_get_utc_hours(self):
        i = run("let v = new Date(2024, 0, 15, 14, 0, 0).getUTCHours();")
        assert val(i) == 14

    def test_get_utc_minutes(self):
        i = run("let v = new Date(2024, 0, 15, 0, 45, 0).getUTCMinutes();")
        assert val(i) == 45

    def test_get_utc_seconds(self):
        i = run("let v = new Date(2024, 0, 15, 0, 0, 30).getUTCSeconds();")
        assert val(i) == 30

    def test_get_utc_milliseconds(self):
        i = run("let v = new Date(2024, 0, 15, 0, 0, 0, 750).getUTCMilliseconds();")
        assert val(i) == 750

    def test_get_utc_day_sunday(self):
        # 2024-01-07 is a Sunday
        i = run("let v = new Date(2024, 0, 7).getUTCDay();")
        assert val(i) == 0

    def test_utc_getters_equal_local_getters(self):
        """SpryCode has no tz support so UTC and local getters return the same value."""
        i = run("""
let d = new Date(2024, 5, 15, 14, 30, 45, 123);
let v = d.getUTCFullYear() === d.getFullYear()
     && d.getUTCMonth() === d.getMonth()
     && d.getUTCDate() === d.getDate()
     && d.getUTCHours() === d.getHours()
     && d.getUTCMinutes() === d.getMinutes()
     && d.getUTCSeconds() === d.getSeconds()
     && d.getUTCMilliseconds() === d.getMilliseconds();
""")
        assert val(i) is True

    def test_get_utc_day_is_number(self):
        i = run("let v = typeof new Date(2024, 0, 15).getUTCDay();")
        assert val(i) == "number"


# ---------------------------------------------------------------------------
# UTC setters
# ---------------------------------------------------------------------------

class TestUTCSetters:
    def test_set_utc_full_year(self):
        i = run("let d = new Date(2024, 0, 15); d.setUTCFullYear(2026); let v = d.getUTCFullYear();")
        assert val(i) == 2026

    def test_set_utc_month(self):
        i = run("let d = new Date(2024, 0, 15); d.setUTCMonth(8); let v = d.getUTCMonth();")
        assert val(i) == 8

    def test_set_utc_date(self):
        i = run("let d = new Date(2024, 0, 15); d.setUTCDate(28); let v = d.getUTCDate();")
        assert val(i) == 28

    def test_set_utc_hours(self):
        i = run("let d = new Date(2024, 0, 15, 0, 0, 0); d.setUTCHours(20); let v = d.getUTCHours();")
        assert val(i) == 20

    def test_set_utc_minutes(self):
        i = run("let d = new Date(2024, 0, 15, 0, 0, 0); d.setUTCMinutes(15); let v = d.getUTCMinutes();")
        assert val(i) == 15

    def test_set_utc_seconds(self):
        i = run("let d = new Date(2024, 0, 15, 0, 0, 0); d.setUTCSeconds(10); let v = d.getUTCSeconds();")
        assert val(i) == 10

    def test_set_utc_milliseconds(self):
        i = run("let d = new Date(2024, 0, 15, 0, 0, 0, 0); d.setUTCMilliseconds(123); let v = d.getUTCMilliseconds();")
        assert val(i) == 123


# ---------------------------------------------------------------------------
# Comparison operators
# ---------------------------------------------------------------------------

class TestDateComparisons:
    def test_earlier_date_less_than(self):
        i = run("let a = new Date(2024, 0, 1); let b = new Date(2024, 0, 2); let v = a < b;")
        assert val(i) is True

    def test_later_date_not_less_than(self):
        i = run("let a = new Date(2024, 0, 1); let b = new Date(2024, 0, 2); let v = b < a;")
        assert val(i) is False

    def test_later_date_greater_than(self):
        i = run("let a = new Date(2024, 0, 1); let b = new Date(2024, 0, 2); let v = b > a;")
        assert val(i) is True

    def test_same_dates_equal(self):
        i = run("let a = new Date(2024, 0, 15); let b = new Date(2024, 0, 15); let v = a == b;")
        assert val(i) is True

    def test_different_dates_not_equal(self):
        i = run("let a = new Date(2024, 0, 1); let b = new Date(2024, 0, 2); let v = a == b;")
        assert val(i) is False

    def test_less_than_or_equal_when_equal(self):
        i = run("let a = new Date(2024, 0, 15); let b = new Date(2024, 0, 15); let v = a <= b;")
        assert val(i) is True

    def test_greater_than_or_equal_when_equal(self):
        i = run("let a = new Date(2024, 0, 15); let b = new Date(2024, 0, 15); let v = a >= b;")
        assert val(i) is True

    def test_sort_dates(self):
        i = run("""
let dates = [new Date(2024, 2, 1), new Date(2024, 0, 1), new Date(2024, 1, 1)];
let sorted = dates.sort((a, b) => a < b ? -1 : a > b ? 1 : 0);
let v = sorted[0].getMonth();
""")
        assert val(i) == 0  # January
