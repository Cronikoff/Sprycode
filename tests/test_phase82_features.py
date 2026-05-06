"""Tests for Phase 82: Closures and Scoping."""
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
# Basic closure
# ---------------------------------------------------------------------------

def test_basic_closure_captures_variable():
    i = run("""
var x = 10;
function getX() { return x; }
var v = getX();
""")
    assert val(i) == 10


def test_closure_captures_after_definition():
    i = run("""
var x = 1;
function getX() { return x; }
x = 42;
var v = getX();
""")
    assert val(i) == 42


def test_closure_captures_mutable():
    i = run("""
var count = 0;
function inc() { count++; }
inc(); inc(); inc();
var v = count;
""")
    assert val(i) == 3


def test_closure_inner_function():
    i = run("""
function outer() {
    var x = 99;
    function inner() { return x; }
    return inner();
}
var v = outer();
""")
    assert val(i) == 99


def test_closure_returned_function():
    i = run("""
function makeAdder(n) {
    return function(x) { return x + n; };
}
var add10 = makeAdder(10);
var v = add10(5);
""")
    assert val(i) == 15


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

def test_factory_returns_closure():
    i = run("""
function makeMultiplier(factor) {
    return function(x) { return x * factor; };
}
var double = makeMultiplier(2);
var triple = makeMultiplier(3);
var v = double(5) + triple(5);
""")
    assert val(i) == 25


def test_each_closure_independent_scope():
    i = run("""
function makeAdder(n) {
    return function(x) { return x + n; };
}
var add1 = makeAdder(1);
var add2 = makeAdder(2);
var v = add1(10) + add2(10);
""")
    assert val(i) == 23  # 11 + 12


def test_counter_factory():
    i = run("""
function makeCounter() {
    var count = 0;
    return function() {
        count++;
        return count;
    };
}
var counter = makeCounter();
counter(); counter();
var v = counter();
""")
    assert val(i) == 3


def test_two_independent_counters():
    i = run("""
function makeCounter() {
    var count = 0;
    return function() { count++; return count; };
}
var c1 = makeCounter();
var c2 = makeCounter();
c1(); c1(); c1();
c2();
var v = c1() + c2();
""")
    assert val(i) == 6  # c1=4, c2=2


def test_counter_does_not_share_state():
    i = run("""
function makeCounter() {
    var n = 0;
    return function() { n++; return n; };
}
var a = makeCounter();
var b = makeCounter();
a(); a();
var v = b();
""")
    assert val(i) == 1


# ---------------------------------------------------------------------------
# IIFE
# ---------------------------------------------------------------------------

def test_iife_basic():
    i = run("""
var v = (function() { return 42; })();
""")
    assert val(i) == 42


def test_iife_with_arg():
    i = run("""
var v = (function(x) { return x * 2; })(21);
""")
    assert val(i) == 42


def test_iife_scope_isolation():
    i = run("""
var x = 1;
(function() { var x = 99; })();
var v = x;
""")
    assert val(i) == 1


def test_iife_returns_object():
    i = run("""
var obj = (function() { return { a: 1, b: 2 }; })();
var v = obj.a + obj.b;
""")
    assert val(i) == 3


# ---------------------------------------------------------------------------
# Module pattern
# ---------------------------------------------------------------------------

def test_module_pattern_counter():
    i = run("""
var counter = (function() {
    var count = 0;
    return {
        inc: function() { count++; },
        get: function() { return count; }
    };
})();
counter.inc();
counter.inc();
counter.inc();
var v = counter.get();
""")
    assert val(i) == 3


def test_module_pattern_encapsulates():
    i = run("""
var mod = (function() {
    var hidden = 42;
    return { getHidden: function() { return hidden; } };
})();
var v = mod.getHidden();
""")
    assert val(i) == 42


# ---------------------------------------------------------------------------
# Shared closures
# ---------------------------------------------------------------------------

def test_shared_closure_multiple_fns():
    i = run("""
var shared = 0;
function inc() { shared++; }
function dec() { shared--; }
function get() { return shared; }
inc(); inc(); dec();
var v = get();
""")
    assert val(i) == 1


def test_shared_state_via_closure():
    i = run("""
function makeBank() {
    var balance = 0;
    return {
        deposit: function(n) { balance += n; },
        withdraw: function(n) { balance -= n; },
        balance: function() { return balance; }
    };
}
var bank = makeBank();
bank.deposit(100);
bank.deposit(50);
bank.withdraw(30);
var v = bank.balance();
""")
    assert val(i) == 120


# ---------------------------------------------------------------------------
# Memoization
# ---------------------------------------------------------------------------

def test_memoization_caches_result():
    i = run("""
function memoize(compute) {
    var cache = new Map();
    return function(n) {
        if (cache.has(n)) return cache.get(n);
        var result = compute(n);
        cache.set(n, result);
        return result;
    };
}
var calls = 0;
var slow = memoize(function(x) { calls++; return x * x; });
slow(5); slow(5); slow(5);
var v = calls;
""")
    assert val(i) == 1


def test_memoization_returns_correct():
    i = run("""
function memoize(compute) {
    var cache = new Map();
    return function(n) {
        if (cache.has(n)) return cache.get(n);
        var result = compute(n);
        cache.set(n, result);
        return result;
    };
}
var square = memoize(function(x) { return x * x; });
var v = square(7);
""")
    assert val(i) == 49


# ---------------------------------------------------------------------------
# Partial application via closure
# ---------------------------------------------------------------------------

def test_partial_via_closure():
    i = run("""
function partial(f, a) {
    return function(b) { return f(a, b); };
}
function add(x, y) { return x + y; }
var add5 = partial(add, 5);
var v = add5(3);
""")
    assert val(i) == 8


def test_partial_via_bind():
    i = run("""
function multiply(a, b) { return a * b; }
var double = multiply.bind(null, 2);
var v = double(7);
""")
    assert val(i) == 14


# ---------------------------------------------------------------------------
# var vs let scoping
# ---------------------------------------------------------------------------

def test_var_function_scoped():
    """var declared inside a function is accessible throughout that function."""
    i = run("""
function test() {
    var x = 10;
    if (true) { x = 20; }
    return x;
}
var v = test();
""")
    assert val(i) == 20


def test_let_block_scoped():
    i = run("""
var v = 0;
{
    let x = 10;
    v = x;
}
""")
    assert val(i) == 10


def test_var_hoisted():
    """var in a function is accessible after the assignment in the same scope."""
    i = run("""
function f() {
    var result = 0;
    for (var i = 0; i < 3; i++) { result = i; }
    return result;
}
var v = f();
""")
    assert val(i) == 2


# ---------------------------------------------------------------------------
# Nested function scope
# ---------------------------------------------------------------------------

def test_nested_function_scope():
    i = run("""
function outer() {
    var x = 10;
    function middle() {
        var y = 20;
        function inner() {
            return x + y;
        }
        return inner();
    }
    return middle();
}
var v = outer();
""")
    assert val(i) == 30


def test_nested_shadows_outer():
    i = run("""
var x = 1;
function outer() {
    var x = 2;
    function inner() {
        var x = 3;
        return x;
    }
    return inner();
}
var v = outer();
""")
    assert val(i) == 3


def test_closure_returns_different_values():
    i = run("""
function makeGetter(value) {
    return function() { return value; };
}
var getA = makeGetter(\"a\");
var getB = makeGetter(\"b\");
var v = getA() + getB();
""")
    assert val(i) == "ab"


# ---------------------------------------------------------------------------
# Arrow functions and closures
# ---------------------------------------------------------------------------

def test_arrow_closes_over_outer():
    i = run("""
function outer() {
    var msg = \"hello\";
    return () => msg;
}
var v = outer()();
""")
    assert val(i) == "hello"


def test_arrow_in_array_map():
    i = run("""
var base = 10;
var arr = [1, 2, 3];
var v = arr.map(x => x + base);
""")
    assert val(i) == [11, 12, 13]


def test_closure_in_map():
    i = run("""
function addN(n) {
    return function(x) { return x + n; };
}
var add5 = addN(5);
var v = [1,2,3].map(add5);
""")
    assert val(i) == [6, 7, 8]


def test_recursive_closure():
    i = run("""
function makeFactorial() {
    function fact(n) {
        if (n <= 1) return 1;
        return n * fact(n - 1);
    }
    return fact;
}
var factorial = makeFactorial();
var v = factorial(5);
""")
    assert val(i) == 120


def test_closure_over_params():
    i = run("""
function greet(greeting) {
    return function(name) {
        return greeting + \" \" + name;
    };
}
var hello = greet(\"Hello\");
var v = hello(\"World\");
""")
    assert val(i) == "Hello World"
