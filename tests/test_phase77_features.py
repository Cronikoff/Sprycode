"""Tests for Phase 77 features: Advanced Destructuring."""
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


class TestObjectDestructuringDefaults:
    def test_object_default_missing_key(self):
        src = """
const obj = {a: 5};
const {a = 1, b = 2} = obj;
let v = b;
"""
        assert val(run(src)) == 2

    def test_object_default_present_key_overrides(self):
        src = """
const obj = {a: 5};
const {a = 1, b = 2} = obj;
let v = a;
"""
        assert val(run(src)) == 5

    def test_object_default_sum(self):
        src = """
const obj = {a: 5};
const {a = 1, b = 2} = obj;
let v = a + b;
"""
        assert val(run(src)) == 7

    def test_object_default_empty_object(self):
        src = """
const {x = 10, y = 20} = {};
let v = x + y;
"""
        assert val(run(src)) == 30

    def test_object_renaming(self):
        src = """
const {a: localA} = {a: 42};
let v = localA;
"""
        assert val(run(src)) == 42

    def test_object_renaming_with_default(self):
        src = """
const {a: myA = 99} = {};
let v = myA;
"""
        assert val(run(src)) == 99


class TestArrayDestructuringDefaults:
    def test_array_default_missing(self):
        src = """
const [a = 0, b = 1] = [10];
let v = b;
"""
        assert val(run(src)) == 1

    def test_array_default_present_overrides(self):
        src = """
const [a = 0, b = 1] = [10];
let v = a;
"""
        assert val(run(src)) == 10

    def test_array_default_sum(self):
        src = """
const [a = 0, b = 1] = [10];
let v = a + b;
"""
        assert val(run(src)) == 11

    def test_skip_elements(self):
        src = """
const [, second] = [10, 20, 30];
let v = second;
"""
        assert val(run(src)) == 20

    def test_skip_to_third(self):
        src = """
const [, , third] = [10, 20, 30];
let v = third;
"""
        assert val(run(src)) == 30


class TestNestedDestructuring:
    def test_nested_object(self):
        src = """
const obj = {a: {b: 42}};
const {a: {b}} = obj;
let v = b;
"""
        assert val(run(src)) == 42

    def test_nested_array(self):
        src = """
const arr = [[1, 2], [3, 4]];
const [[a, b], [c, d]] = arr;
let v = a + b + c + d;
"""
        assert val(run(src)) == 10

    def test_nested_array_first(self):
        src = """
const [[a]] = [[5, 6], [7, 8]];
let v = a;
"""
        assert val(run(src)) == 5

    def test_mixed_nested_obj_arr(self):
        src = """
const obj = {arr: [1, 2, 3]};
const {arr: [first]} = obj;
let v = first;
"""
        assert val(run(src)) == 1

    def test_mixed_nested_arr_obj(self):
        src = """
const arr = [{x: 10}, {x: 20}];
const [{x: first}] = arr;
let v = first;
"""
        assert val(run(src)) == 10


class TestRestDestructuring:
    def test_rest_in_object(self):
        src = """
const obj = {a: 1, b: 2, c: 3};
const {a, ...rest} = obj;
let v = rest.b + rest.c;
"""
        assert val(run(src)) == 5

    def test_rest_in_object_excludes_picked(self):
        src = """
const {a, ...rest} = {a: 1, b: 2, c: 3};
let v = 'a' in rest;
"""
        assert val(run(src)) is False

    def test_rest_in_array(self):
        src = """
const [head, ...tail] = [1, 2, 3, 4];
let v = tail.length;
"""
        assert val(run(src)) == 3

    def test_rest_in_array_values(self):
        src = """
const [head, ...tail] = [1, 2, 3, 4];
let v = tail.join(',');
"""
        assert val(run(src)) == "2,3,4"

    def test_rest_in_array_head(self):
        src = """
const [head, ...tail] = [10, 20, 30];
let v = head;
"""
        assert val(run(src)) == 10


class TestDestructuringInContext:
    def test_destructuring_function_params(self):
        src = """
function add({a, b}) { return a + b; }
let v = add({a: 3, b: 4});
"""
        assert val(run(src)) == 7

    def test_arrow_fn_destructuring_params(self):
        src = """
const add = ({a, b}) => a + b;
let v = add({a: 3, b: 4});
"""
        assert val(run(src)) == 7

    def test_array_params_destructuring(self):
        src = """
function sum([first, second]) { return first + second; }
let v = sum([10, 20]);
"""
        assert val(run(src)) == 30

    def test_for_of_destructuring(self):
        src = """
let sum = 0;
for (const [k, v2] of Object.entries({a: 1, b: 2})) {
  sum += v2;
}
let v = sum;
"""
        assert val(run(src)) == 3

    def test_destructuring_return_value(self):
        src = """
function getCoords() { return {x: 10, y: 20}; }
const {x, y} = getCoords();
let v = x + y;
"""
        assert val(run(src)) == 30

    def test_swap_variables(self):
        src = """
let a = 1, b = 2;
[a, b] = [b, a];
let v = a * 10 + b;
"""
        assert val(run(src)) == 21

    def test_destructuring_array_function_return(self):
        src = """
function getPair() { return [10, 20]; }
const [x, y] = getPair();
let v = x + y;
"""
        assert val(run(src)) == 30

    def test_for_of_map_destructuring(self):
        src = """
let m = new Map();
m.set('a', 1);
m.set('b', 2);
let sum = 0;
for (const [k, v2] of m) { sum += v2; }
let v = sum;
"""
        assert val(run(src)) == 3
