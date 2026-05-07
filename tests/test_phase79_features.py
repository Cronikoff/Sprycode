"""Tests for Phase 79 features: Date Object."""
from __future__ import annotations
from typing import Any
import pytest
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


class TestDateNow:
    def test_date_now_is_number(self):
        assert val(run("let v = typeof Date.now()")) == "number"

    def test_date_now_positive(self):
        assert val(run("let v = Date.now()")) > 0

    def test_date_now_is_large(self):
        # Should be at least year 2020 in ms
        assert val(run("let v = Date.now()")) > 1_000_000_000_000


class TestNewDate:
    def test_new_date_returns_object(self):
        assert val(run("let d = new Date(); let v = typeof d")) == "object"

    def test_new_date_no_args(self):
        # Should not throw and should give a valid year
        i = run("let d = new Date(); let v = d.getFullYear()")
        year = val(i)
        assert isinstance(year, int)
        assert year >= 2020

    def test_new_date_from_timestamp_zero(self):
        assert val(run("let d = new Date(0); let v = d.getFullYear()")) == 1970

    def test_new_date_from_timestamp_year(self):
        # 1000ms after epoch still 1970
        assert val(run("let d = new Date(1000); let v = d.getFullYear()")) == 1970

    def test_new_date_from_string(self):
        assert val(run('let d = new Date("2024-01-15"); let v = d.getFullYear()')) == 2024

    def test_new_date_from_string_month(self):
        assert val(run('let d = new Date("2024-06-15"); let v = d.getMonth()')) == 5

    def test_new_date_from_components_year(self):
        assert val(run("let d = new Date(2024, 0, 15); let v = d.getFullYear()")) == 2024

    def test_new_date_from_components_month(self):
        # JS month is 0-based
        assert val(run("let d = new Date(2024, 5, 15); let v = d.getMonth()")) == 5

    def test_new_date_from_components_day(self):
        assert val(run("let d = new Date(2024, 0, 15); let v = d.getDate()")) == 15


class TestDateGetters:
    def test_get_full_year(self):
        assert val(run("let d = new Date(2023, 0, 1); let v = d.getFullYear()")) == 2023

    def test_get_month_zero_indexed(self):
        # January = 0
        assert val(run("let d = new Date(2023, 0, 1); let v = d.getMonth()")) == 0

    def test_get_month_december(self):
        # December = 11
        assert val(run("let d = new Date(2023, 11, 1); let v = d.getMonth()")) == 11

    def test_get_date(self):
        assert val(run("let d = new Date(2023, 0, 25); let v = d.getDate()")) == 25

    def test_get_day_is_number(self):
        assert val(run("let d = new Date(2024, 0, 15); let v = typeof d.getDay()")) == "number"

    def test_get_hours_is_number(self):
        assert val(run("let d = new Date(2024, 0, 15); let v = typeof d.getHours()")) == "number"

    def test_get_minutes_is_number(self):
        assert val(run("let d = new Date(2024, 0, 15); let v = typeof d.getMinutes()")) == "number"

    def test_get_seconds_is_number(self):
        assert val(run("let d = new Date(2024, 0, 15); let v = typeof d.getSeconds()")) == "number"

    def test_get_milliseconds_is_number(self):
        assert val(run("let d = new Date(2024, 0, 15); let v = typeof d.getMilliseconds()")) == "number"

    def test_get_time_from_epoch(self):
        # new Date(1000) should have getTime() == 1000
        assert val(run("let d = new Date(1000); let v = d.getTime()")) == pytest.approx(1000)

    def test_get_time_is_number(self):
        assert val(run("let d = new Date(); let v = typeof d.getTime()")) == "number"


class TestDateFormatters:
    def test_to_iso_string_is_string(self):
        assert val(run("let d = new Date(0); let v = typeof d.toISOString()")) == "string"

    def test_to_iso_string_contains_year(self):
        result = val(run("let d = new Date(0); let v = d.toISOString()"))
        assert "1970" in str(result)

    def test_to_locale_date_string_is_string(self):
        assert val(run("let d = new Date(0); let v = typeof d.toLocaleDateString()")) == "string"

    def test_to_locale_time_string_is_string(self):
        assert val(run("let d = new Date(0); let v = typeof d.toLocaleTimeString()")) == "string"

    def test_to_string_is_string(self):
        assert val(run("let d = new Date(0); let v = typeof d.toString()")) == "string"

    def test_value_of_from_epoch(self):
        assert val(run("let d = new Date(1000); let v = d.valueOf()")) == pytest.approx(1000)

    def test_value_of_is_number(self):
        assert val(run("let d = new Date(); let v = typeof d.valueOf()")) == "number"

    def test_to_string_not_empty(self):
        result = val(run("let d = new Date(0); let v = d.toString()"))
        assert len(str(result)) > 0
