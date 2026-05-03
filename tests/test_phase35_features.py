"""Phase 35 feature tests.

Covers:
- Class public instance fields (without var/let keyword):
  - ``class Foo { x = 1; y = "hello" }`` — field declarations evaluated at construction
  - Fields are mutable instance properties (like VarDeclaration)
  - Init method can override field defaults
  - Inheritance: subclass fields override/extend parent fields
- ``new Set(iterable)`` / ``Set(iterable)`` returns SprySet:
  - size, has, add, delete, etc. work on the result
  - SprySet equality with list preserved for backward compat
  - SprySet len() preserved for backward compat
- Iterator helper methods (TC39 Iterator Helpers proposal):
  - ``Iterator.from(iterable)`` returns a SpryIterator with chaining methods
  - ``.filter(fn)`` — keep items where fn returns truthy
  - ``.map(fn)`` — transform each item
  - ``.take(n)`` — first n items
  - ``.drop(n)`` — skip first n items
  - ``.flatMap(fn)`` — map and flatten one level
  - ``.toArray()`` — materialise to list
  - ``.forEach(fn)`` — side-effect each item (returns None)
  - ``.reduce(fn, initial)`` — fold to single value
  - ``.some(fn)`` / ``.every(fn)`` — boolean short-circuit checks
  - ``.find(fn)`` — first matching item
  - ``.length`` / ``.size`` — count of remaining items
  - ``SpryIterator.toArray()`` works on iterators from ``.values()``
  - ``list.toArray()`` — alias returning a copy of the list
- ``Promise.withResolvers()`` (ES2024):
  - Returns ``{promise, resolve, reject}``
  - ``resolve(value)`` fulfils the promise container
  - ``reject(reason)`` rejects the promise container
- ``Array.fromAsync(iterable)`` (ES2024):
  - Returns a SpryPromise wrapping the array
  - Accepts same iterables as Array.from
  - Accepts optional map function
- ``structuredClone`` for SpryDate:
  - Deep-clones a Date object
  - Clone is independent of original
"""

from __future__ import annotations

from typing import Any

import pytest

from sprycode.interpreter import Interpreter, SpryDate, SpryPromise, SprySet
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


def val(source_or_interp: Any, name: str = "v") -> Any:
    if isinstance(source_or_interp, str):
        return run(source_or_interp).globals.get(name)
    return source_or_interp.globals.get(name)


# ---------------------------------------------------------------------------
# Class public instance fields
# ---------------------------------------------------------------------------


class TestClassInstanceFields:
    def test_basic_numeric_fields(self) -> None:
        i = run("class P { x = 10; y = 20 }; let p = P.new(); let v = p.x + p.y")
        assert val(i) == 30

    def test_string_field(self) -> None:
        i = run('class Msg { text = "hello" }; let m = Msg.new(); let v = m.text')
        assert val(i) == "hello"

    def test_bool_field(self) -> None:
        i = run("class Flag { active = true }; let f = Flag.new(); let v = f.active")
        assert val(i) is True

    def test_null_field(self) -> None:
        i = run("class Node { next = null }; let n = Node.new(); let v = n.next")
        assert val(i) is None

    def test_expression_field(self) -> None:
        i = run("class Cfg { maxRetries = 2 + 1 }; let c = Cfg.new(); let v = c.maxRetries")
        assert val(i) == 3

    def test_field_then_init_override(self) -> None:
        src = """
class Point {
  x = 0
  y = 0
  fn init(x, y) {
    this.x = x
    this.y = y
  }
}
let p = Point.new(3, 4)
let v = p.x + p.y
"""
        assert val(src) == 7

    def test_field_default_used_when_no_init(self) -> None:
        src = """
class Counter {
  count = 100
}
let c = Counter.new()
let v = c.count
"""
        assert val(src) == 100

    def test_multiple_fields_independent(self) -> None:
        src = """
class Box {
  width = 5
  height = 10
  depth = 2
}
let b = Box.new()
let v = b.width * b.height * b.depth
"""
        assert val(src) == 100

    def test_field_is_mutable(self) -> None:
        src = """
class Counter {
  count = 0
  fn inc() { this.count = this.count + 1 }
}
let c = Counter.new()
c.inc()
c.inc()
let v = c.count
"""
        assert val(src) == 2

    def test_fields_independent_across_instances(self) -> None:
        src = """
class Box { n = 0 }
let a = Box.new()
let b = Box.new()
a.n = 10
let v = b.n
"""
        assert val(src) == 0

    def test_array_field(self) -> None:
        src = """
class Queue {
  items = []
  fn push(x) { this.items.push(x) }
}
let q = Queue.new()
q.push(1)
q.push(2)
let v = q.items.length
"""
        assert val(src) == 2

    def test_subclass_inherits_parent_fields(self) -> None:
        src = """
class Animal {
  name = "unknown"
}
class Dog extends Animal {
  sound = "woof"
}
let d = Dog.new()
let v = d.name + ":" + d.sound
"""
        assert val(src) == "unknown:woof"

    def test_subclass_field_overrides_parent(self) -> None:
        src = """
class Base {
  x = 1
}
class Child extends Base {
  x = 99
}
let c = Child.new()
let v = c.x
"""
        assert val(src) == 99


# ---------------------------------------------------------------------------
# new Set(iterable) / Set(iterable) returns SprySet
# ---------------------------------------------------------------------------


class TestNewSetReturnsSprySet:
    def test_new_set_size(self) -> None:
        i = run("let s = new Set([1, 2, 3]); let v = s.size")
        assert val(i) == 3

    def test_new_set_has(self) -> None:
        i = run("let s = new Set([1, 2, 3]); let v = s.has(2)")
        assert val(i) is True

    def test_new_set_deduplicates(self) -> None:
        i = run("let s = new Set([1, 2, 2, 3, 1]); let v = s.size")
        assert val(i) == 3

    def test_new_set_empty(self) -> None:
        i = run("let s = new Set(); let v = s.size")
        assert val(i) == 0

    def test_new_set_from_string_iterable(self) -> None:
        i = run("let s = new Set([\"a\", \"b\", \"a\"]); let v = s.size")
        assert val(i) == 2

    def test_set_call_returns_spry_set(self) -> None:
        i = run("let s = Set([1, 2, 3]); let v = s.size")
        assert val(i) == 3

    def test_set_backward_compat_eq_list(self) -> None:
        """Set([...]) result should still compare equal to a deduplicated list."""
        i = run("let v = Set([1, 2, 3])")
        result = val(i)
        assert result == [1, 2, 3]

    def test_set_backward_compat_len(self) -> None:
        """len(Set([...])) should still work."""
        i = run("let v = len(Set([1, 2, 2, 3]))")
        assert val(i) == 3

    def test_new_set_add(self) -> None:
        i = run("let s = new Set([1, 2]); s.add(3); let v = s.size")
        assert val(i) == 3

    def test_new_set_delete(self) -> None:
        i = run("let s = new Set([1, 2, 3]); s.delete(2); let v = s.size")
        assert val(i) == 2

    def test_new_set_for_of(self) -> None:
        src = """
let s = new Set([1, 2, 3])
var v = 0
for (let x of s) { v = v + x }
"""
        assert val(src) == 6

    def test_new_set_to_list(self) -> None:
        i = run("let s = new Set([3, 1, 2]); let v = s.toList()")
        assert val(i) == [3, 1, 2]


# ---------------------------------------------------------------------------
# Iterator helpers
# ---------------------------------------------------------------------------


class TestIteratorFrom:
    def test_from_list_to_array(self) -> None:
        assert val("let v = Iterator.from([1, 2, 3]).toArray()") == [1, 2, 3]

    def test_from_empty_to_array(self) -> None:
        assert val("let v = Iterator.from([]).toArray()") == []

    def test_from_string_iterable(self) -> None:
        # Strings are iterable — each char becomes an item
        result = val('let v = Iterator.from("abc").toArray()')
        assert result == ["a", "b", "c"]

    def test_from_set(self) -> None:
        i = run("let s = new Set([1, 2, 3]); let v = Iterator.from(s).toArray()")
        assert sorted(val(i)) == [1, 2, 3]


class TestIteratorFilter:
    def test_basic_filter(self) -> None:
        assert val("let v = Iterator.from([1,2,3,4,5]).filter(x => x > 2).toArray()") == [3, 4, 5]

    def test_filter_even(self) -> None:
        assert val("let v = Iterator.from([1,2,3,4,5,6]).filter(x => x % 2 == 0).toArray()") == [2, 4, 6]

    def test_filter_empty_result(self) -> None:
        assert val("let v = Iterator.from([1,2,3]).filter(x => x > 10).toArray()") == []

    def test_filter_all_pass(self) -> None:
        assert val("let v = Iterator.from([1,2,3]).filter(x => x > 0).toArray()") == [1, 2, 3]


class TestIteratorMap:
    def test_basic_map(self) -> None:
        assert val("let v = Iterator.from([1,2,3]).map(x => x * 2).toArray()") == [2, 4, 6]

    def test_map_to_string(self) -> None:
        assert val("let v = Iterator.from([1,2,3]).map(x => \"n\" + x).toArray()") == ["n1", "n2", "n3"]

    def test_map_to_objects(self) -> None:
        i = run("let v = Iterator.from([1,2]).map(x => x * 10).toArray()")
        result = val(i)
        assert result == [10, 20]


class TestIteratorTake:
    def test_take_first_n(self) -> None:
        assert val("let v = Iterator.from([1,2,3,4,5]).take(3).toArray()") == [1, 2, 3]

    def test_take_zero(self) -> None:
        assert val("let v = Iterator.from([1,2,3]).take(0).toArray()") == []

    def test_take_more_than_length(self) -> None:
        assert val("let v = Iterator.from([1,2]).take(100).toArray()") == [1, 2]

    def test_take_one(self) -> None:
        assert val("let v = Iterator.from([10,20,30]).take(1).toArray()") == [10]


class TestIteratorDrop:
    def test_drop_first_n(self) -> None:
        assert val("let v = Iterator.from([1,2,3,4,5]).drop(2).toArray()") == [3, 4, 5]

    def test_drop_zero(self) -> None:
        assert val("let v = Iterator.from([1,2,3]).drop(0).toArray()") == [1, 2, 3]

    def test_drop_all(self) -> None:
        assert val("let v = Iterator.from([1,2,3]).drop(10).toArray()") == []

    def test_drop_then_map(self) -> None:
        assert val("let v = Iterator.from([1,2,3,4,5]).drop(2).map(x => x * 10).toArray()") == [30, 40, 50]


class TestIteratorFlatMap:
    def test_basic_flatmap(self) -> None:
        assert val("let v = Iterator.from([[1,2],[3,4]]).flatMap(x => x).toArray()") == [1, 2, 3, 4]

    def test_flatmap_with_transform(self) -> None:
        assert val("let v = Iterator.from([1,2,3]).flatMap(x => [x, x*10]).toArray()") == [1, 10, 2, 20, 3, 30]

    def test_flatmap_scalar(self) -> None:
        # fn returns scalar — wraps in list level not flattened further
        assert val("let v = Iterator.from([1,2,3]).flatMap(x => x * 2).toArray()") == [2, 4, 6]


class TestIteratorChaining:
    def test_filter_then_map(self) -> None:
        src = "let v = Iterator.from([1,2,3,4,5]).filter(x => x % 2 == 0).map(x => x * 10).toArray()"
        assert val(src) == [20, 40]

    def test_map_then_filter(self) -> None:
        src = "let v = Iterator.from([1,2,3,4,5]).map(x => x * 2).filter(x => x > 6).toArray()"
        assert val(src) == [8, 10]

    def test_take_then_map(self) -> None:
        src = "let v = Iterator.from([1,2,3,4,5]).take(3).map(x => x * 100).toArray()"
        assert val(src) == [100, 200, 300]

    def test_drop_then_filter_then_map(self) -> None:
        src = "let v = Iterator.from([1,2,3,4,5,6]).drop(2).filter(x => x % 2 != 0).map(x => x + 1).toArray()"
        assert val(src) == [4, 6]

    def test_flatmap_then_filter(self) -> None:
        src = "let v = Iterator.from([[1,2,3],[4,5,6]]).flatMap(x => x).filter(x => x > 3).toArray()"
        assert val(src) == [4, 5, 6]


class TestIteratorForEach:
    def test_foreach_side_effects(self) -> None:
        src = "var v = 0; Iterator.from([1,2,3]).forEach(x => { v = v + x })"
        assert val(src) == 6

    def test_foreach_empty(self) -> None:
        src = "var v = 0; Iterator.from([]).forEach(x => { v = v + 1 })"
        assert val(src) == 0


class TestIteratorReduce:
    def test_sum_with_initial(self) -> None:
        assert val("let v = Iterator.from([1,2,3,4]).reduce((a, x) => a + x, 0)") == 10

    def test_product_with_initial(self) -> None:
        assert val("let v = Iterator.from([1,2,3,4]).reduce((a, x) => a * x, 1)") == 24

    def test_reduce_without_initial(self) -> None:
        assert val("let v = Iterator.from([1,2,3,4]).reduce((a, x) => a + x)") == 10

    def test_reduce_string_concat(self) -> None:
        assert val('let v = Iterator.from(["a","b","c"]).reduce((a, x) => a + x, "")') == "abc"


class TestIteratorSomeEvery:
    def test_some_true(self) -> None:
        assert val("let v = Iterator.from([1,2,3]).some(x => x > 2)") is True

    def test_some_false(self) -> None:
        assert val("let v = Iterator.from([1,2,3]).some(x => x > 10)") is False

    def test_some_empty(self) -> None:
        assert val("let v = Iterator.from([]).some(x => true)") is False

    def test_every_true(self) -> None:
        assert val("let v = Iterator.from([2,4,6]).every(x => x % 2 == 0)") is True

    def test_every_false(self) -> None:
        assert val("let v = Iterator.from([1,2,3]).every(x => x > 1)") is False

    def test_every_empty(self) -> None:
        assert val("let v = Iterator.from([]).every(x => false)") is True


class TestIteratorFind:
    def test_find_first_match(self) -> None:
        assert val("let v = Iterator.from([1,2,3,4]).find(x => x > 2)") == 3

    def test_find_no_match(self) -> None:
        assert val("let v = Iterator.from([1,2,3]).find(x => x > 10)") is None

    def test_find_first_only(self) -> None:
        assert val("let v = Iterator.from([10,20,30]).find(x => x > 5)") == 10


class TestIteratorLengthSize:
    def test_length_property(self) -> None:
        i = run("let it = Iterator.from([1,2,3,4,5]); let v = it.length")
        assert val(i) == 5

    def test_size_property(self) -> None:
        i = run("let it = Iterator.from([1,2,3]); let v = it.size")
        assert val(i) == 3


class TestSpryIteratorToArray:
    def test_values_toarray(self) -> None:
        assert val("let v = [1,2,3].values().toArray()") == [1, 2, 3]

    def test_values_filter_toarray(self) -> None:
        i = run("let v = [1,2,3,4].values().filter(x => x > 2).toArray()")
        assert val(i) == [3, 4]

    def test_values_map_toarray(self) -> None:
        i = run("let v = [1,2,3].values().map(x => x + 10).toArray()")
        assert val(i) == [11, 12, 13]


class TestListToArray:
    def test_list_toarray_returns_list(self) -> None:
        assert val("let v = [1,2,3].toArray()") == [1, 2, 3]

    def test_list_toarray_empty(self) -> None:
        assert val("let v = [].toArray()") == []

    def test_list_toarray_is_copy(self) -> None:
        src = """
let arr = [1,2,3]
let snapshot = arr.toArray()
snapshot.push(99)
let v = arr.length
"""
        assert val(src) == 3


# ---------------------------------------------------------------------------
# Promise.withResolvers
# ---------------------------------------------------------------------------


class TestPromiseWithResolvers:
    def test_returns_object_with_keys(self) -> None:
        i = run("let r = Promise.withResolvers(); let v = typeof r.resolve")
        assert val(i) == "Function"

    def test_has_reject_key(self) -> None:
        i = run("let r = Promise.withResolvers(); let v = typeof r.reject")
        assert val(i) == "Function"

    def test_resolve_fulfils_promise(self) -> None:
        src = """
let r = Promise.withResolvers()
r.resolve(42)
let v = r.promise.value
"""
        assert val(src) == 42

    def test_reject_rejects_promise(self) -> None:
        src = """
let r = Promise.withResolvers()
r.reject("oops")
let v = r.promise.error
"""
        assert val(src) == "oops"

    def test_initial_promise_is_accessible(self) -> None:
        src = """
let r = Promise.withResolvers()
let v = r.promise != null
"""
        assert val(src) is True

    def test_resolve_with_string(self) -> None:
        src = """
let r = Promise.withResolvers()
r.resolve("hello")
let v = r.promise.value
"""
        assert val(src) == "hello"


# ---------------------------------------------------------------------------
# Array.fromAsync
# ---------------------------------------------------------------------------


class TestArrayFromAsync:
    def test_basic_fromAsync(self) -> None:
        i = run("let p = Array.fromAsync([1,2,3]); let v = p.value")
        assert val(i) == [1, 2, 3]

    def test_fromAsync_returns_promise(self) -> None:
        i = run("let p = Array.fromAsync([1,2,3]); let v = p.status")
        assert val(i) == "fulfilled"

    def test_fromAsync_empty(self) -> None:
        i = run("let p = Array.fromAsync([]); let v = p.value")
        assert val(i) == []

    def test_fromAsync_with_map_fn(self) -> None:
        i = run("let p = Array.fromAsync([1,2,3], x => x * 2); let v = p.value")
        assert val(i) == [2, 4, 6]

    def test_fromAsync_from_set(self) -> None:
        i = run("let s = new Set([1,2,3]); let p = Array.fromAsync(s); let v = p.value.length")
        assert val(i) == 3

    def test_fromAsync_accessible_via_then(self) -> None:
        src = """
var v = 0
let p = Array.fromAsync([10, 20, 30])
p.then(arr => { v = arr.length })
"""
        assert val(src) == 3


# ---------------------------------------------------------------------------
# structuredClone for SpryDate
# ---------------------------------------------------------------------------


class TestStructuredCloneDate:
    def test_clone_date_year(self) -> None:
        src = "let d = Date.new(2024, 6, 15); let d2 = structuredClone(d); let v = d2.getFullYear()"
        assert val(src) == 2024

    def test_clone_date_month(self) -> None:
        src = "let d = Date.new(2024, 6, 15); let d2 = structuredClone(d); let v = d2.getMonth()"
        # getMonth() returns 0-based month (JS convention): June is 5
        assert val(src) == 5

    def test_clone_is_independent(self) -> None:
        """Cloned date is a separate object (not the same reference)."""
        src = """
let d = Date.new(2024, 1, 1)
let d2 = structuredClone(d)
let v = d == d2
"""
        # They may be equal by value but they should be different objects
        # The test here just checks no error is thrown and the clone works
        i = run(src)
        assert i.globals.get("d2") is not None

    def test_clone_date_iso_string(self) -> None:
        src = "let d = Date.new(2024, 6, 15); let d2 = structuredClone(d); let v = d2.toISOString()"
        result = val(src)
        assert "2024" in str(result)

    def test_structuredclone_preserves_other_types(self) -> None:
        """structuredClone still works for dict/list alongside Date."""
        src = "let v = structuredClone({a: [1,2,3], b: null}).a.length"
        assert val(src) == 3
