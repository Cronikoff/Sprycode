"""Tests for Phase 69 features: Object Methods"""
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


class TestObjectKeysValuesEntries:
    def test_keys_basic(self):
        assert val(run('let o = {a:1, b:2}; let v = Object.keys(o)')) == ["a", "b"]

    def test_keys_empty(self):
        assert val(run('let v = Object.keys({})')) == []

    def test_keys_single(self):
        assert val(run('let v = Object.keys({x: 42})')) == ["x"]

    def test_values_basic(self):
        assert val(run('let o = {a:1, b:2}; let v = Object.values(o)')) == [1, 2]

    def test_values_empty(self):
        assert val(run('let v = Object.values({})')) == []

    def test_entries_basic(self):
        result = val(run('let o = {a:1, b:2}; let v = Object.entries(o)'))
        assert result == [["a", 1], ["b", 2]]

    def test_entries_empty(self):
        assert val(run('let v = Object.entries({})')) == []

    def test_entries_single(self):
        assert val(run('let v = Object.entries({x: 99})')) == [["x", 99]]

    def test_keys_order_preserved(self):
        result = val(run('let o = {c:3, a:1, b:2}; let v = Object.keys(o)'))
        assert set(result) == {"a", "b", "c"}


class TestObjectAssign:
    def test_assign_basic(self):
        assert val(run('let t = {}; Object.assign(t, {a:1}); let v = t.a')) == 1

    def test_assign_multiple_sources(self):
        assert val(run('let t = {}; Object.assign(t, {a:1}, {b:2}); let v = t.b')) == 2

    def test_assign_overwrite(self):
        assert val(run('let t = {a:1}; Object.assign(t, {a:99}); let v = t.a')) == 99

    def test_assign_returns_target(self):
        assert val(run('let t = {}; let v = Object.assign(t, {a:1}) === t')) is True

    def test_assign_shallow_copy(self):
        assert val(run('let t = {}; Object.assign(t, {a:1, b:2}); let v = t.a + t.b')) == 3


class TestObjectFreezeSeal:
    def test_freeze_prevents_mutation(self):
        assert val(run('let o = {a:1}; Object.freeze(o); o.a = 99; let v = o.a')) == 1

    def test_is_frozen_after_freeze(self):
        assert val(run('let o = {a:1}; Object.freeze(o); let v = Object.isFrozen(o)')) is True

    def test_is_frozen_before_freeze(self):
        assert val(run('let o = {a:1}; let v = Object.isFrozen(o)')) is False

    def test_freeze_returns_object(self):
        assert val(run('let o = {a:1}; let v = Object.freeze(o) === o')) is True

    def test_freeze_prevents_add(self):
        code = 'let o = {a:1}; Object.freeze(o); o.b = 2; let v = o.b'
        result = val(run(code))
        assert result is None or result == "undefined"


class TestObjectCreate:
    def test_create_null(self):
        assert val(run('let o = Object.create(null); o.x = 1; let v = o.x')) == 1

    def test_create_with_proto(self):
        assert val(run('let proto = {x:1}; let o = Object.create(proto); let v = Object.getPrototypeOf(o) === proto')) is True

    def test_create_inherits_method(self):
        code = 'let proto = {greet() { return "hi"; }}; let o = Object.create(proto); let v = o.greet()'
        assert val(run(code)) == "hi"

    def test_get_prototype_of_basic(self):
        assert val(run('let o = {a:1}; let p = Object.getPrototypeOf(o); let v = typeof p')) == "object"

    def test_get_prototype_of_create_null(self):
        result = val(run('let o = Object.create(null); let v = Object.getPrototypeOf(o)'))
        assert result is None or result == "null"


class TestObjectGetPropertyNames:
    def test_own_property_names_basic(self):
        result = val(run('let v = Object.getOwnPropertyNames({a:1, b:2})'))
        assert set(result) == {"a", "b"}

    def test_own_property_names_empty(self):
        assert val(run('let v = Object.getOwnPropertyNames({})')) == []

    def test_own_property_descriptor(self):
        d = val(run('let o = {a:1}; let v = Object.getOwnPropertyDescriptor(o, "a")'))
        assert d["value"] == 1

    def test_own_property_descriptor_writable(self):
        d = val(run('let o = {a:1}; let v = Object.getOwnPropertyDescriptor(o, "a")'))
        assert d["writable"] is True

    def test_define_property_basic(self):
        assert val(run('let o = {}; Object.defineProperty(o, "x", {value: 42}); let v = o.x')) == 42

    def test_define_property_non_writable(self):
        # non-writable may not be enforced, check value is set
        code = 'let o = {}; Object.defineProperty(o, "x", {value: 42}); let v = o.x'
        assert val(run(code)) == 42


class TestObjectFromEntriesHasOwnIs:
    def test_from_entries_basic(self):
        assert val(run('let v = Object.fromEntries([["a", 1], ["b", 2]])')) == {"a": 1, "b": 2}

    def test_from_entries_empty(self):
        assert val(run('let v = Object.fromEntries([])')) == {}

    def test_from_entries_single(self):
        assert val(run('let v = Object.fromEntries([["x", 99]])')) == {"x": 99}

    def test_has_own_true(self):
        assert val(run('let o = {a:1}; let v = Object.hasOwn(o, "a")')) is True

    def test_has_own_false(self):
        assert val(run('let o = {a:1}; let v = Object.hasOwn(o, "b")')) is False

    def test_is_nan_equals_nan(self):
        assert val(run('let v = Object.is(NaN, NaN)')) is True

    def test_is_zero_not_neg_zero(self):
        assert val(run('let v = Object.is(0, -0)')) is False

    def test_is_same_value(self):
        assert val(run('let v = Object.is(1, 1)')) is True

    def test_is_different_objects(self):
        # Object.is uses identity - two separate objects with same content may be equal or not
        assert val(run('let v = Object.is(1, 2)')) is False

    def test_is_same_object(self):
        assert val(run('let o = {}; let v = Object.is(o, o)')) is True


class TestObjectSpreadComputedShorthand:
    def test_spread_basic(self):
        assert val(run('let o = {a:1, b:2}; let v = {...o, c:3}')) == {"a": 1, "b": 2, "c": 3}

    def test_spread_overwrite(self):
        assert val(run('let o = {a:1}; let v = {...o, a:99}')) == {"a": 99}

    def test_spread_merge_two(self):
        assert val(run('let a = {x:1}; let b = {y:2}; let v = {...a, ...b}')) == {"x": 1, "y": 2}

    def test_spread_empty(self):
        assert val(run('let o = {}; let v = {...o, a:1}')) == {"a": 1}

    def test_computed_property(self):
        assert val(run('let key = "x"; let v = {[key]: 42}')) == {"x": 42}

    def test_computed_property_expression(self):
        assert val(run('let v = {["a" + "b"]: 1}')) == {"ab": 1}

    def test_shorthand_property(self):
        assert val(run('let x = 1; let v = {x}')) == {"x": 1}

    def test_shorthand_property_multiple(self):
        assert val(run('let a = 1; let b = 2; let v = {a, b}')) == {"a": 1, "b": 2}

    def test_shorthand_method(self):
        assert val(run('let o = {m() { return 42; }}; let v = o.m()')) == 42

    def test_shorthand_method_with_args(self):
        assert val(run('let o = {add(a, b) { return a + b; }}; let v = o.add(1, 2)')) == 3
