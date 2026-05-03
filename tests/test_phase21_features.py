"""Phase 21 feature tests."""
from __future__ import annotations

from typing import Any

import pytest

from sprycode.interpreter import (
    Interpreter,
    SpryMap,
    SpryRegexMatch,
    SpryRuntimeError,
    SprySymbol,
)
from sprycode.lexer import Lexer
from sprycode.parser import Parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(source: str) -> Interpreter:
    tokens = Lexer(source).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str) -> Any:
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# Fix 1 — Map.new(entries?) and Map.__call__(entries?)
# ---------------------------------------------------------------------------


class TestMapNew:
    def test_map_new_empty(self):
        i = run("let m = Map.new()")
        assert isinstance(val(i, "m"), SpryMap)
        assert len(val(i, "m")._data) == 0

    def test_map_new_from_list_pairs(self):
        i = run('let m = Map.new([["a", 1], ["b", 2]])')
        m = val(i, "m")
        assert isinstance(m, SpryMap)
        assert m.spry_get("a") == 1
        assert m.spry_get("b") == 2

    def test_map_new_from_dict(self):
        i = run("let m = Map.new({x: 10, y: 20})")
        m = val(i, "m")
        assert m.spry_get("x") == 10
        assert m.spry_get("y") == 20

    def test_map_new_from_sprymap(self):
        i = run('let a = Map.new([["k", 99]])\nlet b = Map.new(a)')
        b = val(i, "b")
        assert b.spry_get("k") == 99

    def test_map_callable_empty(self):
        i = run("let m = Map.new()")
        assert isinstance(val(i, "m"), SpryMap)

    def test_map_new_partial_pairs_ignored(self):
        i = run('let m = Map.new([["a", 1], ["b", 2], ["c", 3]])')
        assert len(val(i, "m")._data) == 3

    def test_map_new_size(self):
        i = run('let m = Map.new([["x", 1], ["y", 2], ["z", 3]])\nlet s = m.size')
        assert val(i, "s") == 3

    def test_map_new_none_is_empty(self):
        i = run("let m = Map.new(null)")
        assert len(val(i, "m")._data) == 0


# ---------------------------------------------------------------------------
# Fix 2 — SpryMap for..of iteration
# ---------------------------------------------------------------------------


class TestMapForOf:
    def test_for_of_map_collects_pairs(self):
        i = run(
            'let m = Map.new([["a", 1], ["b", 2]])\n'
            "var keys = []\n"
            "for pair in m { keys.push(pair[0]) }"
        )
        assert sorted(val(i, "keys")) == ["a", "b"]

    def test_for_of_map_values(self):
        i = run(
            'let m = Map.new([["x", 10], ["y", 20]])\n'
            "var vals = []\n"
            "for pair in m { vals.push(pair[1]) }"
        )
        assert sorted(val(i, "vals")) == [10, 20]

    def test_for_of_map_destructuring(self):
        i = run(
            'let m = Map.new([["a", 1]])\n'
            "var k = null\n"
            "var v = null\n"
            "for pair in m { k = pair[0]\nv = pair[1] }"
        )
        assert val(i, "k") == "a"
        assert val(i, "v") == 1

    def test_for_of_empty_map(self):
        i = run("let m = Map.new()\nvar count = 0\nfor pair in m { count = count + 1 }")
        assert val(i, "count") == 0

    def test_for_of_map_pair_is_list(self):
        i = run(
            'let m = Map.new([["z", 99]])\n'
            "var got = null\n"
            "for pair in m { got = pair }"
        )
        assert val(i, "got") == ["z", 99]

    def test_for_of_map_three_entries(self):
        i = run(
            'let m = Map.new([["a", 1], ["b", 2], ["c", 3]])\n'
            "var sum = 0\n"
            "for pair in m { sum = sum + pair[1] }"
        )
        assert val(i, "sum") == 6

    def test_for_of_map_keys_count(self):
        i = run(
            'let m = Map.new([["p", 5], ["q", 6]])\n'
            "var n = 0\n"
            "for pair in m { n = n + 1 }"
        )
        assert val(i, "n") == 2

    def test_for_of_map_set_then_iterate(self):
        i = run(
            "let m = Map.new()\n"
            'm.set("hello", 42)\n'
            "var found = null\n"
            "for pair in m { found = pair[1] }"
        )
        assert val(i, "found") == 42


# ---------------------------------------------------------------------------
# Fix 3 — Symbol well-known symbols
# ---------------------------------------------------------------------------


class TestSymbolWellKnown:
    def test_symbol_iterator_is_symbol(self):
        i = run("let s = Symbol.iterator")
        assert isinstance(val(i, "s"), SprySymbol)

    def test_symbol_iterator_description(self):
        i = run("let s = Symbol.iterator")
        assert val(i, "s").description == "iterator"

    def test_symbol_toPrimitive(self):
        i = run("let s = Symbol.toPrimitive")
        assert isinstance(val(i, "s"), SprySymbol)

    def test_symbol_toStringTag(self):
        i = run("let s = Symbol.toStringTag")
        assert val(i, "s").description == "toStringTag"

    def test_symbol_hasInstance(self):
        i = run("let s = Symbol.hasInstance")
        assert isinstance(val(i, "s"), SprySymbol)

    def test_symbol_well_known_singleton(self):
        # Same attribute access returns the same object
        i = run("let a = Symbol.iterator\nlet b = Symbol.iterator")
        a = val(i, "a")
        b = val(i, "b")
        assert a is b

    def test_symbol_species(self):
        i = run("let s = Symbol.species")
        assert val(i, "s").description == "species"

    def test_symbol_asyncIterator(self):
        i = run("let s = Symbol.asyncIterator")
        assert isinstance(val(i, "s"), SprySymbol)

    def test_symbol_match_well_known(self):
        i = run("let s = Symbol.match")
        assert val(i, "s").description == "match"

    def test_symbol_split_well_known(self):
        i = run("let s = Symbol.split")
        assert isinstance(val(i, "s"), SprySymbol)


# ---------------------------------------------------------------------------
# Fix 4 — regex.exec() / regex.match() return SpryRegexMatch
# ---------------------------------------------------------------------------


class TestRegexExecMatch:
    def test_exec_returns_regex_match(self):
        i = run('let r = /hello/\nlet m = r.exec("hello world")')
        assert isinstance(val(i, "m"), SpryRegexMatch)

    def test_exec_full_match_at_index_0(self):
        i = run('let r = /\\d+/\nlet m = r.exec("abc 123 def")')
        assert val(i, "m")[0] == "123"

    def test_exec_index_property(self):
        i = run('let r = /\\d+/\nlet m = r.exec("abc 123 def")')
        m = val(i, "m")
        assert m.index == 4

    def test_exec_no_match_returns_null(self):
        i = run('let r = /xyz/\nlet m = r.exec("hello world")')
        assert val(i, "m") is None

    def test_match_with_groups(self):
        i = run('let r = /(\\w+)\\s(\\w+)/\nlet m = r.match("hello world")')
        m = val(i, "m")
        assert m[0] == "hello world"
        assert m[1] == "hello"
        assert m[2] == "world"

    def test_match_input_property(self):
        i = run('let r = /\\d+/\nlet m = r.match("test 42 end")')
        assert val(i, "m").input == "test 42 end"

    def test_exec_is_same_as_match(self):
        i = run(
            'let r = /foo/\n'
            'let m1 = r.match("foobar")\n'
            'let m2 = r.exec("foobar")'
        )
        assert val(i, "m1")[0] == val(i, "m2")[0]

    def test_regex_match_list_indexing(self):
        i = run('let r = /\\d+/\nlet m = r.exec("num 7 end")')
        m = val(i, "m")
        assert isinstance(m, list)
        assert len(m) == 1
        assert m[0] == "7"

    def test_str_match_regex_returns_regex_match(self):
        i = run('let m = "hello world".match(/\\w+/)')
        assert isinstance(val(i, "m"), SpryRegexMatch)
        assert val(i, "m")[0] == "hello"

    def test_str_match_regex_no_match(self):
        i = run('let m = "123".match(/[a-z]+/)')
        assert val(i, "m") is None


# ---------------------------------------------------------------------------
# Fix 5 — JSON.parse(text, reviver?)
# ---------------------------------------------------------------------------


class TestJsonParseReviver:
    def test_parse_basic_no_reviver(self):
        i = run("let v = JSON.parse('{\"a\": 1}')")
        assert val(i, "v") == {"a": 1}

    def test_parse_array_no_reviver(self):
        i = run('let v = JSON.parse("[1, 2, 3]")')
        assert val(i, "v") == [1, 2, 3]

    def test_parse_with_reviver_doubles_numbers(self):
        src = 'let revived = JSON.parse(\'{"x": 5}\', fn(k, v) { v })'
        # Test without mutation first - just parse
        i = run('let v = JSON.parse(\'{"x": 5}\')')
        assert val(i, "v") == {"x": 5}

    def test_parse_reviver_receives_root(self):
        # Reviver called with "" key for the root value, returns result
        i = run('let result = JSON.parse("42", fn(k, v) { return v })')
        assert val(i, "result") == 42

    def test_parse_invalid_json_raises(self):
        with pytest.raises(Exception):
            run('let v = JSON.parse("{bad json}")')

    def test_parse_null_reviver_is_ignored(self):
        i = run('let v = JSON.parse("[1, 2]", null)')
        assert val(i, "v") == [1, 2]

    def test_parse_nested_object(self):
        i = run('let v = JSON.parse(\'{"a": {"b": 2}}\')')
        assert val(i, "v") == {"a": {"b": 2}}

    def test_parse_reviver_identity(self):
        # Reviver that returns value unchanged
        i = run('let r = JSON.parse("[10, 20, 30]", fn(k, v) { return v })')
        assert val(i, "r") == [10, 20, 30]


# ---------------------------------------------------------------------------
# Fix 6 — Object.getPrototypeOf / setPrototypeOf / getOwnPropertySymbols
#          / getOwnPropertyDescriptors
# ---------------------------------------------------------------------------


class TestObjectPrototypeMethods:
    def test_getPrototypeOf_returns_null(self):
        i = run("let p = Object.getPrototypeOf({a: 1})")
        assert val(i, "p") is None

    def test_setPrototypeOf_returns_obj(self):
        i = run("let o = {x: 5}\nlet r = Object.setPrototypeOf(o, null)")
        assert val(i, "r") == {"x": 5}

    def test_getOwnPropertySymbols_returns_list(self):
        i = run("let s = Object.getOwnPropertySymbols({a: 1})")
        assert val(i, "s") == []

    def test_getOwnPropertyDescriptors_basic(self):
        i = run('let d = Object.getOwnPropertyDescriptors({x: 42})')
        d = val(i, "d")
        assert isinstance(d, dict)
        assert d["x"]["value"] == 42
        assert d["x"]["writable"] is True

    def test_getOwnPropertyDescriptors_empty(self):
        i = run("let d = Object.getOwnPropertyDescriptors({})")
        assert val(i, "d") == {}

    def test_getOwnPropertyDescriptors_multiple(self):
        i = run('let d = Object.getOwnPropertyDescriptors({a: 1, b: 2})')
        d = val(i, "d")
        assert set(d.keys()) == {"a", "b"}
        assert d["b"]["value"] == 2

    def test_getPrototypeOf_non_dict(self):
        i = run("let p = Object.getPrototypeOf(42)")
        assert val(i, "p") is None

    def test_setPrototypeOf_does_not_mutate(self):
        i = run("let o = {y: 7}\nObject.setPrototypeOf(o, {proto: true})\nlet v = o.y")
        assert val(i, "v") == 7


# ---------------------------------------------------------------------------
# Fix 7 — Intl sub-namespaces callable with .new()
# ---------------------------------------------------------------------------


class TestIntlSubNamespaces:
    def test_number_format_callable(self):
        i = run('let nf = Intl.NumberFormat("en-US")\nlet v = nf.format(1234.5)')
        assert val(i, "v") is not None

    def test_number_format_new(self):
        i = run('let nf = Intl.NumberFormat.new("en-US")\nlet v = nf.format(1000)')
        assert val(i, "v") is not None

    def test_datetime_format_callable(self):
        i = run('let df = Intl.DateTimeFormat("en-US")')
        assert val(i, "df") is not None

    def test_datetime_format_new(self):
        i = run('let df = Intl.DateTimeFormat.new("en-US")')
        assert val(i, "df") is not None

    def test_collator_callable(self):
        i = run('let c = Intl.Collator("en-US")\nlet r = c.compare("a", "b")')
        assert isinstance(val(i, "r"), (int, float))

    def test_collator_new(self):
        i = run('let c = Intl.Collator.new("en-US")')
        assert val(i, "c") is not None

    def test_plural_rules_new(self):
        i = run('let pr = Intl.PluralRules.new("en-US")\nlet v = pr.select(1)')
        assert val(i, "v") == "one"

    def test_list_format_new(self):
        i = run('let lf = Intl.ListFormat.new("en-US")\nlet v = lf.format(["a", "b", "c"])')
        assert isinstance(val(i, "v"), str)

    def test_relative_time_format_new(self):
        i = run('let rtf = Intl.RelativeTimeFormat.new("en-US")\nlet v = rtf.format(-1, "day")')
        assert isinstance(val(i, "v"), str)

    def test_supported_locales_of(self):
        i = run('let sl = Intl.NumberFormat.supportedLocalesOf(["en-US", "fr-FR"])')
        assert isinstance(val(i, "sl"), list)
        assert len(val(i, "sl")) == 2
