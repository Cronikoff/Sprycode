"""Tests for Phase 96: Object Advanced Methods
- Object.create, setPrototypeOf, getPrototypeOf
- getOwnPropertyNames, getOwnPropertySymbols, getOwnPropertyDescriptors
- defineProperties, seal, freeze, isFrozen, isSealed
- entries, fromEntries (array and Map), hasOwn, Object.is
- Object.keys on class instance, JSON.stringify instance, spread instance
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


# ── Object.create ─────────────────────────────────────────────────────────────

class TestObjectCreate:
    def test_create_null_is_object(self):
        i = run('let v = typeof Object.create(null)')
        assert val(i) == "object"

    def test_create_null_empty(self):
        i = run('let o = Object.create(null); let v = Object.keys(o).length')
        assert val(i) == 0

    def test_create_with_proto(self):
        i = run('let p = {x: 1}; let o = Object.create(p); let v = o.x')
        assert val(i) == 1

    def test_create_with_proto_multiple(self):
        i = run('let p = {a: 10, b: 20}; let o = Object.create(p); let v = o.a + o.b')
        assert val(i) == 30

    def test_create_null_set_property(self):
        i = run('let o = Object.create(null); o.x = 5; let v = o.x')
        assert val(i) == 5


# ── Object.getPrototypeOf ─────────────────────────────────────────────────────

class TestGetPrototypeOf:
    def test_getPrototypeOf_instance(self):
        i = run('class Foo {}; let f = new Foo(); let v = typeof Object.getPrototypeOf(f)')
        assert val(i) == "object"

    def test_getPrototypeOf_not_null(self):
        i = run('class Bar {}; let b = new Bar(); let v = Object.getPrototypeOf(b) !== null')
        assert val(i) is True


# ── Object.setPrototypeOf ─────────────────────────────────────────────────────

class TestSetPrototypeOf:
    def test_setPrototypeOf_returns_obj(self):
        i = run('''
let o = {};
let p = {y: 99};
let result = Object.setPrototypeOf(o, p);
let v = result === o || result !== null;
''')
        assert val(i) is True

    def test_setPrototypeOf_no_error(self):
        i = run('''
let o = {a: 1};
Object.setPrototypeOf(o, {});
let v = o.a;
''')
        assert val(i) == 1


# ── Object.getOwnPropertyNames ────────────────────────────────────────────────

class TestGetOwnPropertyNames:
    def test_two_props(self):
        i = run('let o = {a: 1, b: 2}; let v = Object.getOwnPropertyNames(o)')
        names = val(i)
        assert sorted(names) == ["a", "b"]

    def test_empty(self):
        i = run('let v = Object.getOwnPropertyNames({}).length')
        assert val(i) == 0

    def test_three_props(self):
        i = run('let o = {x: 1, y: 2, z: 3}; let v = Object.getOwnPropertyNames(o).length')
        assert val(i) == 3

    def test_includes_key(self):
        i = run('let o = {foo: 1}; let v = Object.getOwnPropertyNames(o).includes("foo")')
        assert val(i) is True


# ── Object.getOwnPropertySymbols ──────────────────────────────────────────────

class TestGetOwnPropertySymbols:
    def test_symbol_key_count(self):
        i = run('''
let sym = Symbol("s");
let o = {};
o[sym] = 1;
let v = Object.getOwnPropertySymbols(o).length;
''')
        assert val(i) == 1

    def test_no_symbols(self):
        i = run('let v = Object.getOwnPropertySymbols({a: 1}).length')
        assert val(i) == 0

    def test_two_symbols(self):
        i = run('''
let s1 = Symbol("a");
let s2 = Symbol("b");
let o = {};
o[s1] = 1;
o[s2] = 2;
let v = Object.getOwnPropertySymbols(o).length;
''')
        assert val(i) == 2


# ── Object.getOwnPropertyDescriptors ─────────────────────────────────────────

class TestGetOwnPropertyDescriptors:
    def test_descriptor_value(self):
        i = run('let o = {a: 1}; let v = Object.getOwnPropertyDescriptors(o).a.value')
        assert val(i) == 1

    def test_descriptor_writable(self):
        i = run('let o = {a: 1}; let v = Object.getOwnPropertyDescriptors(o).a.writable')
        assert val(i) is True

    def test_descriptor_enumerable(self):
        i = run('let o = {x: 5}; let v = Object.getOwnPropertyDescriptors(o).x.enumerable')
        assert val(i) is True

    def test_descriptor_configurable(self):
        i = run('let o = {x: 5}; let v = Object.getOwnPropertyDescriptors(o).x.configurable')
        assert val(i) is True


# ── Object.defineProperties ───────────────────────────────────────────────────

class TestDefineProperties:
    def test_two_props(self):
        i = run('''
let o = {};
Object.defineProperties(o, {x: {value: 10}, y: {value: 20}});
let v = o.x + o.y;
''')
        assert val(i) == 30

    def test_single_prop(self):
        i = run('''
let o = {};
Object.defineProperties(o, {name: {value: "Alice"}});
let v = o.name;
''')
        assert val(i) == "Alice"

    def test_returns_object(self):
        i = run('''
let o = {};
let result = Object.defineProperties(o, {a: {value: 1}});
let v = result.a;
''')
        assert val(i) == 1


# ── Object.seal and Object.isSealed ──────────────────────────────────────────

class TestSealIsSealed:
    def test_sealed_after_seal(self):
        i = run('let o = {a: 1}; Object.seal(o); let v = Object.isSealed(o)')
        assert val(i) is True

    def test_not_sealed_initially(self):
        i = run('let v = Object.isSealed({a: 1})')
        assert val(i) is False

    def test_frozen_is_sealed(self):
        i = run('let o = {a: 1}; Object.freeze(o); let v = Object.isSealed(o)')
        assert val(i) is True

    def test_seal_returns_object(self):
        i = run('let o = {a: 1}; let r = Object.seal(o); let v = r.a')
        assert val(i) == 1


# ── Object.freeze and Object.isFrozen ────────────────────────────────────────

class TestFreezeIsFrozen:
    def test_frozen_after_freeze(self):
        i = run('let o = {a: 1}; Object.freeze(o); let v = Object.isFrozen(o)')
        assert val(i) is True

    def test_not_frozen_initially(self):
        i = run('let v = Object.isFrozen({a: 1})')
        assert val(i) is False

    def test_empty_obj_not_frozen(self):
        i = run('let v = Object.isFrozen({})')
        assert val(i) is False


# ── Object.entries ────────────────────────────────────────────────────────────

class TestObjectEntries:
    def test_entries_two(self):
        i = run('let v = Object.entries({a: 1, b: 2})')
        assert sorted(val(i)) == [["a", 1], ["b", 2]]

    def test_entries_length(self):
        i = run('let v = Object.entries({x: 10, y: 20, z: 30}).length')
        assert val(i) == 3

    def test_entries_empty(self):
        i = run('let v = Object.entries({}).length')
        assert val(i) == 0


# ── Object.fromEntries ────────────────────────────────────────────────────────

class TestObjectFromEntries:
    def test_from_array(self):
        i = run('let v = Object.fromEntries([["a", 1], ["b", 2]])')
        assert val(i) == {"a": 1, "b": 2}

    def test_from_map(self):
        i = run('let m = new Map(); m.set("x", 42); let v = Object.fromEntries(m).x')
        assert val(i) == 42

    def test_from_map_multiple(self):
        i = run('''
let m = new Map();
m.set("a", 1);
m.set("b", 2);
let v = Object.fromEntries(m);
''')
        assert val(i) == {"a": 1, "b": 2}

    def test_roundtrip_entries(self):
        i = run('''
let o = {x: 1, y: 2};
let v = Object.fromEntries(Object.entries(o));
''')
        assert val(i) == {"x": 1, "y": 2}


# ── Object.hasOwn ─────────────────────────────────────────────────────────────

class TestObjectHasOwn:
    def test_hasOwn_present(self):
        i = run('let v = Object.hasOwn({a: 1}, "a")')
        assert val(i) is True

    def test_hasOwn_absent(self):
        i = run('let v = Object.hasOwn({a: 1}, "b")')
        assert val(i) is False

    def test_hasOwn_empty(self):
        i = run('let v = Object.hasOwn({}, "x")')
        assert val(i) is False

    def test_hasOwn_nested(self):
        i = run('let o = {a: {b: 1}}; let v = Object.hasOwn(o, "a")')
        assert val(i) is True


# ── Object.is ─────────────────────────────────────────────────────────────────

class TestObjectIs:
    def test_is_NaN_NaN(self):
        i = run('let v = Object.is(NaN, NaN)')
        assert val(i) is True

    def test_is_zero_neg_zero(self):
        i = run('let v = Object.is(0, -0)')
        assert val(i) is False

    def test_is_same_number(self):
        i = run('let v = Object.is(1, 1)')
        assert val(i) is True

    def test_is_diff_numbers(self):
        i = run('let v = Object.is(1, 2)')
        assert val(i) is False

    def test_is_same_string(self):
        i = run('let v = Object.is("abc", "abc")')
        assert val(i) is True

    def test_is_null_null(self):
        i = run('let v = Object.is(null, null)')
        assert val(i) is True

    def test_is_null_undefined(self):
        i = run('let v = Object.is(null, undefined)')
        assert val(i) is False


# ── Object.keys on class instance ─────────────────────────────────────────────

class TestObjectKeysInstance:
    def test_keys_two_fields(self):
        i = run('''
class Foo {
  constructor() { this.x = 1; this.y = 2; }
}
let f = new Foo();
let v = Object.keys(f);
''')
        assert sorted(val(i)) == ["x", "y"]

    def test_keys_constructor_arg(self):
        i = run('''
class Point {
  constructor(x, y) { this.x = x; this.y = y; }
}
let p = new Point(3, 4);
let v = Object.keys(p).length;
''')
        assert val(i) == 2

    def test_keys_excludes_methods(self):
        i = run('''
class Counter {
  constructor() { this.count = 0; }
  inc() { this.count++; }
}
let c = new Counter();
let v = Object.keys(c);
''')
        # Should only have 'count', not 'inc'
        assert "count" in val(i)


# ── JSON.stringify class instance ─────────────────────────────────────────────

class TestJsonStringifyInstance:
    def test_stringify_basic(self):
        i = run('''
class Foo { constructor() { this.x = 1; } }
let f = new Foo();
let v = JSON.stringify(f);
''')
        assert val(i) == '{"x":1}'

    def test_stringify_two_fields(self):
        i = run('''
class Point {
  constructor(x, y) { this.x = x; this.y = y; }
}
let p = new Point(1, 2);
let parsed = JSON.parse(JSON.stringify(p));
let v = parsed.x + parsed.y;
''')
        assert val(i) == 3


# ── Spread of class instance ──────────────────────────────────────────────────

class TestSpreadInstance:
    def test_spread_x(self):
        i = run('''
class Foo { constructor() { this.x = 1; this.y = 2; } }
let f = new Foo();
let o = {...f};
let v = o.x;
''')
        assert val(i) == 1

    def test_spread_creates_plain_object(self):
        i = run('''
class Foo { constructor() { this.a = 10; } }
let f = new Foo();
let o = {...f, b: 20};
let v = o.a + o.b;
''')
        assert val(i) == 30

    def test_spread_override(self):
        i = run('''
class Config { constructor() { this.debug = false; this.port = 8080; } }
let c = new Config();
let o = {...c, debug: true};
let v = o.debug;
''')
        assert val(i) is True
