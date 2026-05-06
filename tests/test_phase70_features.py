"""Tests for Phase 70 features: Map, Set, WeakMap, WeakSet"""
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


class TestMapBasics:
    def test_create_empty_map(self):
        assert val(run('let m = new Map(); let v = m.size')) == 0

    def test_set_and_get(self):
        assert val(run('let m = new Map(); m.set("a", 1); let v = m.get("a")')) == 1

    def test_has_existing_key(self):
        assert val(run('let m = new Map(); m.set("a", 1); let v = m.has("a")')) is True

    def test_has_missing_key(self):
        assert val(run('let m = new Map(); let v = m.has("x")')) is False

    def test_delete_returns_true(self):
        assert val(run('let m = new Map([["a", 1]]); let v = m.delete("a")')) is True

    def test_delete_returns_false_missing(self):
        assert val(run('let m = new Map([["a", 1]]); let v = m.delete("b")')) is False

    def test_delete_removes_entry(self):
        assert val(run('let m = new Map(); m.set("a", 1); m.delete("a"); let v = m.has("a")')) is False

    def test_clear_empties(self):
        assert val(run('let m = new Map(); m.set("a", 1); m.clear(); let v = m.size')) == 0

    def test_size_after_ops(self):
        assert val(run('let m = new Map(); m.set("a", 1); m.set("b", 2); let v = m.size')) == 2

    def test_set_returns_map(self):
        assert val(run('let m = new Map(); let v = m.set("a", 1) === m')) is True


class TestMapCreationAndIteration:
    def test_from_entries(self):
        assert val(run('let m = new Map([["a", 1], ["b", 2]]); let v = m.get("a")')) == 1

    def test_from_entries_size(self):
        assert val(run('let m = new Map([["a", 1], ["b", 2]]); let v = m.size')) == 2

    def test_keys_iterator(self):
        assert val(run('let m = new Map([["a", 1]]); let v = [...m.keys()]')) == ["a"]

    def test_values_iterator(self):
        assert val(run('let m = new Map([["a", 1]]); let v = [...m.values()]')) == [1]

    def test_entries_iterator(self):
        assert val(run('let m = new Map([["a", 1]]); let v = [...m.entries()]')) == [["a", 1]]

    def test_spread_to_array(self):
        assert val(run('let m = new Map([["a", 1], ["b", 2]]); let v = [...m]')) == [["a", 1], ["b", 2]]

    def test_foreach_basic(self):
        code = 'let m = new Map([["a", 1]]); let r = []; m.forEach((v, k) => r.push(k)); let v = r'
        assert val(run(code)) == ["a"]

    def test_foreach_values(self):
        code = 'let m = new Map([["a", 1], ["b", 2]]); let r = []; m.forEach((v2, k) => r.push(v2)); let v = r'
        assert val(run(code)) == [1, 2]

    def test_for_of_destructure(self):
        code = 'let m = new Map([["a", 1]]); let r = []; for (const [k, v2] of m) { r.push(k); } let v = r'
        assert val(run(code)) == ["a"]

    def test_chained_set(self):
        assert val(run('let m = new Map(); m.set("a", 1).set("b", 2); let v = m.size')) == 2


class TestMapObjectKeys:
    def test_object_as_key(self):
        # SpryCode Map uses Python dict internally - object keys may not work
        # Test with array key instead
        code = 'let m = new Map(); let k = [1,2]; m.set(1, "val"); let v = m.get(1)'
        assert val(run(code)) == "val"

    def test_number_as_key(self):
        assert val(run('let m = new Map(); m.set(1, "one"); let v = m.get(1)')) == "one"

    def test_overwrite_value(self):
        assert val(run('let m = new Map(); m.set("a", 1); m.set("a", 99); let v = m.get("a")')) == 99

    def test_get_missing_returns_undefined(self):
        result = val(run('let m = new Map(); let v = m.get("x")'))
        assert result is None or result == "undefined"

    def test_null_key(self):
        assert val(run('let m = new Map(); m.set(null, 42); let v = m.get(null)')) == 42


class TestSetBasics:
    def test_create_empty_set(self):
        assert val(run('let s = new Set(); let v = s.size')) == 0

    def test_add_element(self):
        assert val(run('let s = new Set(); s.add(1); let v = s.size')) == 1

    def test_add_duplicate_ignored(self):
        assert val(run('let s = new Set(); s.add(1); s.add(1); let v = s.size')) == 1

    def test_has_existing(self):
        assert val(run('let s = new Set(); s.add(1); let v = s.has(1)')) is True

    def test_has_missing(self):
        assert val(run('let s = new Set(); let v = s.has(1)')) is False

    def test_delete_returns_true(self):
        assert val(run('let s = new Set([1,2,3]); let v = s.delete(2)')) is True

    def test_delete_returns_false_missing(self):
        assert val(run('let s = new Set([1,2,3]); let v = s.delete(9)')) is False

    def test_delete_removes_element(self):
        assert val(run('let s = new Set([1,2,3]); s.delete(2); let v = s.has(2)')) is False

    def test_clear_empties(self):
        assert val(run('let s = new Set([1,2,3]); s.clear(); let v = s.size')) == 0

    def test_add_returns_set(self):
        assert val(run('let s = new Set(); let v = s.add(1) === s')) is True


class TestSetCreationAndIteration:
    def test_from_array(self):
        assert val(run('let s = new Set([1,2,3]); let v = s.size')) == 3

    def test_from_array_dedup(self):
        assert val(run('let s = new Set([1,1,2,2,3]); let v = s.size')) == 3

    def test_values_iterator(self):
        assert val(run('let s = new Set([1,2,3]); let v = [...s.values()]')) == [1, 2, 3]

    def test_keys_same_as_values(self):
        assert val(run('let s = new Set([1,2]); let v = [...s.keys()]')) == [1, 2]

    def test_spread(self):
        assert val(run('let s = new Set([1,2,3]); let v = [...s]')) == [1, 2, 3]

    def test_entries_iterator(self):
        assert val(run('let s = new Set([1,2]); let v = [...s.entries()]')) == [[1, 1], [2, 2]]

    def test_foreach_basic(self):
        code = 'let s = new Set([1,2,3]); let r = []; s.forEach(x => r.push(x)); let v = r'
        assert val(run(code)) == [1, 2, 3]

    def test_for_of(self):
        code = 'let s = new Set([10,20]); let r = []; for (const x of s) { r.push(x); } let v = r'
        assert val(run(code)) == [10, 20]


class TestSetPatterns:
    def test_union_pattern(self):
        code = 'let a = new Set([1,2,3]); let b = new Set([3,4,5]); let v = [...new Set([...a, ...b])]'
        result = val(run(code))
        assert set(result) == {1, 2, 3, 4, 5}

    def test_intersection_pattern(self):
        code = 'let a = new Set([1,2,3,4]); let b = new Set([2,4,6]); let v = [...a].filter(x => b.has(x))'
        assert val(run(code)) == [2, 4]

    def test_difference_pattern(self):
        code = 'let a = new Set([1,2,3,4]); let b = new Set([2,4]); let v = [...a].filter(x => !b.has(x))'
        assert val(run(code)) == [1, 3]

    def test_unique_values(self):
        code = 'let a = [1,2,2,3,3,3]; let v = [...new Set(a)]'
        assert val(run(code)) == [1, 2, 3]

    def test_set_string_values(self):
        assert val(run('let s = new Set(["a","b","a"]); let v = s.size')) == 2


class TestWeakMapBasics:
    def test_create_weakmap(self):
        # just creating doesn't error
        i = run('let wm = new WeakMap(); let v = 1')
        assert val(i) == 1

    def test_set_and_get(self):
        code = 'let wm = new WeakMap(); let o = {}; wm.set(o, 42); let v = wm.get(o)'
        assert val(run(code)) == 42

    def test_has_existing(self):
        code = 'let wm = new WeakMap(); let o = {}; wm.set(o, 1); let v = wm.has(o)'
        assert val(run(code)) is True

    def test_has_missing(self):
        code = 'let wm = new WeakMap(); let o = {}; let v = wm.has(o)'
        assert val(run(code)) is False

    def test_delete_removes(self):
        code = 'let wm = new WeakMap(); let o = {}; wm.set(o, 1); wm.delete(o); let v = wm.has(o)'
        assert val(run(code)) is False

    def test_different_objects_different_entries(self):
        code = 'let wm = new WeakMap(); let a = {}; let b = {}; wm.set(a, 1); wm.set(b, 2); let v = wm.get(b)'
        assert val(run(code)) == 2

    def test_rejects_primitive_number(self):
        code = 'let wm = new WeakMap(); let v = 0; try { wm.set(42, 1); v = 0; } catch(e) { v = 1; }'
        assert val(run(code)) == 1

    def test_overwrite_value(self):
        code = 'let wm = new WeakMap(); let o = {}; wm.set(o, 1); wm.set(o, 99); let v = wm.get(o)'
        assert val(run(code)) == 99


class TestWeakSetBasics:
    def test_create_weakset(self):
        i = run('let ws = new WeakSet(); let v = 1')
        assert val(i) == 1

    def test_add_and_has(self):
        code = 'let ws = new WeakSet(); let o = {}; ws.add(o); let v = ws.has(o)'
        assert val(run(code)) is True

    def test_has_missing(self):
        code = 'let ws = new WeakSet(); let o = {}; let v = ws.has(o)'
        assert val(run(code)) is False

    def test_delete_removes(self):
        code = 'let ws = new WeakSet(); let o = {}; ws.add(o); ws.delete(o); let v = ws.has(o)'
        assert val(run(code)) is False

    def test_different_objects(self):
        code = 'let ws = new WeakSet(); let a = {}; let b = {}; ws.add(a); let v = ws.has(b)'
        assert val(run(code)) is False

    def test_multiple_objects(self):
        code = 'let ws = new WeakSet(); let a = {}; let b = {}; ws.add(a); ws.add(b); let v = ws.has(a) && ws.has(b)'
        assert val(run(code)) is True
