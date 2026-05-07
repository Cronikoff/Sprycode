"""Tests for Phase 101: Computed Properties & Dynamic Keys"""
from __future__ import annotations
from typing import Any
import pytest
from sprycode.interpreter import Interpreter, SPRY_UNDEFINED
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


# ── Computed object properties ────────────────────────────────────────────────

class TestComputedObjectProperty:
    def test_computed_string_key(self):
        i = run("let key = \"name\"; let obj = {[key]: \"Alice\"}; let v = obj.name;")
        assert val(i) == "Alice"

    def test_computed_number_key(self):
        i = run("let obj = {[1 + 1]: \"two\"}; let v = obj[\"2\"];")
        assert val(i) == "two"

    def test_computed_template_literal_key(self):
        i = run("""
let prefix = \"get\"; let suffix = \"Name\";
let obj = {[`${prefix}${suffix}`]: \"Alice\"};
let v = obj.getName;
""")
        assert val(i) == "Alice"

    def test_computed_multiple_computed_keys(self):
        i = run("""
let k1 = \"a\"; let k2 = \"b\";
let obj = {[k1]: 1, [k2]: 2};
let v = obj.a + obj.b;
""")
        assert val(i) == 3

    def test_computed_mixed_with_regular(self):
        i = run("""
let key = \"x\";
let obj = {[key]: 10, y: 20};
let v = obj.x + obj.y;
""")
        assert val(i) == 30

    def test_computed_overwrites_existing(self):
        i = run("""
let key = \"x\";
let obj = {x: 1, [key]: 2};
let v = obj.x;
""")
        assert val(i) == 2

    def test_computed_expression_as_key(self):
        i = run("""
let n = 3;
let obj = {[n * 2]: \"six\"};
let v = obj[\"6\"];
""")
        assert val(i) == "six"

    def test_computed_key_from_array(self):
        i = run("""
let keys = [\"a\", \"b\", \"c\"];
let obj = {[keys[0]]: 10, [keys[1]]: 20, [keys[2]]: 30};
let v = obj.a + obj.b + obj.c;
""")
        assert val(i) == 60


# ── Computed method in object ─────────────────────────────────────────────────

class TestComputedObjectMethod:
    def test_computed_method_basic(self):
        i = run("""
let m = \"greet\";
let obj = {[m]() { return \"hello\"; }};
let v = obj.greet();
""")
        assert val(i) == "hello"

    def test_computed_method_with_arg(self):
        i = run("""
let m = \"double\";
let obj = {[m](x) { return x * 2; }};
let v = obj.double(5);
""")
        assert val(i) == 10

    def test_computed_method_from_variable(self):
        i = run("""
let methodName = \"compute\";
let obj = {[methodName](a, b) { return a + b; }};
let v = obj.compute(3, 4);
""")
        assert val(i) == 7


# ── Computed class method ─────────────────────────────────────────────────────

class TestComputedClassMethod:
    def test_computed_class_method_basic(self):
        i = run("""
let key = \"myMethod\";
class Foo {
  [key]() { return 42; }
}
let f = new Foo();
let v = f.myMethod();
""")
        assert val(i) == 42

    def test_computed_class_method_with_arg(self):
        i = run("""
let key = \"mul\";
class Calc {
  [key](a, b) { return a * b; }
}
let c = new Calc();
let v = c.mul(3, 7);
""")
        assert val(i) == 21

    def test_computed_class_method_expression(self):
        i = run("""
let prefix = \"get\";
class Foo {
  [prefix + \"Value\"]() { return 99; }
}
let f = new Foo();
let v = f.getValue();
""")
        assert val(i) == 99


# ── Computed static field ─────────────────────────────────────────────────────

class TestComputedStaticField:
    def test_computed_static_basic(self):
        i = run("""
let key = \"MAX\";
class Config {
  static [key] = 100;
}
let v = Config.MAX;
""")
        assert val(i) == 100

    def test_computed_static_string(self):
        i = run("""
let key = \"VERSION\";
class App {
  static [key] = \"1.0.0\";
}
let v = App.VERSION;
""")
        assert val(i) == "1.0.0"

    def test_computed_static_expression(self):
        i = run("""
let prefix = \"MAX\";
class Limit {
  static [prefix + \"_SIZE\"] = 1024;
}
let v = Limit.MAX_SIZE;
""")
        assert val(i) == 1024


# ── Dynamic property access and assignment ────────────────────────────────────

class TestDynamicPropertyAccess:
    def test_dynamic_get(self):
        i = run("""
let obj = {x: 1, y: 2};
let prop = \"x\";
let v = obj[prop];
""")
        assert val(i) == 1

    def test_dynamic_set(self):
        i = run("""
let obj = {};
let prop = \"name\";
obj[prop] = \"Alice\";
let v = obj.name;
""")
        assert val(i) == "Alice"

    def test_dynamic_update(self):
        i = run("""
let obj = {n: 5};
let prop = \"n\";
obj[prop] = obj[prop] * 2;
let v = obj.n;
""")
        assert val(i) == 10

    def test_dynamic_nested(self):
        i = run("""
let obj = {a: {b: {c: 42}}};
let v = obj[\"a\"][\"b\"][\"c\"];
""")
        assert val(i) == 42

    def test_dynamic_iterate_keys(self):
        i = run("""
let obj = {a: 1, b: 2, c: 3};
let sum = 0;
let keys = Object.keys(obj);
for (let k of keys) { sum = sum + obj[k]; }
let v = sum;
""")
        assert val(i) == 6


# ── delete obj[key] ───────────────────────────────────────────────────────────

class TestDeleteDynamicKey:
    def test_delete_key(self):
        i = run("""
let obj = {a: 1, b: 2};
let key = \"a\";
delete obj[key];
let v = \"a\" in obj;
""")
        assert val(i) is False

    def test_delete_key_preserves_others(self):
        i = run("""
let obj = {a: 1, b: 2, c: 3};
delete obj[\"b\"];
let v = Object.keys(obj).length;
""")
        assert val(i) == 2

    def test_delete_by_variable(self):
        i = run("""
let obj = {x: 10, y: 20};
let prop = \"x\";
delete obj[prop];
let v = \"y\" in obj;
""")
        assert val(i) is True


# ── Optional computed access ──────────────────────────────────────────────────

class TestOptionalComputedAccess:
    def test_optional_computed_exists(self):
        i = run("let obj = {x: 1}; let v = obj?.[\"x\"];")
        assert val(i) == 1

    def test_optional_computed_null(self):
        i = run("let n = null; let v = n?.[\"x\"];")
        assert val(i) == SPRY_UNDEFINED

    def test_optional_computed_undefined(self):
        i = run("let u = undefined; let v = u?.[\"x\"];")
        assert val(i) == SPRY_UNDEFINED

    def test_optional_computed_with_variable(self):
        i = run("""
let obj = {name: \"Alice\"};
let key = \"name\";
let v = obj?.[key];
""")
        assert val(i) == "Alice"

    def test_optional_chain_computed(self):
        i = run("""
let obj = {a: {b: 42}};
let v = obj?.a?.[\"b\"];
""")
        assert val(i) == 42


# ── Property shorthand ────────────────────────────────────────────────────────

class TestPropertyShorthand:
    def test_shorthand_basic(self):
        i = run("let x = 10; let y = 20; let obj = {x, y}; let v = obj.x + obj.y;")
        assert val(i) == 30

    def test_shorthand_single(self):
        i = run("let name = \"Alice\"; let obj = {name}; let v = obj.name;")
        assert val(i) == "Alice"

    def test_shorthand_mixed(self):
        i = run("let a = 1; let obj = {a, b: 2}; let v = obj.a + obj.b;")
        assert val(i) == 3

    def test_shorthand_preserves_value(self):
        i = run("let n = 42; let obj = {n}; n = 0; let v = obj.n;")
        assert val(i) == 42


# ── Spread in object literal ──────────────────────────────────────────────────

class TestObjectSpread:
    def test_spread_two_objects(self):
        i = run("let a = {x: 1}; let b = {y: 2}; let c = {...a, ...b}; let v = c.x + c.y;")
        assert val(i) == 3

    def test_spread_override(self):
        i = run("let a = {x: 1, y: 2}; let b = {...a, y: 99}; let v = b.y;")
        assert val(i) == 99

    def test_spread_merge_three(self):
        i = run("""
let a = {x: 1}; let b = {y: 2}; let c = {z: 3};
let merged = {...a, ...b, ...c};
let v = merged.x + merged.y + merged.z;
""")
        assert val(i) == 6

    def test_spread_does_not_modify_original(self):
        i = run("""
let a = {x: 1};
let b = {...a, y: 2};
let v = \"y\" in a;
""")
        assert val(i) is False

    def test_spread_with_extra_props(self):
        i = run("""
let defaults = {a: 1, b: 2, c: 3};
let overrides = {b: 99};
let result = {...defaults, ...overrides};
let v = result.b;
""")
        assert val(i) == 99


# ── Nested computed props ─────────────────────────────────────────────────────

class TestNestedComputedProps:
    def test_nested_computed(self):
        i = run("""
let k1 = \"a\"; let k2 = \"b\";
let obj = {[k1]: {[k2]: 42}};
let v = obj.a.b;
""")
        assert val(i) == 42

    def test_nested_computed_access(self):
        i = run("""
let outer = \"level1\";
let inner = \"level2\";
let obj = {[outer]: {[inner]: \"deep\"}};
let v = obj[outer][inner];
""")
        assert val(i) == "deep"


# ── Object.keys on computed-prop object ──────────────────────────────────────

class TestObjectKeysOnComputed:
    def test_keys_with_computed(self):
        i = run("""
let key = \"x\";
let obj = {[key]: 1, y: 2};
let v = Object.keys(obj).length;
""")
        assert val(i) == 2

    def test_keys_all_computed(self):
        i = run("""
let k1 = \"a\"; let k2 = \"b\"; let k3 = \"c\";
let obj = {[k1]: 1, [k2]: 2, [k3]: 3};
let v = Object.keys(obj).length;
""")
        assert val(i) == 3

    def test_keys_contain_computed(self):
        i = run("""
let key = \"dynamic\";
let obj = {[key]: 99, static: 0};
let v = Object.keys(obj).includes(\"dynamic\");
""")
        assert val(i) is True


# ── Property names with special characters ────────────────────────────────────

class TestSpecialCharProperties:
    def test_hyphenated_key(self):
        i = run("""
let obj = {};
obj[\"foo-bar\"] = 42;
let v = obj[\"foo-bar\"];
""")
        assert val(i) == 42

    def test_space_in_key(self):
        i = run("""
let obj = {};
obj[\"hello world\"] = 99;
let v = obj[\"hello world\"];
""")
        assert val(i) == 99

    def test_dot_in_key(self):
        i = run("""
let obj = {};
obj[\"a.b.c\"] = 5;
let v = obj[\"a.b.c\"];
""")
        assert val(i) == 5

    def test_numeric_string_key(self):
        i = run("""
let obj = {};
obj[\"123\"] = \"num\";
let v = obj[\"123\"];
""")
        assert val(i) == "num"


# ── in operator with computed key ─────────────────────────────────────────────

class TestInOperatorComputed:
    def test_in_computed_true(self):
        i = run("let key = \"x\"; let obj = {x: 1}; let v = key in obj;")
        assert val(i) is True

    def test_in_computed_false(self):
        i = run("let key = \"z\"; let obj = {x: 1}; let v = key in obj;")
        assert val(i) is False

    def test_in_computed_after_delete(self):
        i = run("""
let obj = {a: 1, b: 2};
let key = \"a\";
delete obj[key];
let v = key in obj;
""")
        assert val(i) is False

    def test_in_with_expression(self):
        i = run("let obj = {sum: 5}; let v = (\"su\" + \"m\") in obj;")
        assert val(i) is True


# ── Computed getter/setter ────────────────────────────────────────────────────

class TestComputedGetterSetter:
    def test_computed_getter(self):
        i = run("""
let k = \"val\";
let obj = {
  _v: 10,
  get [k]() { return this._v; }
};
let v = obj.val;
""")
        assert val(i) == 10

    def test_computed_setter(self):
        i = run("""
let k = \"val\";
let obj = {
  _v: 0,
  get [k]() { return this._v; },
  set [k](x) { this._v = x * 2; }
};
obj.val = 5;
let v = obj.val;
""")
        assert val(i) == 10

    def test_computed_getter_expression(self):
        i = run("""
let prefix = \"get\";
let obj = {
  _n: 7,
  get [prefix + \"N\"]() { return this._n; }
};
let v = obj.getN;
""")
        assert val(i) == 7


# ── Template literal as computed key ─────────────────────────────────────────

class TestTemplateLiteralComputedKey:
    def test_template_literal_key(self):
        i = run("""
let prefix = \"get\";
let obj = {[`${prefix}Name`]: \"Alice\"};
let v = obj.getName;
""")
        assert val(i) == "Alice"

    def test_template_literal_method_key(self):
        i = run("""
let action = \"compute\";
let obj = {[`${action}Sum`](a, b) { return a + b; }};
let v = obj.computeSum(3, 4);
""")
        assert val(i) == 7

    def test_template_literal_dynamic_key(self):
        i = run("""
let type = \"circle\";
let obj = {[`area_${type}`]: 3.14};
let v = obj.area_circle;
""")
        assert val(i) == 3.14
