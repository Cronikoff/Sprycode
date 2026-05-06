"""Tests for Phase 85: Functional Programming Patterns."""
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
# Function properties
# ---------------------------------------------------------------------------

def test_fn_name_named():
    i = run("function namedFunc() {} var v = namedFunc.name;")
    assert val(i) == "namedFunc"


def test_fn_length_no_params():
    i = run("function f() {} var v = f.length;")
    assert val(i) == 0


def test_fn_length_two_params():
    i = run("function f(a, b) {} var v = f.length;")
    assert val(i) == 2


def test_fn_length_three_params():
    i = run("function f(a, b, c) {} var v = f.length;")
    assert val(i) == 3


def test_fn_tostring_returns_string():
    i = run("function f() {} var v = typeof f.toString();")
    assert val(i) == "string"


def test_fn_tostring_contains_function():
    # Verify toString exists on functions and returns a string
    i = run("function myFunc() {} var v = typeof myFunc.toString();")
    assert val(i) == "string"


# ---------------------------------------------------------------------------
# Function.prototype.call
# ---------------------------------------------------------------------------

def test_call_with_this():
    i = run("""
function greet(greeting) { return greeting + ' ' + this.name; }
var obj = {name: 'World'};
var v = greet.call(obj, 'Hello');
""")
    assert val(i) == "Hello World"


def test_call_null_this():
    i = run("function add(a, b) { return a + b; } var v = add.call(null, 3, 4);")
    assert val(i) == 7


def test_call_with_context():
    i = run("""
function getN() { return this.n; }
var obj = {n: 42};
var v = getN.call(obj);
""")
    assert val(i) == 42


def test_call_multiple_args():
    i = run("""
function sum3(a, b, c) { return a + b + c; }
var v = sum3.call(null, 1, 2, 3);
""")
    assert val(i) == 6


# ---------------------------------------------------------------------------
# Function.prototype.apply
# ---------------------------------------------------------------------------

def test_apply_basic():
    i = run("function add(a, b) { return a + b; } var v = add.apply(null, [3, 4]);")
    assert val(i) == 7


def test_apply_with_context():
    i = run("""
function getN() { return this.n; }
var obj = {n: 99};
var v = getN.apply(obj, []);
""")
    assert val(i) == 99


def test_apply_sum():
    i = run("""
function sum(a, b, c) { return a + b + c; }
var args = [1, 2, 3];
var v = sum.apply(null, args);
""")
    assert val(i) == 6


def test_apply_spread_equivalent():
    i = run("""
function max(a, b) { return a > b ? a : b; }
var nums = [10, 20];
var v = max.apply(null, nums);
""")
    assert val(i) == 20


# ---------------------------------------------------------------------------
# Function.prototype.bind
# ---------------------------------------------------------------------------

def test_bind_partial_application():
    i = run("function add(a, b) { return a + b; } var add5 = add.bind(null, 5); var v = add5(3);")
    assert val(i) == 8


def test_bind_this_context():
    i = run("""
function getN() { return this.n; }
var obj = {n: 77};
var bound = getN.bind(obj);
var v = bound();
""")
    assert val(i) == 77


def test_bind_multiple_prebound_args():
    i = run("""
function sum3(a, b, c) { return a + b + c; }
var add10 = sum3.bind(null, 5, 5);
var v = add10(10);
""")
    assert val(i) == 20


def test_bind_creates_new_function():
    i = run("""
function double(x) { return x * 2; }
var bound = double.bind(null);
var v = typeof bound;
""")
    assert val(i) == "function"


# ---------------------------------------------------------------------------
# Currying
# ---------------------------------------------------------------------------

def test_curry_two_args():
    i = run("""
function curry(f) {
    return function(a) {
        return function(b) { return f(a, b); };
    };
}
function add(x, y) { return x + y; }
var v = curry(add)(2)(3);
""")
    assert val(i) == 5


def test_curry_multiply():
    i = run("""
function curry(f) {
    return function(a) {
        return function(b) { return f(a, b); };
    };
}
function multiply(x, y) { return x * y; }
var v = curry(multiply)(3)(4);
""")
    assert val(i) == 12


def test_curry_creates_specializations():
    i = run("""
function curry(f) {
    return function(a) {
        return function(b) { return f(a, b); };
    };
}
function power(base, exp) { return Math.pow(base, exp); }
var square = curry(power)(2);
var v = square(10);
""")
    assert val(i) == 1024


# ---------------------------------------------------------------------------
# Function composition
# ---------------------------------------------------------------------------

def test_compose_two_functions():
    i = run("""
var double = function(x) { return x * 2; };
var inc = function(x) { return x + 1; };
var compose = function(f, g) { return function(x) { return f(g(x)); }; };
var v = compose(double, inc)(4);
""")
    assert val(i) == 10  # double(inc(4)) = double(5) = 10


def test_compose_arrow():
    i = run("""
var double = x => x * 2;
var inc = x => x + 1;
var compose = (f, g) => x => f(g(x));
var v = compose(double, inc)(4);
""")
    assert val(i) == 10


def test_compose_three():
    i = run("""
var inc = x => x + 1;
var double = x => x * 2;
var negate = x => -x;
function compose2(f, g) { return x => f(g(x)); }
var v = compose2(negate, compose2(double, inc))(3);
""")
    assert val(i) == -8  # negate(double(inc(3))) = negate(double(4)) = negate(8) = -8


# ---------------------------------------------------------------------------
# Pipe pattern
# ---------------------------------------------------------------------------

def test_pipe_two_functions():
    i = run("""
var double = x => x * 2;
var inc = x => x + 1;
var pipe = (f, g) => x => g(f(x));
var v = pipe(double, inc)(4);
""")
    assert val(i) == 9  # inc(double(4)) = inc(8) = 9


def test_pipe_order():
    i = run("""
function pipe(f, g) { return function(x) { return g(f(x)); }; }
var addTen = x => x + 10;
var halve = x => x / 2;
var v = pipe(addTen, halve)(6);
""")
    assert val(i) == 8  # halve(addTen(6)) = halve(16) = 8


# ---------------------------------------------------------------------------
# Higher-order functions
# ---------------------------------------------------------------------------

def test_higher_order_apply():
    i = run("""
function applyTwice(f, x) { return f(f(x)); }
function inc(x) { return x + 1; }
var v = applyTwice(inc, 5);
""")
    assert val(i) == 7


def test_higher_order_map():
    i = run("""
var double = x => x * 2;
var v = [1, 2, 3].map(double);
""")
    assert val(i) == [2, 4, 6]


def test_higher_order_filter():
    i = run("""
var isEven = x => x % 2 === 0;
var v = [1, 2, 3, 4, 5].filter(isEven);
""")
    assert val(i) == [2, 4]


def test_higher_order_reduce():
    i = run("""
var add = (acc, x) => acc + x;
var v = [1, 2, 3, 4, 5].reduce(add, 0);
""")
    assert val(i) == 15


def test_higher_order_compose_map():
    i = run("""
var inc = x => x + 1;
var double = x => x * 2;
var v = [1, 2, 3].map(inc).map(double);
""")
    assert val(i) == [4, 6, 8]


# ---------------------------------------------------------------------------
# Memoization
# ---------------------------------------------------------------------------

def test_memoize_with_map():
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
var v = square(5);
""")
    assert val(i) == 25


def test_memoize_caches_calls():
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
var callCount = 0;
var sq = memoize(function(x) { callCount++; return x * x; });
sq(4); sq(4); sq(5); sq(4);
var v = callCount;
""")
    assert val(i) == 2  # called once for 4, once for 5


def test_memoize_fibonacci():
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
var fib = memoize(function(n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
});
var v = fib(10);
""")
    assert val(i) == 55


# ---------------------------------------------------------------------------
# Once (run only once)
# ---------------------------------------------------------------------------

def test_once_runs_once():
    i = run("""
function once(f) {
    var called = false;
    var result;
    return function() {
        if (!called) { called = true; result = f(); }
        return result;
    };
}
var callCount = 0;
var wrapped = once(function() { callCount++; return 42; });
wrapped(); wrapped(); wrapped();
var v = callCount;
""")
    assert val(i) == 1


def test_once_returns_first_value():
    i = run("""
function once(f) {
    var called = false;
    var result;
    return function() {
        if (!called) { called = true; result = f(); }
        return result;
    };
}
var n = 0;
var wrapped = once(function() { n++; return n; });
var r1 = wrapped();
var r2 = wrapped();
var v = r1 + r2;
""")
    assert val(i) == 2  # both return 1


# ---------------------------------------------------------------------------
# Partial application
# ---------------------------------------------------------------------------

def test_partial_closure():
    i = run("""
function partial(f, a) {
    return function(b) { return f(a, b); };
}
function add(x, y) { return x + y; }
var add10 = partial(add, 10);
var v = add10(5);
""")
    assert val(i) == 15


def test_partial_bind():
    i = run("""
function multiply(a, b) { return a * b; }
var triple = multiply.bind(null, 3);
var v = triple(7);
""")
    assert val(i) == 21


# ---------------------------------------------------------------------------
# Throttle/debounce stubs
# ---------------------------------------------------------------------------

def test_throttle_stub():
    i = run("""
function throttle(f, delay) {
    return function() { return f(); };
}
var count = 0;
var throttled = throttle(function() { count++; }, 100);
throttled(); throttled();
var v = count;
""")
    assert val(i) == 2  # stub always calls through


def test_debounce_stub():
    i = run("""
function debounce(f, delay) {
    return function() { return f(); };
}
var count = 0;
var debounced = debounce(function() { count++; }, 100);
debounced();
var v = count;
""")
    assert val(i) == 1


# ---------------------------------------------------------------------------
# Point-free style
# ---------------------------------------------------------------------------

def test_pointfree_map():
    i = run("""
var times2 = x => x * 2;
var v = [1, 2, 3, 4].map(times2);
""")
    assert val(i) == [2, 4, 6, 8]


def test_pointfree_filter_reduce():
    i = run("""
var isOdd = x => x % 2 !== 0;
var add = (a, b) => a + b;
var v = [1, 2, 3, 4, 5].filter(isOdd).reduce(add, 0);
""")
    assert val(i) == 9  # 1+3+5


def test_pointfree_chained():
    i = run("""
var inc = x => x + 1;
var isEven = x => x % 2 === 0;
var v = [1, 2, 3, 4, 5].map(inc).filter(isEven);
""")
    assert val(i) == [2, 4, 6]


# ---------------------------------------------------------------------------
# Recursive functional patterns
# ---------------------------------------------------------------------------

def test_fold_left():
    i = run("""
function foldLeft(f, init, arr) {
    var acc = init;
    for (var x of arr) { acc = f(acc, x); }
    return acc;
}
var v = foldLeft((a, b) => a + b, 0, [1, 2, 3, 4, 5]);
""")
    assert val(i) == 15


def test_map_recursive():
    i = run("""
function myMap(f, arr) {
    if (arr.length === 0) return [];
    return [f(arr[0])].concat(myMap(f, arr.slice(1)));
}
var v = myMap(x => x * x, [1, 2, 3]);
""")
    assert val(i) == [1, 4, 9]
