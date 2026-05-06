"""Tests for Phase 98: Async/Await Advanced"""
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


# ── Async function returns a resolved Promise ─────────────────────────────────

class TestAsyncFunction:
    def test_async_returns_promise(self):
        i = run("async function f() { return 1; } let p = f(); let v = typeof p;")
        assert val(i) == "object"

    def test_async_value_accessible(self):
        i = run("async function f() { return 42; } let p = f(); let v = p.value;")
        assert val(i) == 42

    def test_async_string_return(self):
        i = run("async function f() { return \"hello\"; } let v = f().value;")
        assert val(i) == "hello"

    def test_async_math_return(self):
        i = run("async function add(a, b) { return a + b; } let v = add(3, 4).value;")
        assert val(i) == 7

    def test_async_boolean_return(self):
        i = run("async function f() { return true; } let v = f().value;")
        assert val(i) is True

    def test_async_null_return(self):
        i = run("async function f() { return null; } let v = f().value;")
        assert val(i) is None

    def test_async_implicit_return_undefined(self):
        i = run("async function f() {} let v = f().value;")
        assert val(i) is None

    def test_async_array_return(self):
        i = run("async function f() { return [1, 2, 3]; } let v = f().value;")
        assert val(i) == [1, 2, 3]

    def test_async_object_return(self):
        i = run("async function f() { return {x: 10}; } let v = f().value.x;")
        assert val(i) == 10

    def test_async_named_function(self):
        i = run("async function myFunc() { return 99; } let v = myFunc.name;")
        assert val(i) == "myFunc"


# ── await resolves a Promise ───────────────────────────────────────────────────

class TestAwaitResolvesPromise:
    def test_await_basic(self):
        i = run("""
async function f() {
  let x = await Promise.resolve(10);
  return x;
}
let v = f().value;
""")
        assert val(i) == 10

    def test_await_addition(self):
        i = run("""
async function f() {
  let x = await Promise.resolve(5);
  return x + 3;
}
let v = f().value;
""")
        assert val(i) == 8

    def test_await_string(self):
        i = run("""
async function f() {
  let s = await Promise.resolve(\"world\");
  return \"hello \" + s;
}
let v = f().value;
""")
        assert val(i) == "hello world"

    def test_await_multiplied(self):
        i = run("""
async function f() {
  let x = await Promise.resolve(6);
  return x * x;
}
let v = f().value;
""")
        assert val(i) == 36


# ── await on non-promise ───────────────────────────────────────────────────────

class TestAwaitNonPromise:
    def test_await_number(self):
        i = run("""
async function f() { let v = await 42; return v; }
let v = f().value;
""")
        assert val(i) == 42

    def test_await_string(self):
        i = run("""
async function f() { let v = await \"hi\"; return v; }
let v = f().value;
""")
        assert val(i) == "hi"

    def test_await_true(self):
        i = run("""
async function f() { let v = await true; return v; }
let v = f().value;
""")
        assert val(i) is True

    def test_await_object(self):
        i = run("""
async function f() { let obj = await {a: 1}; return obj.a; }
let v = f().value;
""")
        assert val(i) == 1

    def test_await_null(self):
        i = run("""
async function f() { let v = await null; return v; }
let v = f().value;
""")
        assert val(i) is None


# ── Async function returning another async ────────────────────────────────────

class TestAsyncReturningAsync:
    def test_async_returns_async(self):
        i = run("""
async function inner() { return 5; }
async function outer() { return inner(); }
let v = outer().value;
""")
        assert val(i) == 5

    def test_async_awaits_async(self):
        i = run("""
async function getVal() { return 7; }
async function compute() {
  let x = await getVal();
  return x * 3;
}
let v = compute().value;
""")
        assert val(i) == 21

    def test_chained_async(self):
        i = run("""
async function a() { return 1; }
async function b() { return await a() + 2; }
async function c() { return await b() + 3; }
let v = c().value;
""")
        assert val(i) == 6


# ── Promise.resolve ────────────────────────────────────────────────────────────

class TestPromiseResolve:
    def test_resolve_number(self):
        i = run("let v = Promise.resolve(42).value;")
        assert val(i) == 42

    def test_resolve_string(self):
        i = run("let v = Promise.resolve(\"ok\").value;")
        assert val(i) == "ok"

    def test_resolve_null(self):
        i = run("let v = Promise.resolve(null).value;")
        assert val(i) is None

    def test_resolve_array(self):
        i = run("let v = Promise.resolve([1,2,3]).value;")
        assert val(i) == [1, 2, 3]

    def test_resolve_object(self):
        i = run("let v = Promise.resolve({x: 5}).value.x;")
        assert val(i) == 5

    def test_resolve_is_promise_like(self):
        i = run("let p = Promise.resolve(1); let v = typeof p;")
        assert val(i) == "object"


# ── Promise.reject ─────────────────────────────────────────────────────────────

class TestPromiseReject:
    def test_reject_string(self):
        i = run("let v = Promise.reject(\"fail\").error;")
        assert val(i) == "fail"

    def test_reject_number(self):
        i = run("let v = Promise.reject(404).error;")
        assert val(i) == 404

    def test_reject_not_settled_true(self):
        i = run("let p = Promise.reject(\"e\"); let v = p.error !== null;")
        assert val(i) is True

    def test_reject_caught_by_catch(self):
        i = run("let v = Promise.reject(\"err\").catch(e => \"got:\" + e).value;")
        assert val(i) == "got:err"


# ── Promise.all ────────────────────────────────────────────────────────────────

class TestPromiseAll:
    def test_all_basic(self):
        i = run("""
let v = Promise.all([Promise.resolve(1), Promise.resolve(2), Promise.resolve(3)]).value;
""")
        assert val(i) == [1, 2, 3]

    def test_all_single(self):
        i = run("let v = Promise.all([Promise.resolve(42)]).value;")
        assert val(i) == [42]

    def test_all_empty(self):
        i = run("let v = Promise.all([]).value;")
        assert val(i) == []

    def test_all_mixed_values(self):
        i = run("let v = Promise.all([Promise.resolve(\"a\"), Promise.resolve(\"b\")]).value;")
        assert val(i) == ["a", "b"]

    def test_all_length(self):
        i = run("let v = Promise.all([Promise.resolve(1), Promise.resolve(2)]).value.length;")
        assert val(i) == 2


# ── Promise.allSettled ─────────────────────────────────────────────────────────

class TestPromiseAllSettled:
    def test_allsettled_all_fulfilled(self):
        i = run("""
let r = Promise.allSettled([Promise.resolve(1), Promise.resolve(2)]).value;
let v = r[0].status;
""")
        assert val(i) == "fulfilled"

    def test_allsettled_mixed(self):
        i = run("""
let r = Promise.allSettled([Promise.resolve(1), Promise.reject(\"e\")]).value;
let v = r.length;
""")
        assert val(i) == 2

    def test_allsettled_rejected_status(self):
        i = run("""
let r = Promise.allSettled([Promise.resolve(1), Promise.reject(\"e\")]).value;
let v = r[1].status;
""")
        assert val(i) == "rejected"

    def test_allsettled_fulfilled_value(self):
        i = run("""
let r = Promise.allSettled([Promise.resolve(42)]).value;
let v = r[0].value;
""")
        assert val(i) == 42

    def test_allsettled_rejected_reason(self):
        i = run("""
let r = Promise.allSettled([Promise.reject(\"oops\")]).value;
let v = r[0].reason;
""")
        assert val(i) == "oops"

    def test_allsettled_always_resolves(self):
        i = run("""
let p = Promise.allSettled([Promise.reject(\"e1\"), Promise.reject(\"e2\")]);
let v = typeof p.value;
""")
        assert val(i) == "object"


# ── Promise.race ──────────────────────────────────────────────────────────────

class TestPromiseRace:
    def test_race_first_wins(self):
        i = run("""
let v = Promise.race([Promise.resolve(1), Promise.resolve(2)]).value;
""")
        assert val(i) == 1

    def test_race_single(self):
        i = run("let v = Promise.race([Promise.resolve(99)]).value;")
        assert val(i) == 99

    def test_race_resolved_wins_over_rejected(self):
        i = run("""
let v = Promise.race([Promise.resolve(\"win\"), Promise.reject(\"lose\")]).value;
""")
        assert val(i) == "win"


# ── Promise.any ───────────────────────────────────────────────────────────────

class TestPromiseAny:
    def test_any_first_fulfillment(self):
        i = run("""
let v = Promise.any([Promise.reject(\"e\"), Promise.resolve(2), Promise.resolve(3)]).value;
""")
        assert val(i) == 2

    def test_any_single_resolved(self):
        i = run("let v = Promise.any([Promise.resolve(5)]).value;")
        assert val(i) == 5

    def test_any_skips_rejections(self):
        i = run("""
let v = Promise.any([Promise.reject(\"a\"), Promise.reject(\"b\"), Promise.resolve(42)]).value;
""")
        assert val(i) == 42


# ── Promise chaining .then().then() ──────────────────────────────────────────

class TestPromiseThenChain:
    def test_then_basic(self):
        i = run("let v = Promise.resolve(1).then(x => x + 1).value;")
        assert val(i) == 2

    def test_then_chain(self):
        i = run("let v = Promise.resolve(1).then(x => x + 1).then(x => x * 3).value;")
        assert val(i) == 6

    def test_then_triple(self):
        i = run("let v = Promise.resolve(2).then(x => x * 2).then(x => x + 1).then(x => x * x).value;")
        assert val(i) == 25

    def test_then_string(self):
        i = run("let v = Promise.resolve(\"foo\").then(s => s + \"bar\").value;")
        assert val(i) == "foobar"

    def test_then_returns_new_promise(self):
        i = run("let p = Promise.resolve(1).then(x => x); let v = typeof p;")
        assert val(i) == "object"


# ── Promise .catch() ──────────────────────────────────────────────────────────

class TestPromiseCatch:
    def test_catch_rejected(self):
        i = run("let v = Promise.reject(\"err\").catch(e => \"got:\" + e).value;")
        assert val(i) == "got:err"

    def test_catch_not_called_on_resolve(self):
        i = run("let v = Promise.resolve(5).catch(e => 99).value;")
        assert val(i) == 5

    def test_catch_transforms_value(self):
        i = run("let v = Promise.reject(\"bad\").catch(e => 0).value;")
        assert val(i) == 0

    def test_catch_chained_then(self):
        i = run("let v = Promise.reject(\"e\").catch(e => 1).then(x => x + 9).value;")
        assert val(i) == 10


# ── Promise .finally() ────────────────────────────────────────────────────────

class TestPromiseFinally:
    def test_finally_runs_on_resolve(self):
        i = run("""
let v = 0;
Promise.resolve(1).finally(() => { v = 99; });
""")
        assert val(i) == 99

    def test_finally_preserves_value(self):
        i = run("let v = Promise.resolve(5).finally(() => null).value;")
        assert val(i) == 5

    def test_finally_after_then(self):
        i = run("""
let log = 0;
let p = Promise.resolve(2).then(x => x * 3).finally(() => { log = 1; });
let v = log;
""")
        assert val(i) == 1

    def test_finally_always_runs(self):
        i = run("""
let flag = false;
Promise.resolve(10).finally(() => { flag = true; });
let v = flag;
""")
        assert val(i) is True


# ── Async error handling with try/catch ───────────────────────────────────────

class TestAsyncErrorHandling:
    def test_async_try_catch_throws(self):
        i = run("""
async function test() {
  try {
    throw \"oops\";
  } catch(e) {
    return \"caught\";
  }
}
let v = test().value;
""")
        assert val(i) == "caught"

    def test_async_await_rejected_caught(self):
        i = run("""
async function test() {
  try {
    let x = await Promise.reject(\"fail\");
    return \"no\";
  } catch(e) {
    return \"caught\";
  }
}
let v = test().value;
""")
        assert val(i) == "caught"

    def test_async_error_propagates_to_promise(self):
        i = run("""
async function failFn() { throw \"oops\"; }
let p = failFn();
let v = p.error;
""")
        assert val(i) == "oops"

    def test_async_catch_recovers(self):
        i = run("""
async function mayFail() { throw \"err\"; }
async function safe() {
  try { await mayFail(); return \"ok\"; }
  catch(e) { return \"recovered\"; }
}
let v = safe().value;
""")
        assert val(i) == "recovered"


# ── Sequential await calls ────────────────────────────────────────────────────

class TestSequentialAwait:
    def test_two_awaits(self):
        i = run("""
async function f() {
  let a = await Promise.resolve(3);
  let b = await Promise.resolve(4);
  return a + b;
}
let v = f().value;
""")
        assert val(i) == 7

    def test_three_awaits(self):
        i = run("""
async function f() {
  let a = await Promise.resolve(1);
  let b = await Promise.resolve(2);
  let c = await Promise.resolve(3);
  return a + b + c;
}
let v = f().value;
""")
        assert val(i) == 6

    def test_dependent_awaits(self):
        i = run("""
async function double(x) { return x * 2; }
async function f() {
  let a = await double(5);
  let b = await double(a);
  return b;
}
let v = f().value;
""")
        assert val(i) == 20

    def test_await_in_loop(self):
        i = run("""
async function f() {
  let sum = 0;
  let i = 0;
  while (i < 3) {
    let x = await Promise.resolve(i);
    sum = sum + x;
    i++;
  }
  return sum;
}
let v = f().value;
""")
        assert val(i) == 3
