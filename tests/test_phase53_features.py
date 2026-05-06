"""Phase 53 feature tests — String.at(), String.localeCompare, getOwnPropertySymbols,
JSON.stringify Symbol filter, Intl.Segmenter, async generator improvements."""
import pytest
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.interpreter import Interpreter


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(src: str, name: str = "v"):
    return run(src).globals.get(name)


# ---------------------------------------------------------------------------
# String.at() with negative indices
# ---------------------------------------------------------------------------

class TestStringAt:
    def test_at_positive(self):
        assert val('let v = "hello".at(0)') == "h"

    def test_at_negative(self):
        assert val('let v = "hello".at(-1)') == "o"

    def test_at_negative_second(self):
        assert val('let v = "hello".at(-2)') == "l"

    def test_at_out_of_range(self):
        assert val('let v = "hello".at(10)') is None


# ---------------------------------------------------------------------------
# String.localeCompare
# ---------------------------------------------------------------------------

class TestLocaleCompare:
    def test_equal(self):
        assert val('let v = "a".localeCompare("a")') == 0

    def test_less(self):
        assert val('let v = "a".localeCompare("b")') == -1

    def test_greater(self):
        assert val('let v = "b".localeCompare("a")') == 1


# ---------------------------------------------------------------------------
# Object.getOwnPropertySymbols
# ---------------------------------------------------------------------------

class TestGetOwnPropertySymbols:
    def test_no_symbols(self):
        v = val('let obj = {a: 1, b: 2}\nlet v = Object.getOwnPropertySymbols(obj).length')
        assert v == 0

    def test_with_symbol(self):
        src = """
let s = Symbol("test")
let obj = {a: 1}
obj[s] = 42
let v = Object.getOwnPropertySymbols(obj).length
"""
        assert val(src) == 1


# ---------------------------------------------------------------------------
# JSON.stringify Symbol filter
# ---------------------------------------------------------------------------

class TestJsonStringifySymbols:
    def test_symbols_excluded(self):
        src = """
let s = Symbol("x")
let obj = {a: 1}
obj[s] = 99
let v = JSON.stringify(obj)
"""
        result = val(src)
        assert '"a":1' in result or '"a": 1' in result
        assert "99" not in result

    def test_normal_keys_included(self):
        src = 'let v = JSON.stringify({a: 1, b: 2})'
        result = val(src)
        assert "a" in result and "b" in result


# ---------------------------------------------------------------------------
# Intl.Segmenter
# ---------------------------------------------------------------------------

class TestIntlSegmenter:
    def test_segmenter_creates(self):
        src = 'let seg = new Intl.Segmenter("en")\nlet v = typeof seg'
        assert val(src) == "object"

    def test_segmenter_segment_count(self):
        src = """
let seg = new Intl.Segmenter("en")
let segs = seg.segment("Hello World")
let v = segs.length
"""
        result = val(src)
        assert isinstance(result, int) and result > 0

    def test_segmenter_has_segment_field(self):
        src = """
let seg = new Intl.Segmenter("en")
let segs = seg.segment("Hi")
let v = segs[0].segment
"""
        result = val(src)
        assert result is not None
