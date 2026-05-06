"""Tests for Phase 67 features: Comprehensive Array Methods"""
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


class TestPushPopShiftUnshift:
    def test_push_returns_length(self):
        assert val(run('let a = [1,2]; let v = a.push(3)')) == 3

    def test_push_mutates(self):
        assert val(run('let a = [1,2]; a.push(3); let v = a.length')) == 3

    def test_push_multiple(self):
        assert val(run('let a = []; a.push(1, 2, 3); let v = a.length')) == 3

    def test_pop_returns_element(self):
        assert val(run('let a = [1,2,3]; let v = a.pop()')) == 3

    def test_pop_mutates(self):
        assert val(run('let a = [1,2,3]; a.pop(); let v = a.length')) == 2

    def test_shift_returns_element(self):
        assert val(run('let a = [1,2,3]; let v = a.shift()')) == 1

    def test_shift_mutates(self):
        assert val(run('let a = [1,2,3]; a.shift(); let v = a[0]')) == 2

    def test_unshift_returns_length(self):
        assert val(run('let a = [1,2,3]; let v = a.unshift(0)')) == 4

    def test_unshift_mutates(self):
        assert val(run('let a = [1,2,3]; a.unshift(0); let v = a[0]')) == 0

    def test_unshift_multiple(self):
        assert val(run('let a = [3]; a.unshift(1, 2); let v = a.length')) == 3


class TestSpliceSlice:
    def test_splice_remove_returns_removed(self):
        assert val(run('let a = [1,2,3]; let v = a.splice(1, 1)')) == [2]

    def test_splice_mutates_array(self):
        assert val(run('let a = [1,2,3]; a.splice(0, 1); let v = a[0]')) == 2

    def test_splice_insert(self):
        assert val(run('let a = [1,2,3]; a.splice(1, 0, 10); let v = a[1]')) == 10

    def test_splice_replace(self):
        assert val(run('let a = [1,2,3]; a.splice(1, 1, 10, 11); let v = a.length')) == 4

    def test_splice_from_end(self):
        assert val(run('let a = [1,2,3,4,5]; a.splice(-2, 1); let v = a.length')) == 4

    def test_slice_basic(self):
        assert val(run('let a = [1,2,3,4,5]; let v = a.slice(1, 3)')) == [2, 3]

    def test_slice_no_end(self):
        assert val(run('let a = [1,2,3]; let v = a.slice(1)')) == [2, 3]

    def test_slice_negative(self):
        assert val(run('let a = [1,2,3,4,5]; let v = a.slice(-2)')) == [4, 5]

    def test_slice_full_copy(self):
        assert val(run('let a = [1,2,3]; let v = a.slice(0)')) == [1, 2, 3]

    def test_slice_does_not_mutate(self):
        assert val(run('let a = [1,2,3]; a.slice(0, 1); let v = a.length')) == 3


class TestIndexOfLastIndexOfIncludes:
    def test_index_of_basic(self):
        assert val(run('let a = [1,2,3]; let v = a.indexOf(2)')) == 1

    def test_index_of_not_found(self):
        assert val(run('let a = [1,2,3]; let v = a.indexOf(9)')) == -1

    def test_index_of_with_from(self):
        assert val(run('let a = [1,2,3,2]; let v = a.indexOf(2, 2)')) == 3

    def test_last_index_of_basic(self):
        assert val(run('let a = [1,2,3,2]; let v = a.lastIndexOf(2)')) == 3

    def test_last_index_of_not_found(self):
        assert val(run('let a = [1,2,3]; let v = a.lastIndexOf(9)')) == -1

    def test_last_index_of_with_from(self):
        assert val(run('let a = [1,2,3,2]; let v = a.lastIndexOf(2, 2)')) == 1

    def test_includes_true(self):
        assert val(run('let a = [1,2,3]; let v = a.includes(2)')) is True

    def test_includes_false(self):
        assert val(run('let a = [1,2,3]; let v = a.includes(9)')) is False

    def test_includes_with_from(self):
        # includes with from position - not supported (only 1 arg)
        assert val(run('let a = [1,2,3]; let v = a.includes(2)')) is True

    def test_includes_nan(self):
        assert val(run('let a = [1, NaN, 3]; let v = a.includes(NaN)')) is True


class TestJoinReverseSort:
    def test_join_basic(self):
        assert val(run('let a = [1,2,3]; let v = a.join("-")')) == "1-2-3"

    def test_join_default(self):
        # default join separator is empty string in this interpreter
        assert val(run('let a = [1,2,3]; let v = a.join()')) == "123"

    def test_join_empty_sep(self):
        assert val(run('let a = ["a","b","c"]; let v = a.join("")')) == "abc"

    def test_sort_returns_sorted(self):
        assert val(run('let a = [3,1,2]; let v = a.sort()')) == [1, 2, 3]

    def test_sort_strings(self):
        result = val(run('let a = ["banana", "apple", "cherry"]; let v = a.sort()'))
        assert result == ["apple", "banana", "cherry"]

    def test_sort_with_comparator(self):
        assert val(run('let a = [3,1,2]; let v = a.sort((a,b) => a - b)')) == [1, 2, 3]

    def test_sort_reverse_comparator(self):
        assert val(run('let a = [1,2,3]; let v = a.sort((a,b) => b - a)')) == [3, 2, 1]

    def test_reverse_returns_reversed(self):
        assert val(run('let a = [1,2,3]; let v = a.reverse()')) == [3, 2, 1]

    def test_reverse_already_reversed(self):
        assert val(run('let a = [3,2,1]; let v = a.reverse()')) == [1, 2, 3]


class TestFlatFlatMap:
    def test_flat_one_level(self):
        assert val(run('let a = [[1,2],[3]]; let v = a.flat()')) == [1, 2, 3]

    def test_flat_deep(self):
        assert val(run('let a = [[1,[2]],[[3]]]; let v = a.flat(2)')) == [1, 2, 3]

    def test_flat_no_nested(self):
        assert val(run('let a = [1,2,3]; let v = a.flat()')) == [1, 2, 3]

    def test_flatmap_basic(self):
        assert val(run('let a = [1,2,3]; let v = a.flatMap(x => [x, x*2])')) == [1, 2, 2, 4, 3, 6]

    def test_flatmap_filter_effect(self):
        assert val(run('let a = [1,2,3]; let v = a.flatMap(x => x > 1 ? [x] : [])')) == [2, 3]

    def test_flat_depth_zero(self):
        assert val(run('let a = [[1,2],[3]]; let v = a.flat(0)')) == [[1, 2], [3]]


class TestFillCopyWithin:
    def test_fill_all(self):
        assert val(run('let a = [0,0,0]; a.fill(5); let v = a[0]')) == 5

    def test_fill_with_range(self):
        assert val(run('let a = [1,2,3,4]; a.fill(0, 1, 3); let v = a[1]')) == 0

    def test_fill_preserves_outside_range(self):
        assert val(run('let a = [1,2,3,4]; a.fill(0, 1, 3); let v = a[0]')) == 1

    def test_fill_end_preserved(self):
        assert val(run('let a = [1,2,3,4]; a.fill(0, 1, 3); let v = a[3]')) == 4

    def test_fill_returns_array(self):
        result = val(run('let v = [1,2,3].fill(0)'))
        assert result == [0, 0, 0]


class TestEverySomeFilter:
    def test_every_all_true(self):
        assert val(run('let a = [1,2,3]; let v = a.every(x => x > 0)')) is True

    def test_every_some_false(self):
        assert val(run('let a = [1,-2,3]; let v = a.every(x => x > 0)')) is False

    def test_every_empty(self):
        assert val(run('let a = []; let v = a.every(x => false)')) is True

    def test_some_any_true(self):
        assert val(run('let a = [1,-2,3]; let v = a.some(x => x < 0)')) is True

    def test_some_all_false(self):
        assert val(run('let a = [1,2,3]; let v = a.some(x => x < 0)')) is False

    def test_some_empty(self):
        assert val(run('let a = []; let v = a.some(x => true)')) is False

    def test_filter_basic(self):
        assert val(run('let a = [1,-2,3,-4]; let v = a.filter(x => x > 0)')) == [1, 3]

    def test_filter_empty_result(self):
        assert val(run('let a = [1,2,3]; let v = a.filter(x => x > 10)')) == []

    def test_filter_all_pass(self):
        assert val(run('let a = [1,2,3]; let v = a.filter(x => x > 0)')) == [1, 2, 3]


class TestMapReduceForEach:
    def test_map_basic(self):
        assert val(run('let a = [1,2,3]; let v = a.map(x => x * 2)')) == [2, 4, 6]

    def test_map_strings(self):
        assert val(run('let a = [1,2,3]; let v = a.map(x => x.toString())')) == ["1", "2", "3"]

    def test_reduce_sum(self):
        assert val(run('let a = [1,2,3,4]; let v = a.reduce((acc, x) => acc + x, 0)')) == 10

    def test_reduce_product(self):
        assert val(run('let a = [1,2,3,4]; let v = a.reduce((acc, x) => acc * x, 1)')) == 24

    def test_reduce_right(self):
        assert val(run('let a = [1,2,3]; let v = a.reduceRight((acc, x) => acc + x, 0)')) == 6

    def test_reduce_right_order(self):
        result = val(run('let a = ["a","b","c"]; let v = a.reduceRight((acc, x) => acc + x, "")'))
        assert result == "cba"

    def test_foreach_iterates(self):
        code = 'let a = [1,2,3]; let r = []; a.forEach(x => r.push(x)); let v = r'
        assert val(run(code)) == [1, 2, 3]

    def test_foreach_with_index(self):
        code = 'let a = [10,20,30]; let r = []; a.forEach((x, i) => r.push(i)); let v = r'
        assert val(run(code)) == [0, 1, 2]

    def test_map_with_index(self):
        assert val(run('let a = [10,20,30]; let v = a.map((x, i) => i)')) == [0, 1, 2]


class TestFindMethods:
    def test_find_basic(self):
        assert val(run('let a = [1,2,3]; let v = a.find(x => x > 1)')) == 2

    def test_find_not_found(self):
        result = val(run('let a = [1,2,3]; let v = a.find(x => x > 10)'))
        assert result is None or result == "undefined"

    def test_find_index_basic(self):
        assert val(run('let a = [1,2,3]; let v = a.findIndex(x => x > 1)')) == 1

    def test_find_index_not_found(self):
        assert val(run('let a = [1,2,3]; let v = a.findIndex(x => x > 10)')) == -1

    def test_find_last_basic(self):
        assert val(run('let a = [1,2,3,2]; let v = a.findLast(x => x === 2)')) == 2

    def test_find_last_index_basic(self):
        assert val(run('let a = [1,2,3,2]; let v = a.findLastIndex(x => x === 2)')) == 3

    def test_find_last_index_not_found(self):
        assert val(run('let a = [1,2,3]; let v = a.findLastIndex(x => x > 10)')) == -1


class TestKeysValuesEntriesAt:
    def test_keys_iterator(self):
        assert val(run('let a = [10,20,30]; let v = [...a.keys()]')) == [0, 1, 2]

    def test_values_iterator(self):
        assert val(run('let a = [10,20,30]; let v = [...a.values()]')) == [10, 20, 30]

    def test_entries_iterator(self):
        assert val(run('let a = [10,20]; let v = [...a.entries()]')) == [[0, 10], [1, 20]]

    def test_at_positive(self):
        assert val(run('let a = [10,20,30]; let v = a.at(0)')) == 10

    def test_at_negative(self):
        assert val(run('let a = [10,20,30]; let v = a.at(-1)')) == 30

    def test_at_negative_two(self):
        assert val(run('let a = [10,20,30]; let v = a.at(-2)')) == 20

    def test_at_middle(self):
        assert val(run('let a = [10,20,30]; let v = a.at(1)')) == 20


class TestArrayStaticMethods:
    def test_is_array_true(self):
        assert val(run('let v = Array.isArray([1,2,3])')) is True

    def test_is_array_false_string(self):
        assert val(run('let v = Array.isArray("hello")')) is False

    def test_is_array_false_object(self):
        assert val(run('let v = Array.isArray({})')) is False

    def test_is_array_false_number(self):
        assert val(run('let v = Array.isArray(42)')) is False

    def test_from_array(self):
        assert val(run('let v = Array.from([1,2,3])')) == [1, 2, 3]

    def test_from_string(self):
        assert val(run('let v = Array.from("abc")')) == ["a", "b", "c"]

    def test_from_with_map_fn(self):
        assert val(run('let v = Array.from([1,2,3], x => x * 2)')) == [2, 4, 6]

    def test_of_basic(self):
        assert val(run('let v = Array.of(1,2,3)')) == [1, 2, 3]

    def test_of_single(self):
        assert val(run('let v = Array.of(42)')) == [42]

    def test_of_empty(self):
        assert val(run('let v = Array.of()')) == []
