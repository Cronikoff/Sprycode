"""Phase 13 feature tests — zero-arg lambdas, number.toString(radix), array.group,
generator iterator helpers, SprySet, Iterator.from, structuredClone, globalThis,
Promise, Date namespace, Reflect namespace, queueMicrotask."""

import pytest
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.interpreter import Interpreter


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str = "v"):
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# Zero-arg lambdas
# ---------------------------------------------------------------------------


class TestZeroArgLambda:
    def test_returns_literal(self):
        i = run("let f = () => 42\nlet v = f()")
        assert val(i) == 42

    def test_returns_expression(self):
        i = run("let x = 10\nlet f = () => x * 2\nlet v = f()")
        assert val(i) == 20

    def test_block_body(self):
        i = run("let f = () => { return 99 }\nlet v = f()")
        assert val(i) == 99

    def test_block_body_with_logic(self):
        i = run("var n = 0\nlet f = () => { n += 1\nreturn n }\nf()\nlet v = f()")
        assert val(i) == 2

    def test_passed_as_argument(self):
        i = run("fn call(f) { return f() }\nlet v = call(() => 77)")
        assert val(i) == 77

    def test_stored_in_variable(self):
        i = run("let greet = () => 'hello'\nlet v = greet()")
        assert val(i) == "hello"

    def test_queueMicrotask_uses_zero_arg(self):
        i = run("var v = 0\nqueueMicrotask(() => { v = 42 })")
        assert val(i) == 42

    def test_zero_arg_in_array(self):
        i = run("let fns = [() => 1, () => 2, () => 3]\nlet v = fns[1]()")
        assert val(i) == 2


# ---------------------------------------------------------------------------
# number.toString(radix)
# ---------------------------------------------------------------------------


class TestNumberToStringRadix:
    def test_hex_lowercase(self):
        i = run("let v = (255).toString(16)")
        assert val(i) == "ff"

    def test_hex_large(self):
        i = run("let v = (65535).toString(16)")
        assert val(i) == "ffff"

    def test_binary(self):
        i = run("let v = (10).toString(2)")
        assert val(i) == "1010"

    def test_octal(self):
        i = run("let v = (8).toString(8)")
        assert val(i) == "10"

    def test_decimal_default(self):
        i = run("let v = (42).toString()")
        assert val(i) == "42"

    def test_decimal_explicit(self):
        i = run("let v = (42).toString(10)")
        assert val(i) == "42"

    def test_zero(self):
        i = run("let v = (0).toString(16)")
        assert val(i) == "0"

    def test_variable(self):
        i = run("let n = 255\nlet v = n.toString(16)")
        assert val(i) == "ff"


# ---------------------------------------------------------------------------
# array.group
# ---------------------------------------------------------------------------


class TestArrayGroup:
    def test_group_by_parity(self):
        i = run("let v = [1,2,3,4].group(x => x % 2)")
        result = val(i)
        assert result[1] == [1, 3]
        assert result[0] == [2, 4]

    def test_group_by_string_length(self):
        i = run('let v = ["a", "bb", "c", "dd"].group(s => s.length)')
        result = val(i)
        assert result[2] == ["bb", "dd"]
        assert result[1] == ["a", "c"]

    def test_group_returns_dict(self):
        i = run("let v = [1, 2].group(x => x)")
        assert isinstance(val(i), dict)

    def test_group_single_item(self):
        i = run("let v = [42].group(x => x)")
        assert val(i) == {42: [42]}

    def test_group_empty(self):
        i = run("let v = [].group(x => x)")
        assert val(i) == {}

    def test_group_all_same_key(self):
        i = run("let v = [1,2,3].group(x => 'all')")
        assert val(i) == {"all": [1, 2, 3]}


# ---------------------------------------------------------------------------
# Generator iterator helpers
# ---------------------------------------------------------------------------


class TestGeneratorIteratorHelpers:
    def test_toArray(self):
        i = run("fn* g() { yield 1\nyield 2\nyield 3 }\nlet v = g().toArray()")
        assert val(i) == [1, 2, 3]

    def test_take(self):
        i = run("fn* g() { yield 1\nyield 2\nyield 3 }\nlet v = g().take(2)")
        assert val(i) == [1, 2]

    def test_take_more_than_available(self):
        i = run("fn* g() { yield 1\nyield 2 }\nlet v = g().take(10)")
        assert val(i) == [1, 2]

    def test_take_zero(self):
        i = run("fn* g() { yield 1\nyield 2 }\nlet v = g().take(0)")
        assert val(i) == []

    def test_drop(self):
        i = run("fn* g() { yield 1\nyield 2\nyield 3 }\nlet v = g().drop(1)")
        assert val(i) == [2, 3]

    def test_drop_all(self):
        i = run("fn* g() { yield 1\nyield 2 }\nlet v = g().drop(5)")
        assert val(i) == []

    def test_map(self):
        i = run("fn* g() { yield 1\nyield 2\nyield 3 }\nlet v = g().map(x => x * 2)")
        assert val(i) == [2, 4, 6]

    def test_filter(self):
        i = run("fn* g() { yield 1\nyield 2\nyield 3\nyield 4 }\nlet v = g().filter(x => x % 2 == 0)")
        assert val(i) == [2, 4]

    def test_reduce(self):
        i = run("fn* g() { yield 1\nyield 2\nyield 3 }\nlet v = g().reduce((acc, x) => acc + x, 0)")
        assert val(i) == 6

    def test_length(self):
        i = run("fn* g() { yield 1\nyield 2\nyield 3 }\nlet v = g().length")
        assert val(i) == 3

    def test_forEach(self):
        i = run("fn* g() { yield 1\nyield 2\nyield 3 }\nvar v = 0\ng().forEach(x => { v += x })")
        assert val(i) == 6


# ---------------------------------------------------------------------------
# SprySet
# ---------------------------------------------------------------------------


class TestSprySet:
    def test_new_deduplicates(self):
        i = run("let s = SprySet.new([1,2,3,2,1])\nlet v = s.size")
        assert val(i) == 3

    def test_has_true(self):
        i = run("let s = SprySet.new([1,2,3])\nlet v = s.has(2)")
        assert val(i) is True

    def test_has_false(self):
        i = run("let s = SprySet.new([1,2,3])\nlet v = s.has(99)")
        assert val(i) is False

    def test_add(self):
        i = run("let s = SprySet.new([1,2])\ns.add(3)\nlet v = s.size")
        assert val(i) == 3

    def test_add_duplicate_no_change(self):
        i = run("let s = SprySet.new([1,2])\ns.add(1)\nlet v = s.size")
        assert val(i) == 2

    def test_delete(self):
        i = run("let s = SprySet.new([1,2,3])\ns.delete(2)\nlet v = s.size")
        assert val(i) == 2

    def test_delete_nonexistent(self):
        i = run("let s = SprySet.new([1,2])\nlet v = s.delete(99)")
        assert val(i) is False

    def test_toList(self):
        i = run("let s = SprySet.new([3,1,2])\nlet v = s.toList()")
        assert sorted(val(i)) == [1, 2, 3]

    def test_union(self):
        i = run("let a = SprySet.new([1,2,3])\nlet b = SprySet.new([3,4,5])\nlet v = a.union(b).toList()")
        assert sorted(val(i)) == [1, 2, 3, 4, 5]

    def test_intersection(self):
        i = run("let a = SprySet.new([1,2,3])\nlet b = SprySet.new([2,3,4])\nlet v = a.intersection(b).toList()")
        assert sorted(val(i)) == [2, 3]

    def test_difference(self):
        i = run("let a = SprySet.new([1,2,3])\nlet b = SprySet.new([2,3,4])\nlet v = a.difference(b).toList()")
        assert val(i) == [1]

    def test_symmetric_difference(self):
        i = run("let a = SprySet.new([1,2,3])\nlet b = SprySet.new([3,4,5])\nlet v = a.symmetricDifference(b).toList()")
        assert sorted(val(i)) == [1, 2, 4, 5]

    def test_isSubsetOf(self):
        i = run("let a = SprySet.new([2,3])\nlet b = SprySet.new([1,2,3,4])\nlet v = a.isSubsetOf(b)")
        assert val(i) is True

    def test_isSubsetOf_false(self):
        i = run("let a = SprySet.new([1,2,5])\nlet b = SprySet.new([1,2,3])\nlet v = a.isSubsetOf(b)")
        assert val(i) is False

    def test_isSupersetOf(self):
        i = run("let a = SprySet.new([1,2,3,4])\nlet b = SprySet.new([2,3])\nlet v = a.isSupersetOf(b)")
        assert val(i) is True

    def test_isDisjointFrom(self):
        i = run("let a = SprySet.new([1,2])\nlet b = SprySet.new([3,4])\nlet v = a.isDisjointFrom(b)")
        assert val(i) is True

    def test_isDisjointFrom_false(self):
        i = run("let a = SprySet.new([1,2,3])\nlet b = SprySet.new([3,4,5])\nlet v = a.isDisjointFrom(b)")
        assert val(i) is False

    def test_empty_set(self):
        i = run("let s = SprySet.new([])\nlet v = s.size")
        assert val(i) == 0

    def test_clear(self):
        i = run("let s = SprySet.new([1,2,3])\ns.clear()\nlet v = s.size")
        assert val(i) == 0


# ---------------------------------------------------------------------------
# Iterator.from
# ---------------------------------------------------------------------------


class TestIteratorFrom:
    def test_from_list(self):
        i = run("let v = Iterator.from([1,2,3])")
        assert val(i) == [1, 2, 3]

    def test_from_string(self):
        i = run('let v = Iterator.from("abc")')
        assert val(i) == ["a", "b", "c"]

    def test_from_generator(self):
        i = run("fn* g() { yield 10\nyield 20 }\nlet v = Iterator.from(g())")
        assert val(i) == [10, 20]

    def test_from_spryset(self):
        i = run("let s = SprySet.new([1,2,3])\nlet v = Iterator.from(s)")
        assert sorted(val(i)) == [1, 2, 3]


# ---------------------------------------------------------------------------
# structuredClone
# ---------------------------------------------------------------------------


class TestStructuredClone:
    def test_clones_object(self):
        i = run("var obj = {a: 1}\nvar c = structuredClone(obj)\nc.a = 99\nlet v = obj.a")
        assert val(i) == 1

    def test_clones_nested(self):
        i = run("var obj = {a: {b: 1}}\nvar c = structuredClone(obj)\nc.a.b = 99\nlet v = obj.a.b")
        assert val(i) == 1

    def test_clones_list(self):
        i = run("var lst = [1, 2, 3]\nvar c = structuredClone(lst)\nc[0] = 99\nlet v = lst[0]")
        assert val(i) == 1

    def test_clone_primitive(self):
        i = run("let v = structuredClone(42)")
        assert val(i) == 42

    def test_clone_string(self):
        i = run('let v = structuredClone("hello")')
        assert val(i) == "hello"


# ---------------------------------------------------------------------------
# globalThis
# ---------------------------------------------------------------------------


class TestGlobalThis:
    def test_is_not_null(self):
        i = run("let v = globalThis != null")
        assert val(i) is True

    def test_is_defined(self):
        i = run("let v = typeof globalThis")
        assert val(i) == "Object"


# ---------------------------------------------------------------------------
# Promise
# ---------------------------------------------------------------------------


class TestPromise:
    def test_resolve_value(self):
        i = run("let v = Promise.resolve(42).value")
        assert val(i) == 42

    def test_resolve_status(self):
        i = run("let v = Promise.resolve(1).status")
        assert val(i) == "fulfilled"

    def test_reject_status(self):
        i = run('let v = Promise.reject("err").status')
        assert val(i) == "rejected"

    def test_reject_error(self):
        i = run('let v = Promise.reject("bad").error')
        assert val(i) == "bad"

    def test_all_values(self):
        i = run("let v = Promise.all([Promise.resolve(1), Promise.resolve(2)]).value")
        assert val(i) == [1, 2]

    def test_all_rejects_on_first_failure(self):
        i = run('let p = Promise.all([Promise.resolve(1), Promise.reject("e")])\nlet v = p.status')
        assert val(i) == "rejected"

    def test_allSettled_fulfilled(self):
        i = run("let r = Promise.allSettled([Promise.resolve(1)]).value\nlet v = r[0].status")
        assert val(i) == "fulfilled"

    def test_allSettled_rejected(self):
        i = run('let r = Promise.allSettled([Promise.reject("e")]).value\nlet v = r[0].status')
        assert val(i) == "rejected"

    def test_race_returns_first(self):
        i = run("let v = Promise.race([Promise.resolve(99)]).value")
        assert val(i) == 99

    def test_then_transforms_value(self):
        i = run("let v = Promise.resolve(10).then(x => x * 3).value")
        assert val(i) == 30

    def test_catch_handles_rejection(self):
        i = run('let v = Promise.reject("err").catch(e => "handled").value')
        assert val(i) == "handled"

    def test_then_chained(self):
        i = run("let v = Promise.resolve(5).then(x => x + 1).then(x => x * 2).value")
        assert val(i) == 12

    def test_any_first_fulfilled(self):
        i = run("let v = Promise.any([Promise.resolve(7)]).value")
        assert val(i) == 7


# ---------------------------------------------------------------------------
# Date namespace
# ---------------------------------------------------------------------------


class TestDateNamespace:
    def test_now_positive(self):
        i = run("let v = Date.now() > 0")
        assert val(i) is True

    def test_new_year(self):
        i = run("let d = Date.new(2024, 6, 15)\nlet v = d.year")
        assert val(i) == 2024

    def test_new_month(self):
        i = run("let d = Date.new(2024, 6, 15)\nlet v = d.month")
        assert val(i) == 6

    def test_new_day(self):
        i = run("let d = Date.new(2024, 6, 15)\nlet v = d.day")
        assert val(i) == 15

    def test_new_hour_minute_second(self):
        i = run("let d = Date.new(2024, 1, 1, 12, 30, 45)\nlet v = d.hour")
        assert val(i) == 12

    def test_toISOString(self):
        i = run("let d = Date.new(2024, 1, 1)\nlet v = d.toISOString()")
        assert "2024-01-01" in val(i)

    def test_getTime_epoch(self):
        i = run("let v = Date.new(1970, 1, 1).getTime() == 0")
        assert val(i) is True

    def test_getFullYear(self):
        i = run("let d = Date.new(2025, 3, 20)\nlet v = d.getFullYear()")
        assert val(i) == 2025

    def test_getDate(self):
        i = run("let d = Date.new(2025, 3, 20)\nlet v = d.getDate()")
        assert val(i) == 20

    def test_getMonth_zero_indexed(self):
        i = run("let d = Date.new(2025, 1, 1)\nlet v = d.getMonth()")
        assert val(i) == 0  # January = 0 (JS convention)

    def test_UTC(self):
        i = run("let v = Date.UTC(1970, 1, 1) == 0")
        assert val(i) is True

    def test_parse_iso(self):
        i = run('let v = Date.parse("1970-01-01") == 0')
        assert val(i) is True


# ---------------------------------------------------------------------------
# Reflect namespace
# ---------------------------------------------------------------------------


class TestReflectNamespace:
    def test_ownKeys(self):
        i = run("let v = Reflect.ownKeys({a: 1, b: 2})")
        assert sorted(val(i)) == ["a", "b"]

    def test_has_true(self):
        i = run('let v = Reflect.has({a: 1}, "a")')
        assert val(i) is True

    def test_has_false(self):
        i = run('let v = Reflect.has({a: 1}, "z")')
        assert val(i) is False

    def test_get(self):
        i = run('let v = Reflect.get({x: 42}, "x")')
        assert val(i) == 42

    def test_get_default(self):
        i = run('let v = Reflect.get({}, "missing", 99)')
        assert val(i) == 99

    def test_set(self):
        i = run('let o = {x: 1}\nReflect.set(o, "y", 99)\nlet v = o.y')
        assert val(i) == 99

    def test_set_returns_true(self):
        i = run('let v = Reflect.set({}, "k", 1)')
        assert val(i) is True

    def test_deleteProperty(self):
        i = run('let o = {x: 1, y: 2}\nReflect.deleteProperty(o, "x")\nlet v = o.y')
        assert val(i) == 2

    def test_deleteProperty_returns_true(self):
        i = run('let o = {x: 1}\nlet v = Reflect.deleteProperty(o, "x")')
        assert val(i) is True

    def test_deleteProperty_returns_false_nonexistent(self):
        i = run('let v = Reflect.deleteProperty({}, "nope")')
        assert val(i) is False

    def test_apply(self):
        i = run('fn add(a, b) { return a + b }\nlet v = Reflect.apply(add, null, [3, 4])')
        assert val(i) == 7
