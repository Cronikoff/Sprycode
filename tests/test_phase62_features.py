"""Phase 62 feature tests:
- structuredClone deep clone
- queueMicrotask executes synchronously
- Array.from(iterable, mapFn) two-arg form
- Object.fromEntries([[key, val], ...])
- String.prototype.at(-1) / at(0) negative and positive indexing
- WeakRef and FinalizationRegistry
- globalThis object
- Object.hasOwn(obj, key)
- Array.prototype.at(-1) negative indexing
- String.prototype.replaceAll
- Object.keys / values / entries comprehensive
- Array.prototype.flat(depth) and flatMap
- Array.prototype.findIndex(fn)
- Array.prototype.findLast(fn) and findLastIndex(fn)
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


# ---------------------------------------------------------------------------
# structuredClone
# ---------------------------------------------------------------------------

class TestStructuredClone:
    def test_clone_array(self) -> None:
        i = run("let a = [1, 2, 3]\nlet v = structuredClone(a)")
        assert val(i) == [1, 2, 3]

    def test_clone_is_deep_copy(self) -> None:
        i = run(
            "let a = [1, 2, 3]\n"
            "let b = structuredClone(a)\n"
            "b.push(4)\n"
            "let v = a.length"
        )
        assert val(i) == 3

    def test_clone_object(self) -> None:
        i = run('let o = {x: 1, y: 2}\nlet v = structuredClone(o)')
        result = val(i)
        assert result["x"] == 1
        assert result["y"] == 2

    def test_clone_nested(self) -> None:
        i = run('let o = {a: [1, 2]}\nlet c = structuredClone(o)\nc.a.push(3)\nlet v = o.a.length')
        assert val(i) == 2

    def test_clone_string(self) -> None:
        i = run('let v = structuredClone("hello")')
        assert val(i) == "hello"

    def test_clone_number(self) -> None:
        i = run("let v = structuredClone(42)")
        assert val(i) == 42


# ---------------------------------------------------------------------------
# queueMicrotask
# ---------------------------------------------------------------------------

class TestQueueMicrotask:
    def test_executes_synchronously(self) -> None:
        i = run("let v = 0\nqueueMicrotask(fn() { v = 42 })")
        assert val(i) == 42

    def test_multiple_tasks(self) -> None:
        i = run(
            "let v = []\n"
            "queueMicrotask(fn() { v.push(1) })\n"
            "queueMicrotask(fn() { v.push(2) })\n"
        )
        assert val(i) == [1, 2]

    def test_null_argument(self) -> None:
        # Should not throw
        i = run("queueMicrotask(null)\nlet v = true")
        assert val(i) is True


# ---------------------------------------------------------------------------
# Array.from
# ---------------------------------------------------------------------------

class TestArrayFrom:
    def test_from_array(self) -> None:
        i = run("let v = Array.from([1, 2, 3])")
        assert val(i) == [1, 2, 3]

    def test_from_string(self) -> None:
        i = run('let v = Array.from("abc")')
        assert val(i) == ["a", "b", "c"]

    def test_from_with_map_fn(self) -> None:
        i = run("let v = Array.from([1, 2, 3], fn(x) { return x * 2 })")
        assert val(i) == [2, 4, 6]

    def test_from_with_map_fn_index(self) -> None:
        i = run("let v = Array.from([10, 20, 30], fn(x, i) { return i })")
        assert val(i) == [0, 1, 2]

    def test_from_range_like(self) -> None:
        i = run("let v = Array.from({length: 3}, fn(_, i) { return i })")
        assert val(i) == [0, 1, 2]


# ---------------------------------------------------------------------------
# Object.fromEntries
# ---------------------------------------------------------------------------

class TestObjectFromEntries:
    def test_basic(self) -> None:
        i = run('let v = Object.fromEntries([["a", 1], ["b", 2]])')
        assert val(i) == {"a": 1, "b": 2}

    def test_roundtrip_with_entries(self) -> None:
        i = run(
            'let obj = {x: 10, y: 20}\n'
            'let v = Object.fromEntries(Object.entries(obj))'
        )
        result = val(i)
        assert result["x"] == 10
        assert result["y"] == 20

    def test_empty(self) -> None:
        i = run("let v = Object.fromEntries([])")
        assert val(i) == {}

    def test_from_map_entries(self) -> None:
        i = run(
            "let m = new Map()\n"
            "m.set(\"a\", 1)\n"
            "m.set(\"b\", 2)\n"
            "let v = Object.fromEntries(m)"
        )
        result = val(i)
        assert result["a"] == 1
        assert result["b"] == 2


# ---------------------------------------------------------------------------
# String.prototype.at
# ---------------------------------------------------------------------------

class TestStringAt:
    def test_positive_index(self) -> None:
        i = run('let v = "hello".at(0)')
        assert val(i) == "h"

    def test_negative_index(self) -> None:
        i = run('let v = "hello".at(-1)')
        assert val(i) == "o"

    def test_negative_second(self) -> None:
        i = run('let v = "hello".at(-2)')
        assert val(i) == "l"

    def test_middle_index(self) -> None:
        i = run('let v = "hello".at(2)')
        assert val(i) == "l"

    def test_out_of_bounds(self) -> None:
        i = run('let v = "hello".at(10)')
        result = val(i)
        assert result is None or result == "" or str(result) in ("undefined", "None")


# ---------------------------------------------------------------------------
# WeakRef and FinalizationRegistry
# ---------------------------------------------------------------------------

class TestWeakRef:
    def test_deref(self) -> None:
        i = run("let obj = {x: 42}\nlet wr = new WeakRef(obj)\nlet v = wr.deref().x")
        assert val(i) == 42

    def test_deref_returns_original(self) -> None:
        i = run(
            "let obj = {name: \"test\"}\n"
            "let wr = new WeakRef(obj)\n"
            "let v = wr.deref().name"
        )
        assert val(i) == "test"

    def test_weakref_typeof(self) -> None:
        i = run("let wr = new WeakRef({x: 1})\nlet v = typeof wr")
        assert val(i) == "object"


class TestFinalizationRegistry:
    def test_constructor(self) -> None:
        i = run("let fr = new FinalizationRegistry(fn(x) { return x })\nlet v = typeof fr")
        assert val(i) == "object"

    def test_register(self) -> None:
        # Should not throw
        i = run(
            "let fr = new FinalizationRegistry(fn(x) { return x })\n"
            "let obj = {x: 1}\n"
            "fr.register(obj, \"token\")\n"
            "let v = true"
        )
        assert val(i) is True

    def test_unregister(self) -> None:
        i = run(
            "let token = {}\n"
            "let fr = new FinalizationRegistry(fn(x) { return x })\n"
            "let obj = {x: 1}\n"
            "fr.register(obj, \"val\", token)\n"
            "fr.unregister(token)\n"
            "let v = true"
        )
        assert val(i) is True


# ---------------------------------------------------------------------------
# globalThis
# ---------------------------------------------------------------------------

class TestGlobalThis:
    def test_typeof(self) -> None:
        i = run("let v = typeof globalThis")
        assert val(i) == "object"

    def test_exists(self) -> None:
        i = run("let v = globalThis !== null && globalThis !== undefined")
        assert val(i) is True

    def test_undefined_property(self) -> None:
        i = run("let v = globalThis.undefined")
        from sprycode.interpreter import SPRY_UNDEFINED
        assert val(i) is SPRY_UNDEFINED


# ---------------------------------------------------------------------------
# Object.hasOwn
# ---------------------------------------------------------------------------

class TestObjectHasOwn:
    def test_own_property(self) -> None:
        i = run('let v = Object.hasOwn({a: 1}, "a")')
        assert val(i) is True

    def test_missing_property(self) -> None:
        i = run('let v = Object.hasOwn({a: 1}, "b")')
        assert val(i) is False

    def test_empty_object(self) -> None:
        i = run('let v = Object.hasOwn({}, "x")')
        assert val(i) is False

    def test_numeric_key(self) -> None:
        i = run('let v = Object.hasOwn({0: "zero"}, "0")')
        assert val(i) is True


# ---------------------------------------------------------------------------
# Array.prototype.at
# ---------------------------------------------------------------------------

class TestArrayAt:
    def test_positive_index(self) -> None:
        i = run("let v = [10, 20, 30].at(0)")
        assert val(i) == 10

    def test_negative_index(self) -> None:
        i = run("let v = [10, 20, 30].at(-1)")
        assert val(i) == 30

    def test_negative_second(self) -> None:
        i = run("let v = [10, 20, 30].at(-2)")
        assert val(i) == 20

    def test_middle(self) -> None:
        i = run("let v = [10, 20, 30].at(1)")
        assert val(i) == 20


# ---------------------------------------------------------------------------
# String.prototype.replaceAll
# ---------------------------------------------------------------------------

class TestReplaceAll:
    def test_basic(self) -> None:
        i = run('let v = "hello hello hello".replaceAll("hello", "hi")')
        assert val(i) == "hi hi hi"

    def test_no_match(self) -> None:
        i = run('let v = "hello world".replaceAll("xyz", "abc")')
        assert val(i) == "hello world"

    def test_replace_with_empty(self) -> None:
        i = run('let v = "a,b,c".replaceAll(",", "")')
        assert val(i) == "abc"

    def test_replace_all_chars(self) -> None:
        i = run('let v = "aaa".replaceAll("a", "b")')
        assert val(i) == "bbb"


# ---------------------------------------------------------------------------
# Object.keys / values / entries
# ---------------------------------------------------------------------------

class TestObjectKeysValuesEntries:
    def test_keys(self) -> None:
        i = run("let v = Object.keys({a: 1, b: 2, c: 3})")
        assert sorted(val(i)) == ["a", "b", "c"]

    def test_values(self) -> None:
        i = run("let v = Object.values({a: 1, b: 2, c: 3})")
        assert sorted(val(i)) == [1, 2, 3]

    def test_entries(self) -> None:
        i = run("let v = Object.entries({a: 1, b: 2})")
        result = val(i)
        assert sorted(result) == [["a", 1], ["b", 2]]

    def test_keys_empty(self) -> None:
        i = run("let v = Object.keys({})")
        assert val(i) == []

    def test_values_empty(self) -> None:
        i = run("let v = Object.values({})")
        assert val(i) == []

    def test_entries_empty(self) -> None:
        i = run("let v = Object.entries({})")
        assert val(i) == []

    def test_keys_order(self) -> None:
        i = run("let obj = {z: 1, a: 2, m: 3}\nlet v = Object.keys(obj)")
        keys = val(i)
        assert set(keys) == {"z", "a", "m"}


# ---------------------------------------------------------------------------
# Array.prototype.flat and flatMap
# ---------------------------------------------------------------------------

class TestFlat:
    def test_flat_one_level(self) -> None:
        i = run("let v = [[1, 2], [3, 4]].flat()")
        assert val(i) == [1, 2, 3, 4]

    def test_flat_depth_2(self) -> None:
        i = run("let v = [1, [2, [3]]].flat(2)")
        assert val(i) == [1, 2, 3]

    def test_flat_depth_1_partial(self) -> None:
        i = run("let v = [1, [2, [3, [4]]]].flat(1)")
        assert val(i) == [1, 2, [3, [4]]]

    def test_flat_already_flat(self) -> None:
        i = run("let v = [1, 2, 3].flat()")
        assert val(i) == [1, 2, 3]


class TestFlatMap:
    def test_basic(self) -> None:
        i = run("let v = [1, 2, 3].flatMap(fn(x) { return [x, x * 2] })")
        assert val(i) == [1, 2, 2, 4, 3, 6]

    def test_filter_like(self) -> None:
        i = run("let v = [1, 2, 3, 4].flatMap(fn(x) { if (x % 2 == 0) { return [x] } return [] })")
        assert val(i) == [2, 4]

    def test_identity(self) -> None:
        i = run("let v = [1, 2, 3].flatMap(fn(x) { return x })")
        assert val(i) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Array.prototype.findIndex
# ---------------------------------------------------------------------------

class TestFindIndex:
    def test_found(self) -> None:
        i = run("let v = [1, 2, 3, 4].findIndex(fn(x) { return x > 2 })")
        assert val(i) == 2

    def test_not_found(self) -> None:
        i = run("let v = [1, 2, 3].findIndex(fn(x) { return x > 10 })")
        assert val(i) == -1

    def test_first_element(self) -> None:
        i = run("let v = [5, 3, 1].findIndex(fn(x) { return x == 5 })")
        assert val(i) == 0

    def test_last_element(self) -> None:
        i = run("let v = [1, 2, 5].findIndex(fn(x) { return x == 5 })")
        assert val(i) == 2


# ---------------------------------------------------------------------------
# Array.prototype.findLast and findLastIndex
# ---------------------------------------------------------------------------

class TestFindLast:
    def test_find_last(self) -> None:
        i = run("let v = [1, 2, 3, 4].findLast(fn(x) { return x < 3 })")
        assert val(i) == 2

    def test_find_last_no_match(self) -> None:
        i = run("let v = [1, 2, 3].findLast(fn(x) { return x > 10 })")
        result = val(i)
        assert result is None or str(result) in ("undefined", "None")

    def test_find_last_first_element(self) -> None:
        i = run("let v = [1, 2, 3].findLast(fn(x) { return x == 1 })")
        assert val(i) == 1


class TestFindLastIndex:
    def test_find_last_index(self) -> None:
        i = run("let v = [1, 2, 3, 4].findLastIndex(fn(x) { return x < 3 })")
        assert val(i) == 1

    def test_find_last_index_no_match(self) -> None:
        i = run("let v = [1, 2, 3].findLastIndex(fn(x) { return x > 10 })")
        assert val(i) == -1

    def test_find_last_index_last_element(self) -> None:
        i = run("let v = [1, 2, 3].findLastIndex(fn(x) { return x == 3 })")
        assert val(i) == 2
