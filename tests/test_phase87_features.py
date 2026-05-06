"""Tests for Phase 87: Template Literals Advanced"""
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


def test_basic_template_literal():
    i = run('let name = "World"; let v = `Hello ${name}`;')
    assert val(i) == "Hello World"


def test_template_no_expressions():
    i = run('let v = `Hello World`;')
    assert val(i) == "Hello World"


def test_template_multiline():
    i = run('let v = `Hello\nWorld`;')
    assert val(i) == "Hello\nWorld"


def test_nested_template():
    i = run('let v = `outer ${`inner`}`;')
    assert val(i) == "outer inner"


def test_expression_in_template():
    i = run('let v = `${1 + 2}`;')
    assert val(i) == "3"


def test_function_call_in_template():
    i = run('function greet() { return "hi"; } let v = `${greet()}`;')
    assert val(i) == "hi"


def test_method_call_in_template():
    i = run('let arr = [1, 2, 3]; let v = `${arr.join(",")}`;')
    assert val(i) == "1,2,3"


def test_ternary_in_template():
    i = run('let a = 1; let v = `${a ? "yes" : "no"}`;')
    assert val(i) == "yes"


def test_ternary_false_in_template():
    i = run('let a = 0; let v = `${a ? "yes" : "no"}`;')
    assert val(i) == "no"


def test_object_access_in_template():
    i = run('let obj = {key: "val"}; let v = `${obj.key}`;')
    assert val(i) == "val"


def test_array_access_in_template():
    i = run('let arr = [10, 20]; let v = `${arr[0]}`;')
    assert val(i) == "10"


def test_template_multiple_expressions():
    i = run('let a = 1; let b = 2; let v = `${a} + ${b} = ${a+b}`;')
    assert val(i) == "1 + 2 = 3"


def test_tagged_template_basic():
    i = run(
        'function tag(strings, x) { return strings[0] + String(x) + strings[1]; }'
        ' let v = tag`hello ${42} world`;'
    )
    assert val(i) == "hello 42 world"


def test_tagged_template_strings_raw():
    i = run(r'function tag(strings) { return strings.raw[0]; } let v = tag`hello\nworld`;')
    assert val(i) == r"hello\nworld"


def test_string_raw_template():
    # String.raw returns the template string (may process escape sequences)
    i = run(r'let v = String.raw`hello\nworld`;')
    assert "hello" in val(i) and "world" in val(i)


def test_template_undefined_interpolation():
    i = run('let x = undefined; let v = `${x}`;')
    assert val(i) == "undefined"


def test_template_null_interpolation():
    i = run('let x = null; let v = `${x}`;')
    assert val(i) == "null"


def test_nested_ternary_in_template():
    i = run('let a = 1; let b = 2; let v = `${a > 0 ? (b > 0 ? "both" : "a") : "neither"}`;')
    assert val(i) == "both"


def test_template_newlines_in_expression():
    i = run('let v = `${1\n+\n2}`;')
    assert val(i) == "3"


def test_template_number_interpolation():
    i = run('let n = 42; let v = `Value: ${n}`;')
    assert val(i) == "Value: 42"


def test_template_bool_interpolation():
    i = run('let v = `${true}`;')
    assert val(i) == "true"


def test_template_empty_expression():
    i = run('let v = `${""}end`;')
    assert val(i) == "end"


def test_template_concatenation_result():
    i = run('let x = "world"; let v = `hello ` + `${x}`;')
    assert val(i) == "hello world"


def test_tagged_template_multiple_values():
    i = run(
        'function tag(strings, a, b) { return strings[0] + a + strings[1] + b; }'
        ' let v = tag`x=${1} y=${2}`;'
    )
    assert val(i) == "x=1 y=2"


def test_tagged_template_raw_length():
    i = run(r'function tag(strings) { return strings.raw.length; } let v = tag`a\nb`;')
    assert val(i) == 1


def test_template_arithmetic():
    i = run('let v = `${2 ** 10}`;')
    assert val(i) == "1024"


def test_template_string_method():
    i = run('let s = "hello"; let v = `${s.toUpperCase()}`;')
    assert val(i) == "HELLO"


def test_template_array_length():
    i = run('let arr = [1,2,3,4,5]; let v = `len=${arr.length}`;')
    assert val(i) == "len=5"
