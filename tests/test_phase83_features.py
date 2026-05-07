"""Tests for Phase 83: Symbols Advanced."""
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
# Basic Symbol creation
# ---------------------------------------------------------------------------

def test_symbol_creates():
    i = run('var v = Symbol("desc");')
    assert val(i) is not None


def test_symbol_has_description():
    i = run('var s = Symbol("hello"); var v = s.description;')
    assert val(i) == "hello"


def test_symbol_description_empty():
    i = run('var s = Symbol(""); var v = s.description;')
    assert val(i) == ""


def test_symbol_description_none():
    i = run('var s = Symbol(); var v = s.description;')
    assert val(i) is None or val(i) == "" or val(i) == "undefined"


def test_symbol_tostring():
    i = run('var s = Symbol("hi"); var v = s.toString();')
    assert val(i) == "Symbol(hi)"


def test_symbol_tostring_empty():
    i = run('var s = Symbol(""); var v = s.toString();')
    assert val(i) == "Symbol()"


def test_symbol_typeof():
    i = run('var s = Symbol("x"); var v = typeof s;')
    assert val(i) == "symbol"


def test_symbol_typeof_global_registry():
    i = run('var s = Symbol.for("k"); var v = typeof s;')
    assert val(i) == "symbol"


# ---------------------------------------------------------------------------
# Symbol uniqueness
# ---------------------------------------------------------------------------

def test_symbol_unique():
    i = run('var v = Symbol("x") !== Symbol("x");')
    assert val(i) == True


def test_symbol_not_equal_different():
    i = run('var a = Symbol("x"); var b = Symbol("x"); var v = a === b;')
    assert val(i) == False


def test_symbol_equal_to_self():
    i = run('var a = Symbol("x"); var v = a === a;')
    assert val(i) == True


def test_two_symbols_not_equal():
    i = run('var a = Symbol("foo"); var b = Symbol("bar"); var v = a !== b;')
    assert val(i) == True


# ---------------------------------------------------------------------------
# Symbol.for global registry
# ---------------------------------------------------------------------------

def test_symbol_for_creates():
    i = run('var v = Symbol.for("key");')
    assert val(i) is not None


def test_symbol_for_same_key():
    i = run('var v = Symbol.for("k") === Symbol.for("k");')
    assert val(i) == True


def test_symbol_for_different_keys():
    i = run('var v = Symbol.for("a") !== Symbol.for("b");')
    assert val(i) == True


def test_symbol_for_not_equal_local():
    i = run('var local = Symbol("k"); var global_ = Symbol.for("k"); var v = local !== global_;')
    assert val(i) == True


def test_symbol_keyfor():
    i = run('var s = Symbol.for("myKey"); var v = Symbol.keyFor(s);')
    assert val(i) == "myKey"


def test_symbol_keyfor_not_in_registry():
    i = run('var s = Symbol("local"); var v = Symbol.keyFor(s);')
    assert val(i) is None or val(i) == "undefined"


def test_symbol_for_description():
    i = run('var s = Symbol.for("test"); var v = s.description;')
    assert val(i) == "test"


# ---------------------------------------------------------------------------
# Well-known symbols
# ---------------------------------------------------------------------------

def test_symbol_iterator_exists():
    i = run('var v = typeof Symbol.iterator;')
    assert val(i) == "symbol"


def test_symbol_toprimitive_exists():
    i = run('var v = typeof Symbol.toPrimitive;')
    assert val(i) == "symbol"


def test_symbol_hasinstance_exists():
    i = run('var v = typeof Symbol.hasInstance;')
    assert val(i) == "symbol"


def test_symbol_iterator_unique():
    i = run('var v = Symbol.iterator === Symbol.iterator;')
    assert val(i) == True


def test_symbol_toprimitive_tostring():
    i = run('var v = Symbol.toPrimitive.toString();')
    assert "Symbol" in val(i)


def test_symbol_hasinstance_unique():
    i = run('var v = Symbol.hasInstance === Symbol.hasInstance;')
    assert val(i) == True


# ---------------------------------------------------------------------------
# Symbol as object key
# ---------------------------------------------------------------------------

def test_symbol_as_key():
    i = run("""
var sym = Symbol("key");
var obj = {};
obj[sym] = 42;
var v = obj[sym];
""")
    assert val(i) == 42


def test_symbol_key_isolated():
    i = run("""
var sym1 = Symbol("k");
var sym2 = Symbol("k");
var obj = {};
obj[sym1] = 1;
obj[sym2] = 2;
var v = obj[sym1];
""")
    assert val(i) == 1


def test_symbol_key_not_in_for_in():
    i = run("""
var sym = Symbol("k");
var obj = {a: 1, b: 2};
obj[sym] = 99;
var count = 0;
for (var k in obj) { count++; }
var v = count;
""")
    assert val(i) == 2


def test_symbol_key_not_in_object_keys():
    i = run("""
var sym = Symbol("k");
var obj = {a: 1, b: 2};
obj[sym] = 3;
var v = Object.keys(obj).length;
""")
    assert val(i) == 2


def test_object_get_own_property_symbols():
    i = run("""
var sym = Symbol("k");
var obj = {a: 1};
obj[sym] = 2;
var v = Object.getOwnPropertySymbols(obj).length;
""")
    assert val(i) == 1


def test_object_get_own_property_symbols_returns_sym():
    i = run("""
var sym = Symbol("k");
var obj = {a: 1};
obj[sym] = 42;
var syms = Object.getOwnPropertySymbols(obj);
var v = obj[syms[0]];
""")
    assert val(i) == 42


def test_multiple_symbol_keys():
    i = run("""
var s1 = Symbol("a");
var s2 = Symbol("b");
var obj = {};
obj[s1] = 10;
obj[s2] = 20;
var v = Object.getOwnPropertySymbols(obj).length;
""")
    assert val(i) == 2


# ---------------------------------------------------------------------------
# Symbol.hasInstance
# ---------------------------------------------------------------------------

def test_symbol_has_instance():
    i = run("""
class Even {
    static [Symbol.hasInstance](n) { return n % 2 === 0; }
}
var v = 4 instanceof Even;
""")
    assert val(i) == True


def test_symbol_has_instance_false():
    i = run("""
class Even {
    static [Symbol.hasInstance](n) { return n % 2 === 0; }
}
var v = 3 instanceof Even;
""")
    assert val(i) == False


# ---------------------------------------------------------------------------
# Symbol.iterator custom
# ---------------------------------------------------------------------------

def test_symbol_iterator_custom_class():
    i = run("""
class Range {
    constructor(start, end) {
        this.start = start;
        this.end = end;
    }
    [Symbol.iterator]() {
        var cur = this.start;
        var end = this.end;
        return {
            next() {
                if (cur <= end) return { value: cur++, done: false };
                return { value: undefined, done: true };
            }
        };
    }
}
var r = new Range(1, 3);
var v = [];
for (var x of r) { v.push(x); }
""")
    assert val(i) == [1, 2, 3]


def test_symbol_iterator_custom_sum():
    i = run("""
class Counter {
    constructor(n) { this.n = n; }
    [Symbol.iterator]() {
        var i = 0;
        var n = this.n;
        return {
            next() {
                if (i < n) return { value: i++, done: false };
                return { value: undefined, done: true };
            }
        };
    }
}
var sum = 0;
for (var x of new Counter(5)) { sum += x; }
var v = sum;
""")
    assert val(i) == 10  # 0+1+2+3+4


# ---------------------------------------------------------------------------
# typeof and string representation
# ---------------------------------------------------------------------------

def test_symbol_not_coercible_typeof():
    i = run('var s = Symbol("test"); var v = typeof s === "symbol";')
    assert val(i) == True


def test_symbol_tostring_format():
    i = run('var s = Symbol("abc"); var v = s.toString().startsWith("Symbol");')
    assert val(i) == True


def test_symbol_description_via_tostring():
    i = run('var s = Symbol("myDesc"); var v = s.toString().includes("myDesc");')
    assert val(i) == True
