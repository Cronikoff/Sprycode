"""Tests for Phase 93: Array Advanced Methods
- Array.from with map function, Array.of
- entries(), keys(), values() iterators
- every(), some(), includes(), indexOf(), lastIndexOf()
- fill(), copyWithin(), flat(), flatMap(), at()
- Array.isArray(), sort stability, sort with compare
"""
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


# ── Array.from with mapper ─────────────────────────────────────────────────────

class TestArrayFromMap:
    def test_from_length_identity(self):
        i = run('let v = Array.from({length: 3}, (_, i) => i)')
        assert val(i) == [0, 1, 2]

    def test_from_length_double(self):
        i = run('let v = Array.from({length: 4}, (_, i) => i * 2)')
        assert val(i) == [0, 2, 4, 6]

    def test_from_length_fill_value(self):
        i = run('let v = Array.from({length: 3}, () => 7)')
        assert val(i) == [7, 7, 7]

    def test_from_string(self):
        i = run('let v = Array.from("abc")')
        assert val(i) == ["a", "b", "c"]

    def test_from_iterable(self):
        i = run('let v = Array.from([1, 2, 3])')
        assert val(i) == [1, 2, 3]


# ── Array.of ──────────────────────────────────────────────────────────────────

class TestArrayOf:
    def test_of_three_elements(self):
        i = run('let v = Array.of(1, 2, 3)')
        assert val(i) == [1, 2, 3]

    def test_of_single(self):
        i = run('let v = Array.of(7)')
        assert val(i) == [7]

    def test_of_mixed(self):
        i = run('let v = Array.of("a", 1, true)')
        assert val(i) == ["a", 1, True]

    def test_of_empty(self):
        i = run('let v = Array.of()')
        assert val(i) == []


# ── arr.entries() ─────────────────────────────────────────────────────────────

class TestArrayEntries:
    def test_entries_spread(self):
        i = run('let a = ["a", "b", "c"]; let v = [...a.entries()]')
        assert val(i) == [[0, "a"], [1, "b"], [2, "c"]]

    def test_entries_length(self):
        i = run('let a = [10, 20, 30]; let v = [...a.entries()].length')
        assert val(i) == 3

    def test_entries_first_pair(self):
        i = run('let a = ["x", "y"]; let v = [...a.entries()][0]')
        assert val(i) == [0, "x"]

    def test_entries_for_of(self):
        i = run('''
let a = [10, 20, 30];
let sum = 0;
for (let [idx, val] of a.entries()) { sum += idx * val; }
let v = sum;
''')
        assert val(i) == 80  # 0*10 + 1*20 + 2*30


# ── arr.keys() ────────────────────────────────────────────────────────────────

class TestArrayKeys:
    def test_keys_spread(self):
        i = run('let a = ["a", "b"]; let v = [...a.keys()]')
        assert val(i) == [0, 1]

    def test_keys_three(self):
        i = run('let a = [10, 20, 30]; let v = [...a.keys()]')
        assert val(i) == [0, 1, 2]

    def test_keys_sum(self):
        i = run('''
let a = [5, 5, 5];
let s = 0;
for (let k of a.keys()) { s += k; }
let v = s;
''')
        assert val(i) == 3  # 0+1+2


# ── arr.values() ──────────────────────────────────────────────────────────────

class TestArrayValues:
    def test_values_spread(self):
        i = run('let a = [10, 20]; let v = [...a.values()]')
        assert val(i) == [10, 20]

    def test_values_three(self):
        i = run('let a = [1, 2, 3]; let v = [...a.values()]')
        assert val(i) == [1, 2, 3]

    def test_values_for_of(self):
        i = run('''
let a = [1, 2, 3];
let sum = 0;
for (let v of a.values()) { sum += v; }
let v = sum;
''')
        assert val(i) == 6


# ── arr.every() ───────────────────────────────────────────────────────────────

class TestArrayEvery:
    def test_every_true(self):
        i = run('let v = [2, 4, 6].every(x => x % 2 === 0)')
        assert val(i) is True

    def test_every_false(self):
        i = run('let v = [2, 3, 6].every(x => x % 2 === 0)')
        assert val(i) is False

    def test_every_empty(self):
        i = run('let v = [].every(x => x > 0)')
        assert val(i) is True

    def test_every_gt_zero(self):
        i = run('let v = [1, 2, 3].every(x => x > 0)')
        assert val(i) is True

    def test_every_with_index(self):
        i = run('let v = [0, 1, 2].every((x, i) => x === i)')
        assert val(i) is True


# ── arr.some() ────────────────────────────────────────────────────────────────

class TestArraySome:
    def test_some_true(self):
        i = run('let v = [1, 2, 3].some(x => x % 2 === 0)')
        assert val(i) is True

    def test_some_false(self):
        i = run('let v = [1, 3, 5].some(x => x % 2 === 0)')
        assert val(i) is False

    def test_some_empty(self):
        i = run('let v = [].some(x => x > 0)')
        assert val(i) is False

    def test_some_negative(self):
        i = run('let v = [1, -2, 3].some(x => x < 0)')
        assert val(i) is True


# ── arr.includes() ────────────────────────────────────────────────────────────

class TestArrayIncludes:
    def test_includes_true(self):
        i = run('let v = [1, 2, 3].includes(2)')
        assert val(i) is True

    def test_includes_false(self):
        i = run('let v = [1, 2, 3].includes(5)')
        assert val(i) is False

    def test_includes_string(self):
        i = run('let v = ["a", "b", "c"].includes("b")')
        assert val(i) is True

    def test_includes_first(self):
        i = run('let v = [10, 20, 30].includes(10)')
        assert val(i) is True

    def test_includes_last(self):
        i = run('let v = [10, 20, 30].includes(30)')
        assert val(i) is True


# ── arr.indexOf() ─────────────────────────────────────────────────────────────

class TestArrayIndexOf:
    def test_indexOf_found(self):
        i = run('let v = [1, 2, 3, 2].indexOf(2)')
        assert val(i) == 1

    def test_indexOf_not_found(self):
        i = run('let v = [1, 2, 3].indexOf(5)')
        assert val(i) == -1

    def test_indexOf_first(self):
        i = run('let v = [5, 5, 5].indexOf(5)')
        assert val(i) == 0

    def test_indexOf_string(self):
        i = run('let v = ["a", "b", "c"].indexOf("c")')
        assert val(i) == 2


# ── arr.lastIndexOf() ─────────────────────────────────────────────────────────

class TestArrayLastIndexOf:
    def test_lastIndexOf_found(self):
        i = run('let v = [1, 2, 3, 2].lastIndexOf(2)')
        assert val(i) == 3

    def test_lastIndexOf_single(self):
        i = run('let v = [1, 2, 3].lastIndexOf(1)')
        assert val(i) == 0

    def test_lastIndexOf_not_found(self):
        i = run('let v = [1, 2, 3].lastIndexOf(9)')
        assert val(i) == -1

    def test_lastIndexOf_all_same(self):
        i = run('let v = [5, 5, 5].lastIndexOf(5)')
        assert val(i) == 2


# ── arr.fill() ────────────────────────────────────────────────────────────────

class TestArrayFill:
    def test_fill_range(self):
        i = run('let a = [1, 2, 3, 4, 5]; a.fill(0, 2, 4); let v = a')
        assert val(i) == [1, 2, 0, 0, 5]

    def test_fill_all(self):
        i = run('let a = [1, 2, 3]; a.fill(9); let v = a')
        assert val(i) == [9, 9, 9]

    def test_fill_from_start(self):
        i = run('let a = [1, 2, 3, 4]; a.fill(7, 1); let v = a')
        assert val(i) == [1, 7, 7, 7]

    def test_fill_empty_range(self):
        i = run('let a = [1, 2, 3]; a.fill(0, 1, 1); let v = a')
        assert val(i) == [1, 2, 3]


# ── arr.copyWithin() ──────────────────────────────────────────────────────────

class TestArrayCopyWithin:
    def test_copyWithin_basic(self):
        i = run('let a = [1, 2, 3, 4, 5]; let v = a.copyWithin(0, 3, 5)')
        assert val(i) == [4, 5, 3, 4, 5]

    def test_copyWithin_partial(self):
        i = run('let v = [1, 2, 3, 4, 5].copyWithin(1, 3)')
        assert val(i) == [1, 4, 5, 4, 5]

    def test_copyWithin_returns_array(self):
        i = run('let v = [1, 2, 3].copyWithin(0, 2)')
        assert val(i) == [3, 2, 3]


# ── arr.flat() ────────────────────────────────────────────────────────────────

class TestArrayFlat:
    def test_flat_infinity(self):
        i = run('let v = [1, [2, [3, [4]]]].flat(Infinity)')
        assert val(i) == [1, 2, 3, 4]

    def test_flat_depth_1(self):
        i = run('let v = [1, [2, [3]]].flat(1)')
        assert val(i) == [1, 2, [3]]

    def test_flat_depth_2(self):
        i = run('let v = [1, [2, [3, [4]]]].flat(2)')
        assert val(i) == [1, 2, 3, [4]]

    def test_flat_already_flat(self):
        i = run('let v = [1, 2, 3].flat()')
        assert val(i) == [1, 2, 3]


# ── arr.flatMap() ─────────────────────────────────────────────────────────────

class TestArrayFlatMap:
    def test_flatMap_double(self):
        i = run('let v = [1, 2, 3].flatMap(x => [x, x * 2])')
        assert val(i) == [1, 2, 2, 4, 3, 6]

    def test_flatMap_string_split(self):
        i = run('let v = ["hello world", "foo bar"].flatMap(s => s.split(" "))')
        assert val(i) == ["hello", "world", "foo", "bar"]

    def test_flatMap_filter(self):
        i = run('let v = [1, 2, 3, 4].flatMap(x => x % 2 === 0 ? [x] : [])')
        assert val(i) == [2, 4]


# ── arr.at() ──────────────────────────────────────────────────────────────────

class TestArrayAt:
    def test_at_last(self):
        i = run('let v = [1, 2, 3].at(-1)')
        assert val(i) == 3

    def test_at_second_last(self):
        i = run('let v = [1, 2, 3].at(-2)')
        assert val(i) == 2

    def test_at_zero(self):
        i = run('let v = [10, 20, 30].at(0)')
        assert val(i) == 10

    def test_at_positive(self):
        i = run('let v = [10, 20, 30].at(1)')
        assert val(i) == 20


# ── Array.isArray() ───────────────────────────────────────────────────────────

class TestArrayIsArray:
    def test_isArray_empty(self):
        i = run('let v = Array.isArray([])')
        assert val(i) is True

    def test_isArray_non_empty(self):
        i = run('let v = Array.isArray([1, 2, 3])')
        assert val(i) is True

    def test_isArray_object(self):
        i = run('let v = Array.isArray({})')
        assert val(i) is False

    def test_isArray_string(self):
        i = run('let v = Array.isArray("hello")')
        assert val(i) is False

    def test_isArray_number(self):
        i = run('let v = Array.isArray(42)')
        assert val(i) is False

    def test_isArray_null(self):
        i = run('let v = Array.isArray(null)')
        assert val(i) is False


# ── Sort ──────────────────────────────────────────────────────────────────────

class TestArraySort:
    def test_sort_default(self):
        i = run('let v = [3, 1, 2].sort()')
        assert val(i) == [1, 2, 3]

    def test_sort_ascending_compare(self):
        i = run('let v = [10, 1, 5].sort((a, b) => a - b)')
        assert val(i) == [1, 5, 10]

    def test_sort_descending_compare(self):
        i = run('let v = [10, 1, 5].sort((a, b) => b - a)')
        assert val(i) == [10, 5, 1]

    def test_sort_strings(self):
        i = run('let v = ["banana", "apple", "cherry"].sort()')
        assert val(i) == ["apple", "banana", "cherry"]

    def test_sort_stability_equal_keys(self):
        i = run('''
let arr = [{k: 1, i: 0}, {k: 1, i: 1}, {k: 2, i: 2}];
let sorted = arr.sort((a, b) => a.k - b.k);
let v = sorted[0].i;
''')
        assert val(i) == 0
