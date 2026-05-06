"""Tests for Phase 88: Spread and Rest Advanced"""
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


def test_spread_array_in_function_call():
    i = run('function sum(a, b, c) { return a + b + c; } let arr = [1, 2, 3]; let v = sum(...arr);')
    assert val(i) == 6


def test_spread_array_into_array():
    i = run('let a = [1, 2]; let b = [3, 4]; let v = [...a, ...b];')
    assert val(i) == [1, 2, 3, 4]


def test_spread_object():
    i = run('let a = {x: 1}; let b = {y: 2}; let v = {...a, ...b};')
    assert val(i) == {"x": 1, "y": 2}


def test_rest_params():
    i = run('function f(a, ...rest) { return rest; } let v = f(1, 2, 3);')
    assert val(i) == [2, 3]


def test_rest_captures_remaining():
    i = run('function f(a, b, ...rest) { return rest; } let v = f(1, 2, 3, 4);')
    assert val(i) == [3, 4]


def test_rest_empty():
    i = run('function f(a, ...rest) { return rest; } let v = f(1);')
    assert val(i) == []


def test_spread_and_rest_combined():
    i = run('function f(a, ...rest) { return rest; } let arr = [10, 20, 30]; let v = f(...arr);')
    assert val(i) == [20, 30]


def test_spread_string():
    i = run('let v = [..."hello"];')
    assert val(i) == ["h", "e", "l", "l", "o"]


def test_spread_set():
    i = run('let s = new Set([1, 2, 3]); let v = [...s];')
    assert val(i) == [1, 2, 3]


def test_spread_map_entries():
    i = run('let m = new Map([["a", 1]]); let v = [...m];')
    assert val(i) == [["a", 1]]


def test_object_spread_with_override():
    i = run('let obj = {a: 1, b: 2}; let v = {...obj, b: 99};')
    assert val(i) == {"a": 1, "b": 99}


def test_array_spread_in_middle():
    i = run('let arr = [2, 3]; let v = [1, ...arr, 99];')
    assert val(i) == [1, 2, 3, 99]


def test_math_max_spread():
    i = run('let arr = [1, 5, 3]; let v = Math.max(...arr);')
    assert val(i) == 5


def test_fn_length_no_rest():
    i = run('function f(a, ...rest) {} let v = f.length;')
    assert val(i) == 1


def test_spread_empty_array():
    i = run('let v = [...[], 1, 2];')
    assert val(i) == [1, 2]


def test_spread_two_empty_arrays():
    i = run('let v = [...[], ...[]];')
    assert val(i) == []


def test_spread_prepend():
    i = run('let arr = [2, 3]; let v = [1, ...arr];')
    assert val(i) == [1, 2, 3]


def test_spread_append():
    i = run('let arr = [1, 2]; let v = [...arr, 3];')
    assert val(i) == [1, 2, 3]


def test_spread_object_multiple():
    i = run('let a = {x: 1}; let b = {y: 2}; let c = {z: 3}; let v = {...a, ...b, ...c};')
    assert val(i) == {"x": 1, "y": 2, "z": 3}


def test_rest_in_arrow():
    i = run('let f = (...args) => args; let v = f(1, 2, 3);')
    assert val(i) == [1, 2, 3]


def test_spread_copy_array():
    i = run('let original = [1, 2, 3]; let v = [...original]; v.push(4);')
    assert val(i) == [1, 2, 3, 4]
    assert run('let original = [1, 2, 3]; let v = [...original]; v.push(4);').globals.get("original") == [1, 2, 3]


def test_rest_single():
    i = run('function f(...args) { return args.length; } let v = f(1, 2, 3);')
    assert val(i) == 3


def test_spread_function_no_extra():
    i = run('function f(a, b) { return a + b; } let arr = [3, 7]; let v = f(...arr);')
    assert val(i) == 10


def test_spread_nested():
    i = run('let inner = [2, 3]; let v = [1, ...inner, ...[4, 5]];')
    assert val(i) == [1, 2, 3, 4, 5]


def test_object_spread_overrides():
    i = run('let defaults = {a: 1, b: 2, c: 3}; let overrides = {b: 20, c: 30}; let v = {...defaults, ...overrides};')
    assert val(i) == {"a": 1, "b": 20, "c": 30}


def test_rest_is_array():
    i = run('function f(...args) { return Array.isArray(args); } let v = f(1, 2);')
    assert val(i) is True


def test_math_min_spread():
    i = run('let arr = [5, 2, 8, 1]; let v = Math.min(...arr);')
    assert val(i) == 1
