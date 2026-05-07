"""Tests for Phase 86: Advanced Control Flow."""
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


# ---------------------------------------------------------------------------
# Labeled break
# ---------------------------------------------------------------------------

def test_labeled_break_outer():
    i = run("""
var v = 0;
outer: for (var i = 0; i < 3; i++) {
    for (var j = 0; j < 3; j++) {
        if (j === 1) break outer;
        v++;
    }
}
""")
    assert val(i) == 1


def test_labeled_break_stops_both_loops():
    i = run("""
var v = 0;
loop: for (var i = 0; i < 5; i++) {
    for (var j = 0; j < 5; j++) {
        if (i === 2 && j === 1) break loop;
        v++;
    }
}
""")
    assert val(i) == 11  # 5 + 5 + 1


def test_labeled_break_inner_vs_outer():
    i = run("""
var v = 0;
outer: for (var i = 0; i < 3; i++) {
    for (var j = 0; j < 3; j++) {
        if (j === 2) break;
        v++;
    }
}
""")
    assert val(i) == 6  # inner break: each i-loop gets 2 iterations


def test_labeled_break_with_while():
    i = run("""
var v = 0;
var i = 0;
done: while (i < 3) {
    var j = 0;
    while (j < 3) {
        if (j === 1) break done;
        v++;
        j++;
    }
    i++;
}
""")
    assert val(i) == 1


# ---------------------------------------------------------------------------
# Labeled continue
# ---------------------------------------------------------------------------

def test_labeled_continue():
    i = run("""
var v = 0;
outer: for (var i = 0; i < 3; i++) {
    for (var j = 0; j < 3; j++) {
        if (j === 1) continue outer;
        v++;
    }
}
""")
    assert val(i) == 3


def test_labeled_continue_skips_inner():
    i = run("""
var v = 0;
outer: for (var i = 0; i < 2; i++) {
    for (var j = 0; j < 3; j++) {
        if (j === 0) continue outer;
        v++;
    }
}
""")
    assert val(i) == 0  # always continues outer before incrementing v


def test_labeled_continue_vs_break():
    i = run("""
var outer_count = 0;
outer: for (var i = 0; i < 3; i++) {
    outer_count++;
    for (var j = 0; j < 3; j++) {
        if (j === 1) continue outer;
    }
}
var v = outer_count;
""")
    assert val(i) == 3  # outer loop still runs 3 times


# ---------------------------------------------------------------------------
# do...while
# ---------------------------------------------------------------------------

def test_do_while_basic():
    i = run("""
var v = 0;
do { v++; } while (v < 3);
""")
    assert val(i) == 3


def test_do_while_runs_at_least_once():
    i = run("""
var v = 0;
do { v++; } while (false);
""")
    assert val(i) == 1


def test_do_while_runs_once_false_cond():
    i = run("""
var v = 10;
do { v++; } while (v < 10);
""")
    assert val(i) == 11


def test_do_while_with_break():
    i = run("""
var v = 0;
do {
    v++;
    if (v === 2) break;
} while (v < 5);
""")
    assert val(i) == 2


def test_do_while_accumulate():
    i = run("""
var v = 0;
var i = 1;
do {
    v += i;
    i++;
} while (i <= 5);
""")
    assert val(i) == 15


def test_do_while_nested():
    i = run("""
var v = 0;
var i = 0;
do {
    var j = 0;
    do {
        v++;
        j++;
    } while (j < 2);
    i++;
} while (i < 3);
""")
    assert val(i) == 6


# ---------------------------------------------------------------------------
# for...of with break/continue
# ---------------------------------------------------------------------------

def test_for_of_break():
    i = run("""
var arr = [1, 2, 3, 4, 5];
var v = 0;
for (var x of arr) {
    if (x === 3) break;
    v += x;
}
""")
    assert val(i) == 3  # 1 + 2


def test_for_of_continue():
    i = run("""
var arr = [1, 2, 3, 4, 5];
var v = 0;
for (var x of arr) {
    if (x === 3) continue;
    v += x;
}
""")
    assert val(i) == 12  # 1+2+4+5


def test_for_of_complete():
    i = run("""
var v = 0;
for (var x of [1, 2, 3]) { v += x; }
""")
    assert val(i) == 6


def test_for_of_string():
    i = run("""
var v = '';
for (var c of 'abc') { v += c; }
""")
    assert val(i) == "abc"


def test_for_of_break_first():
    i = run("""
var v = 0;
for (var x of [10, 20, 30]) {
    v = x;
    break;
}
""")
    assert val(i) == 10


# ---------------------------------------------------------------------------
# for...in with break/continue
# ---------------------------------------------------------------------------

def test_for_in_break():
    i = run("""
var obj = {a: 1, b: 2, c: 3};
var v = 0;
for (var k in obj) {
    v++;
    if (v === 2) break;
}
""")
    assert val(i) == 2


def test_for_in_continue():
    i = run("""
var obj = {a: 1, b: 2, c: 3};
var v = 0;
for (var k in obj) {
    if (k === 'b') continue;
    v += obj[k];
}
""")
    assert val(i) == 4  # a + c


def test_for_in_all_keys():
    i = run("""
var obj = {x: 10, y: 20, z: 30};
var v = 0;
for (var k in obj) { v += obj[k]; }
""")
    assert val(i) == 60


# ---------------------------------------------------------------------------
# Switch with return
# ---------------------------------------------------------------------------

def test_switch_with_return():
    i = run("""
function classify(n) {
    switch (n) {
        case 1: return 'one';
        case 2: return 'two';
        default: return 'other';
    }
}
var v = classify(2);
""")
    assert val(i) == "two"


def test_switch_default_return():
    i = run("""
function classify(n) {
    switch (n) {
        case 1: return 'one';
        default: return 'default';
    }
}
var v = classify(99);
""")
    assert val(i) == "default"


def test_switch_fallthrough():
    i = run("""
function test(n) {
    var result = '';
    switch (n) {
        case 1:
        case 2:
            result = 'small';
            break;
        default:
            result = 'big';
    }
    return result;
}
var v = test(1);
""")
    assert val(i) == "small"


# ---------------------------------------------------------------------------
# try/finally with return
# ---------------------------------------------------------------------------

def test_try_finally_return():
    i = run("""
function f() {
    try { return 1; } finally { return 2; }
}
var v = f();
""")
    assert val(i) == 2


def test_try_finally_no_exception():
    i = run("""
var cleanup = 0;
function f() {
    try { return 10; }
    finally { cleanup = 1; }
}
var r = f();
var v = r + cleanup;
""")
    assert val(i) == 11


def test_try_finally_with_exception():
    i = run("""
var cleaned = false;
function f() {
    try {
        throw new Error('oops');
    } catch (e) {
        return 1;
    } finally {
        cleaned = true;
    }
}
var r = f();
var v = cleaned;
""")
    assert val(i) == True


# ---------------------------------------------------------------------------
# Nested try/catch/finally
# ---------------------------------------------------------------------------

def test_nested_try_catch_finally():
    i = run("""
var v = 0;
try {
    try {
        throw new Error('inner');
    } catch (e) {
        v = 1;
    } finally {
        v += 10;
    }
} catch (e) {
    v = 99;
}
""")
    assert val(i) == 11


def test_nested_try_rethrow():
    i = run("""
var v = 0;
try {
    try {
        throw new Error('inner');
    } catch (e) {
        v = 1;
        throw e;
    }
} catch (e) {
    v += 100;
}
""")
    assert val(i) == 101


def test_nested_try_finally_order():
    i = run("""
var log = [];
function f() {
    try {
        try {
            throw new Error('err');
        } finally {
            log.push('inner-finally');
        }
    } catch (e) {
        log.push('outer-catch');
    } finally {
        log.push('outer-finally');
    }
}
f();
var v = log.length;
""")
    assert val(i) == 3


# ---------------------------------------------------------------------------
# Generator with try/finally
# ---------------------------------------------------------------------------

def test_generator_finally_on_return():
    i = run("""
function* gen() {
    try {
        yield 1;
        yield 2;
    } finally {
        // cleanup
    }
}
var g = gen();
var a = g.next().value;
var b = g.return(99);
var v = b.value;
""")
    assert val(i) == 99


def test_generator_basic_yield():
    i = run("""
function* range(n) {
    for (var i = 0; i < n; i++) { yield i; }
}
var g = range(3);
var a = g.next().value;
var b = g.next().value;
var v = a + b;
""")
    assert val(i) == 1  # 0 + 1


def test_generator_done_property():
    i = run("""
function* once() { yield 1; }
var g = once();
g.next();
var v = g.next().done;
""")
    assert val(i) == True


# ---------------------------------------------------------------------------
# Ternary chaining
# ---------------------------------------------------------------------------

def test_ternary_chain():
    i = run("var x = 2; var v = x === 1 ? 'one' : x === 2 ? 'two' : 'other';")
    assert val(i) == "two"


def test_ternary_chain_last():
    i = run("var x = 5; var v = x === 1 ? 'one' : x === 2 ? 'two' : 'other';")
    assert val(i) == "other"


def test_ternary_chain_first():
    i = run("var x = 1; var v = x === 1 ? 'a' : x === 2 ? 'b' : 'c';")
    assert val(i) == "a"


def test_ternary_nested():
    i = run("""
function grade(n) {
    return n >= 90 ? 'A' : n >= 80 ? 'B' : n >= 70 ? 'C' : 'F';
}
var v = grade(85);
""")
    assert val(i) == "B"


def test_ternary_in_expression():
    i = run("var v = (true ? 10 : 20) + (false ? 1 : 2);")
    assert val(i) == 12


# ---------------------------------------------------------------------------
# Short-circuit evaluation
# ---------------------------------------------------------------------------

def test_and_all_true():
    i = run("var v = true && true && true;")
    assert val(i) == True


def test_and_short_circuits():
    i = run("var v = true && true && false;")
    assert val(i) == False


def test_and_returns_value():
    i = run("var v = 1 && 2 && 3;")
    assert val(i) == 3


def test_and_short_circuit_falsy():
    i = run("var v = 1 && 0 && 3;")
    assert val(i) == 0


def test_or_all_false():
    i = run("var v = false || false || false;")
    assert val(i) == False


def test_or_short_circuits():
    i = run("var v = false || false || 42;")
    assert val(i) == 42


def test_or_returns_first_truthy():
    i = run("var v = null || undefined || 'hello';")
    assert val(i) == "hello"


def test_and_side_effects():
    i = run("""
var x = 0;
function inc() { x++; return true; }
false && inc();
var v = x;
""")
    assert val(i) == 0  # inc not called due to short-circuit


def test_or_side_effects():
    i = run("""
var x = 0;
function inc() { x++; return true; }
true || inc();
var v = x;
""")
    assert val(i) == 0  # inc not called due to short-circuit


# ---------------------------------------------------------------------------
# Nullish coalescing
# ---------------------------------------------------------------------------

def test_nullish_chain():
    i = run("var a = null; var b = null; var c = 5; var v = a ?? b ?? c;")
    assert val(i) == 5


def test_nullish_first_not_null():
    i = run("var a = 0; var b = null; var v = a ?? b;")
    assert val(i) == 0  # 0 is NOT null/undefined


def test_nullish_undefined_fallback():
    i = run("var v = undefined ?? 'default';")
    assert val(i) == "default"


def test_nullish_null_fallback():
    i = run("var v = null ?? 'fallback';")
    assert val(i) == "fallback"


def test_nullish_zero_not_nullish():
    i = run("var v = 0 ?? 99;")
    assert val(i) == 0


def test_nullish_empty_string_not_nullish():
    i = run("var v = '' ?? 'default';")
    assert val(i) == ""


# ---------------------------------------------------------------------------
# Optional chaining
# ---------------------------------------------------------------------------

def test_optional_chain_basic():
    i = run("var obj = {a: {b: {c: 42}}}; var v = obj?.a?.b?.c;")
    assert val(i) == 42


def test_optional_chain_null():
    i = run("var obj = null; var v = obj?.a?.b;")
    assert val(i) == SPRY_UNDEFINED


def test_optional_chain_stops_at_null():
    i = run("var obj = {a: null}; var v = obj?.a?.b;")
    assert val(i) == SPRY_UNDEFINED


def test_optional_chain_with_method():
    i = run("var obj = {greet: function() { return 'hi'; }}; var v = obj?.greet();")
    assert val(i) == "hi"


def test_optional_chain_undefined_method():
    i = run("var obj = null; var v = obj?.method();")
    assert val(i) == SPRY_UNDEFINED


def test_optional_chain_array():
    i = run("var arr = [1, 2, 3]; var v = arr?.[1];")
    assert val(i) == 2


def test_optional_chain_deep():
    i = run("""
var data = {user: {profile: {name: 'Alice'}}};
var v = data?.user?.profile?.name;
""")
    assert val(i) == "Alice"


def test_optional_chain_missing_key():
    i = run("""
var data = {user: null};
var v = data?.user?.name;
""")
    assert val(i) == SPRY_UNDEFINED


# ---------------------------------------------------------------------------
# Additional switch tests
# ---------------------------------------------------------------------------

def test_switch_default_runs_when_no_match():
    i = run("""
var v = 0;
switch (99) {
    case 1: v = 1; break;
    case 2: v = 2; break;
    default: v = 99;
}
""")
    assert val(i) == 99


def test_switch_breaks_correctly():
    i = run("""
var v = 0;
switch (1) {
    case 1: v = 10; break;
    case 2: v = 20; break;
}
""")
    assert val(i) == 10


def test_switch_string_cases():
    i = run("""
var v = '';
switch ('hello') {
    case 'hi': v = 'informal'; break;
    case 'hello': v = 'formal'; break;
    default: v = 'unknown';
}
""")
    assert val(i) == 'formal'


def test_switch_no_match_no_default_unchanged():
    i = run("""
var v = 42;
switch (99) {
    case 1: v = 1; break;
    case 2: v = 2; break;
}
""")
    assert val(i) == 42


# ---------------------------------------------------------------------------
# Additional do-while tests
# ---------------------------------------------------------------------------

def test_do_while_at_least_once():
    i = run("""
var v = 0;
do { v++; } while (false);
""")
    assert val(i) == 1


def test_do_while_executes_multiple():
    i = run("""
var v = 0;
do { v++; } while (v < 5);
""")
    assert val(i) == 5


def test_do_while_with_break():
    i = run("""
var v = 0;
do {
    v++;
    if (v === 3) break;
} while (v < 10);
""")
    assert val(i) == 3
