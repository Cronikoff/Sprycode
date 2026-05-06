"""Tests for Phase 78 features: JSON Operations."""
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


class TestJSONStringifyBasic:
    def test_stringify_number(self):
        assert val(run("let v = JSON.stringify(42)")) == "42"

    def test_stringify_string(self):
        assert val(run('let v = JSON.stringify("hello")')) == '"hello"'

    def test_stringify_true(self):
        assert val(run("let v = JSON.stringify(true)")) == "true"

    def test_stringify_false(self):
        assert val(run("let v = JSON.stringify(false)")) == "false"

    def test_stringify_null(self):
        assert val(run("let v = JSON.stringify(null)")) == "null"

    def test_stringify_empty_object(self):
        assert val(run("let v = JSON.stringify({})")) == "{}"

    def test_stringify_empty_array(self):
        assert val(run("let v = JSON.stringify([])")) == "[]"

    def test_stringify_simple_object(self):
        assert val(run("let v = JSON.stringify({a: 1})")) == '{"a":1}'

    def test_stringify_array(self):
        assert val(run("let v = JSON.stringify([1, 2, 3])")) == "[1,2,3]"

    def test_stringify_nested_object(self):
        assert val(run("let v = JSON.stringify({a: {b: 1}})")) == '{"a":{"b":1}}'

    def test_stringify_nested_array(self):
        assert val(run("let v = JSON.stringify([1, [2, 3]])")) == "[1,[2,3]]"

    def test_stringify_mixed_object(self):
        src = 'let v = JSON.stringify({a: 1, b: "hello", c: true})'
        result = val(run(src))
        assert '"a":1' in result
        assert '"b":"hello"' in result
        assert '"c":true' in result


class TestJSONStringifyAdvanced:
    def test_stringify_with_indent(self):
        src = "let v = JSON.stringify({a: 1}, null, 2)"
        result = val(run(src))
        assert "\n" in result
        assert "  " in result

    def test_stringify_indent_contains_key(self):
        src = "let v = JSON.stringify({a: 1}, null, 2)"
        result = val(run(src))
        assert '"a"' in result

    def test_stringify_key_filter_array(self):
        src = 'let v = JSON.stringify({a: 1, b: 2, c: 3}, ["a", "c"])'
        result = val(run(src))
        assert '"a":1' in result
        assert '"c":3' in result
        assert '"b"' not in result

    def test_stringify_replacer_function(self):
        src = """
let v = JSON.stringify({a: 1, b: 2}, function(key, value) {
  if (key === 'b') return undefined;
  return value;
});
"""
        result = val(run(src))
        assert '"a":1' in result
        assert '"b"' not in result

    def test_stringify_undefined_in_object_omitted(self):
        src = "let v = JSON.stringify({a: 1, b: undefined})"
        result = val(run(src))
        assert '"a":1' in result
        assert '"b"' not in result

    def test_stringify_undefined_in_array_is_null(self):
        src = "let v = JSON.stringify([1, undefined, 3])"
        assert val(run(src)) == "[1,null,3]"

    def test_stringify_roundtrip(self):
        src = "let obj = {a: 1, b: [2, 3]}; let v = JSON.stringify(JSON.parse(JSON.stringify(obj)))"
        result = val(run(src))
        assert '"a":1' in result
        assert '"b":[2,3]' in result


class TestJSONParse:
    def test_parse_number(self):
        assert val(run("let v = JSON.parse('42')")) == 42

    def test_parse_string(self):
        assert val(run('let v = JSON.parse(\'"hello"\')')) == "hello"

    def test_parse_true(self):
        assert val(run("let v = JSON.parse('true')")) is True

    def test_parse_false(self):
        assert val(run("let v = JSON.parse('false')")) is False

    def test_parse_null(self):
        assert val(run("let v = JSON.parse('null')")) is None

    def test_parse_array(self):
        assert val(run("let v = JSON.parse('[1,2,3]')")) == [1, 2, 3]

    def test_parse_object(self):
        src = "let v = JSON.parse('{\"a\":1}')"
        result = val(run(src))
        assert result == {"a": 1}

    def test_parse_nested(self):
        src = "let v = JSON.parse('{\"a\":{\"b\":1}}')"
        result = val(run(src))
        assert result == {"a": {"b": 1}}

    def test_parse_nested_array(self):
        src = "let v = JSON.parse('[1,[2,3]]')"
        assert val(run(src)) == [1, [2, 3]]

    def test_parse_with_reviver(self):
        src = """
let v = JSON.parse('{\"a\":1,\"b\":2}', function(key, value) {
  if (typeof value === 'number') return value * 2;
  return value;
});
"""
        result = val(run(src))
        assert result["a"] == 2
        assert result["b"] == 4


class TestJSONRoundtrip:
    def test_roundtrip_object(self):
        src = "let obj = {a: 1}; let v = JSON.parse(JSON.stringify(obj))"
        assert val(run(src)) == {"a": 1}

    def test_roundtrip_array(self):
        src = "let arr = [1, 2, 3]; let v = JSON.parse(JSON.stringify(arr))"
        assert val(run(src)) == [1, 2, 3]

    def test_roundtrip_nested(self):
        src = "let v = JSON.parse(JSON.stringify({x: {y: [1, 2]}}))"
        assert val(run(src)) == {"x": {"y": [1, 2]}}

    def test_roundtrip_preserves_types(self):
        src = "let v = JSON.parse(JSON.stringify({a: 1, b: 'str', c: true}))"
        result = val(run(src))
        assert result["a"] == 1
        assert result["b"] == "str"
        assert result["c"] is True

    def test_stringify_float(self):
        assert val(run("let v = JSON.stringify(3.14)")) == "3.14"

    def test_stringify_zero(self):
        assert val(run("let v = JSON.stringify(0)")) == "0"

    def test_parse_float(self):
        assert val(run("let v = JSON.parse('3.14')")) == pytest.approx(3.14)

    def test_stringify_negative(self):
        assert val(run("let v = JSON.stringify(-5)")) == "-5"
