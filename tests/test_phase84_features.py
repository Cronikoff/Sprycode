"""Tests for Phase 84: Intl Internationalization."""
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


# ---------------------------------------------------------------------------
# Intl object
# ---------------------------------------------------------------------------

def test_intl_exists():
    i = run("var v = typeof Intl;")
    assert val(i) == "object"


def test_intl_number_format_is_function():
    i = run("var v = typeof Intl.NumberFormat;")
    assert val(i) == "function"


def test_intl_datetime_format_is_function():
    i = run("var v = typeof Intl.DateTimeFormat;")
    assert val(i) == "function"


def test_intl_collator_is_function():
    i = run("var v = typeof Intl.Collator;")
    assert val(i) == "function"


def test_intl_plural_rules_is_function():
    i = run("var v = typeof Intl.PluralRules;")
    assert val(i) == "function"


def test_intl_list_format_is_function():
    i = run("var v = typeof Intl.ListFormat;")
    assert val(i) == "function"


def test_intl_relative_time_format_is_function():
    i = run("var v = typeof Intl.RelativeTimeFormat;")
    assert val(i) == "function"


def test_intl_segmenter_is_function():
    i = run("var v = typeof Intl.Segmenter;")
    assert val(i) == "function"


# ---------------------------------------------------------------------------
# Intl.NumberFormat
# ---------------------------------------------------------------------------

def test_number_format_basic():
    i = run("var fmt = new Intl.NumberFormat('en-US'); var v = typeof fmt.format(1234);")
    assert val(i) == "string"


def test_number_format_integer():
    i = run("var v = new Intl.NumberFormat('en-US').format(1234567);")
    assert "1" in val(i) and "234" in val(i)


def test_number_format_with_decimals():
    i = run("var v = new Intl.NumberFormat('en-US').format(1234567.89);")
    assert isinstance(val(i), str)
    assert "1" in val(i)


def test_number_format_currency():
    i = run("var v = new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(42);")
    result = val(i)
    assert isinstance(result, str)
    assert "42" in result


def test_number_format_zero():
    i = run("var v = new Intl.NumberFormat('en-US').format(0);")
    assert val(i) == "0"


def test_number_format_negative():
    i = run("var v = new Intl.NumberFormat('en-US').format(-42);")
    result = val(i)
    assert isinstance(result, str)
    assert "42" in result


def test_number_format_percent():
    i = run("var v = new Intl.NumberFormat('en-US', {style: 'percent'}).format(0.5);")
    result = val(i)
    assert isinstance(result, str)


def test_number_format_format_returns_string():
    i = run("var fmt = new Intl.NumberFormat('en-US'); var v = typeof fmt.format(100);")
    assert val(i) == "string"


def test_number_format_large_number():
    i = run("var v = new Intl.NumberFormat('en-US').format(1000000);")
    assert isinstance(val(i), str)


# ---------------------------------------------------------------------------
# Intl.DateTimeFormat
# ---------------------------------------------------------------------------

def test_datetime_format_returns_string():
    i = run("var v = typeof new Intl.DateTimeFormat('en-US').format(new Date());")
    assert val(i) == "string"


def test_datetime_format_creates():
    i = run("var fmt = new Intl.DateTimeFormat('en-US'); var v = typeof fmt;")
    assert val(i) == "object"


def test_datetime_format_has_format():
    i = run("var fmt = new Intl.DateTimeFormat('en-US'); var v = typeof fmt.format;")
    assert val(i) == "function"


def test_datetime_format_with_options():
    i = run("""
var opts = {year: 'numeric', month: 'long', day: 'numeric'};
var fmt = new Intl.DateTimeFormat('en-US', opts);
var v = typeof fmt.format(new Date());
""")
    assert val(i) == "string"


def test_datetime_format_nonempty():
    i = run("var v = new Intl.DateTimeFormat('en-US').format(new Date()).length > 0;")
    assert val(i) == True


# ---------------------------------------------------------------------------
# Intl.Collator
# ---------------------------------------------------------------------------

def test_collator_compare_a_lt_b():
    i = run("var v = new Intl.Collator('en').compare('a', 'b');")
    assert val(i) == -1


def test_collator_compare_b_gt_a():
    i = run("var v = new Intl.Collator('en').compare('b', 'a');")
    assert val(i) == 1


def test_collator_compare_equal():
    i = run("var v = new Intl.Collator('en').compare('a', 'a');")
    assert val(i) == 0


def test_collator_creates():
    i = run("var col = new Intl.Collator('en'); var v = typeof col;")
    assert val(i) == "object"


def test_collator_has_compare():
    i = run("var col = new Intl.Collator('en'); var v = typeof col.compare;")
    assert val(i) == "function"


def test_locale_compare_lt():
    i = run("var v = 'a'.localeCompare('b');")
    assert val(i) == -1


def test_locale_compare_gt():
    i = run("var v = 'b'.localeCompare('a');")
    assert val(i) == 1


def test_locale_compare_equal():
    i = run("var v = 'a'.localeCompare('a');")
    assert val(i) == 0


def test_locale_compare_with_locale():
    i = run("var v = 'a'.localeCompare('b', 'en');")
    assert val(i) == -1


# ---------------------------------------------------------------------------
# Intl.PluralRules
# ---------------------------------------------------------------------------

def test_plural_rules_one():
    i = run("var v = new Intl.PluralRules('en').select(1);")
    assert val(i) == "one"


def test_plural_rules_other():
    i = run("var v = new Intl.PluralRules('en').select(2);")
    assert val(i) == "other"


def test_plural_rules_zero():
    i = run("var v = new Intl.PluralRules('en').select(0);")
    assert isinstance(val(i), str)


def test_plural_rules_creates():
    i = run("var pr = new Intl.PluralRules('en'); var v = typeof pr;")
    assert val(i) == "object"


def test_plural_rules_many():
    i = run("var v = new Intl.PluralRules('en').select(100);")
    assert isinstance(val(i), str)


# ---------------------------------------------------------------------------
# Intl.ListFormat
# ---------------------------------------------------------------------------

def test_list_format_basic():
    i = run("""
var fmt = new Intl.ListFormat('en', {style: 'long', type: 'conjunction'});
var v = fmt.format(['a', 'b', 'c']);
""")
    result = val(i)
    assert isinstance(result, str)
    assert "a" in result and "b" in result and "c" in result


def test_list_format_single():
    i = run("var fmt = new Intl.ListFormat('en'); var v = fmt.format(['one']);")
    assert val(i) == "one"


def test_list_format_two():
    i = run("var fmt = new Intl.ListFormat('en'); var v = fmt.format(['x', 'y']);")
    result = val(i)
    assert "x" in result and "y" in result


def test_list_format_creates():
    i = run("var fmt = new Intl.ListFormat('en'); var v = typeof fmt;")
    assert val(i) == "object"


def test_list_format_has_format():
    i = run("var fmt = new Intl.ListFormat('en'); var v = typeof fmt.format;")
    assert val(i) == "function"


# ---------------------------------------------------------------------------
# Intl.RelativeTimeFormat
# ---------------------------------------------------------------------------

def test_relative_time_format_basic():
    i = run("var fmt = new Intl.RelativeTimeFormat('en'); var v = typeof fmt.format(-1, 'day');")
    assert val(i) == "string"


def test_relative_time_format_creates():
    i = run("var fmt = new Intl.RelativeTimeFormat('en'); var v = typeof fmt;")
    assert val(i) == "object"


def test_relative_time_format_nonempty():
    i = run("var fmt = new Intl.RelativeTimeFormat('en'); var v = fmt.format(-1, 'day').length > 0;")
    assert val(i) == True


def test_relative_time_format_future():
    i = run("var fmt = new Intl.RelativeTimeFormat('en'); var v = typeof fmt.format(1, 'hour');")
    assert val(i) == "string"


# ---------------------------------------------------------------------------
# Intl.Segmenter
# ---------------------------------------------------------------------------

def test_segmenter_creates():
    i = run("var seg = new Intl.Segmenter('en', {granularity: 'word'}); var v = typeof seg;")
    assert val(i) == "object"


def test_segmenter_segment_returns_object():
    i = run("var seg = new Intl.Segmenter('en'); var v = typeof seg.segment('hello world');")
    assert val(i) == "object"


def test_segmenter_has_segment():
    i = run("var seg = new Intl.Segmenter('en'); var v = typeof seg.segment;")
    assert val(i) == "function"


# ---------------------------------------------------------------------------
# Number.toLocaleString
# ---------------------------------------------------------------------------

def test_number_tolocalestring():
    i = run("var v = typeof (1234567).toLocaleString('en-US');")
    assert val(i) == "string"


def test_number_tolocalestring_value():
    i = run("var v = (1234567).toLocaleString('en-US');")
    assert isinstance(val(i), str)
    assert "1" in val(i)
