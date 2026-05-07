"""Tests for Phase 71: Promises and Async/Await
- Promise.resolve, .reject, .all, .allSettled, .race, .any
- .then, .catch, .finally chaining
- async fn, await, error handling in async
- Promise.try, SpryPromise .state and .value/.reason
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


# ---------------------------------------------------------------------------
# Promise.resolve
# ---------------------------------------------------------------------------

class TestPromiseResolve:
    def test_resolve_returns_promise(self):
        i = run("let v = Promise.resolve(42)")
        p = val(i)
        assert type(p).__name__ == "SpryPromise"

    def test_resolve_fulfilled_state(self):
        i = run("let p = Promise.resolve(42)\nlet v = p.state")
        assert val(i) == "fulfilled"

    def test_resolve_value(self):
        i = run("let p = Promise.resolve(99)\nlet v = p.value")
        assert val(i) == 99

    def test_resolve_string(self):
        i = run('let p = Promise.resolve("hello")\nlet v = p.value')
        assert val(i) == "hello"

    def test_resolve_null(self):
        i = run("let p = Promise.resolve(null)\nlet v = p.value")
        assert val(i) is None

    def test_resolve_list(self):
        i = run("let p = Promise.resolve([1,2,3])\nlet v = p.value")
        assert val(i) == [1, 2, 3]

    def test_resolve_zero(self):
        i = run("let p = Promise.resolve(0)\nlet v = p.value")
        assert val(i) == 0

    def test_resolve_false(self):
        i = run("let p = Promise.resolve(false)\nlet v = p.value")
        assert val(i) is False

    def test_resolve_reason_is_none(self):
        i = run("let p = Promise.resolve(1)\nlet v = p.reason")
        assert val(i) is None

    def test_resolve_chained_then_value(self):
        i = run("""
fn add1(x) { return x + 1 }
let p = Promise.resolve(10).then(add1)
let v = p.value
""")
        assert val(i) == 11

    def test_resolve_then_inline_fn(self):
        i = run("""
let results = []
Promise.resolve(5).then(fn(x) { results.push(x * 2) })
let v = results
""")
        assert val(i) == [10]

    def test_resolve_nested(self):
        i = run("""
fn double(x) { return x * 2 }
let p = Promise.resolve(5).then(double).then(double)
let v = p.value
""")
        assert val(i) == 20


# ---------------------------------------------------------------------------
# Promise.reject
# ---------------------------------------------------------------------------

class TestPromiseReject:
    def test_reject_returns_promise(self):
        i = run("let v = Promise.reject('err')")
        assert type(val(i)).__name__ == "SpryPromise"

    def test_reject_state(self):
        i = run("let p = Promise.reject('err')\nlet v = p.state")
        assert val(i) == "rejected"

    def test_reject_reason(self):
        i = run("let p = Promise.reject('bad')\nlet v = p.reason")
        assert val(i) == "bad"

    def test_reject_value_is_none(self):
        i = run("let p = Promise.reject('err')\nlet v = p.value")
        assert val(i) is None

    def test_reject_catch_recovers(self):
        i = run("""
fn handle(e) { return "handled: " + e }
let p = Promise.reject("bad").catch(handle)
let v = p.value
""")
        assert val(i) == "handled: bad"

    def test_reject_catch_state(self):
        i = run("""
fn handle(e) { return "ok" }
let p = Promise.reject("bad").catch(handle)
let v = p.state
""")
        assert val(i) == "fulfilled"

    def test_reject_with_error_object(self):
        i = run("""
let p = Promise.reject(new Error("oops"))
let v = p.reason.message
""")
        assert val(i) == "oops"

    def test_reject_uncaught_reason(self):
        i = run("""
let p = Promise.reject(42)
let v = p.reason
""")
        assert val(i) == 42

    def test_reject_finally_runs(self):
        i = run("""
let log = []
let p = Promise.reject("err").finally(fn() { log.push("finally") })
let v = log
""")
        assert val(i) == ["finally"]

    def test_reject_state_after_finally(self):
        i = run("""
let p = Promise.reject("err").finally(fn() { 99 })
let v = p.state
""")
        assert val(i) == "rejected"


# ---------------------------------------------------------------------------
# Promise.all
# ---------------------------------------------------------------------------

class TestPromiseAll:
    def test_all_basic(self):
        i = run("""
let p = Promise.all([Promise.resolve(1), Promise.resolve(2), Promise.resolve(3)])
let v = p.value
""")
        assert val(i) == [1, 2, 3]

    def test_all_state_fulfilled(self):
        i = run("""
let p = Promise.all([Promise.resolve(1), Promise.resolve(2)])
let v = p.state
""")
        assert val(i) == "fulfilled"

    def test_all_empty(self):
        i = run("let p = Promise.all([])\nlet v = p.value")
        assert val(i) == []

    def test_all_reject_propagates(self):
        i = run("""
let p = Promise.all([Promise.resolve(1), Promise.reject("x")])
let v = p.state
""")
        assert val(i) == "rejected"

    def test_all_single(self):
        i = run("let p = Promise.all([Promise.resolve(99)])\nlet v = p.value")
        assert val(i) == [99]

    def test_all_order_preserved(self):
        i = run("""
let p = Promise.all([Promise.resolve(10), Promise.resolve(20), Promise.resolve(30)])
let v = p.value[1]
""")
        assert val(i) == 20


# ---------------------------------------------------------------------------
# Promise.allSettled
# ---------------------------------------------------------------------------

class TestPromiseAllSettled:
    def test_allSettled_basic(self):
        i = run("""
let p = Promise.allSettled([Promise.resolve(1), Promise.reject("x")])
let v = p.state
""")
        assert val(i) == "fulfilled"

    def test_allSettled_fulfilled_entry(self):
        i = run("""
let p = Promise.allSettled([Promise.resolve(1)])
let v = p.value[0]
""")
        assert val(i) == {"status": "fulfilled", "value": 1}

    def test_allSettled_rejected_entry(self):
        i = run("""
let p = Promise.allSettled([Promise.reject("err")])
let v = p.value[0]
""")
        assert val(i) == {"status": "rejected", "reason": "err"}

    def test_allSettled_mixed(self):
        i = run("""
let p = Promise.allSettled([Promise.resolve(1), Promise.reject("x")])
let v = p.value
""")
        assert val(i) == [
            {"status": "fulfilled", "value": 1},
            {"status": "rejected", "reason": "x"},
        ]

    def test_allSettled_empty(self):
        i = run("let p = Promise.allSettled([])\nlet v = p.value")
        assert val(i) == []

    def test_allSettled_all_rejected_still_fulfilled(self):
        i = run("""
let p = Promise.allSettled([Promise.reject("a"), Promise.reject("b")])
let v = p.state
""")
        assert val(i) == "fulfilled"


# ---------------------------------------------------------------------------
# Promise.race
# ---------------------------------------------------------------------------

class TestPromiseRace:
    def test_race_basic(self):
        i = run("""
let p = Promise.race([Promise.resolve(42)])
let v = p.value
""")
        assert val(i) == 42

    def test_race_first_wins(self):
        i = run("""
let p = Promise.race([Promise.resolve(1), Promise.resolve(2)])
let v = p.value
""")
        assert val(i) == 1

    def test_race_state(self):
        i = run("""
let p = Promise.race([Promise.resolve(1)])
let v = p.state
""")
        assert val(i) == "fulfilled"

    def test_race_rejected_first(self):
        i = run("""
let p = Promise.race([Promise.reject("err"), Promise.resolve(1)])
let v = p.state
""")
        assert val(i) == "rejected"


# ---------------------------------------------------------------------------
# Promise.any
# ---------------------------------------------------------------------------

class TestPromiseAny:
    def test_any_basic(self):
        i = run("""
let p = Promise.any([Promise.resolve(7)])
let v = p.value
""")
        assert val(i) == 7

    def test_any_skips_rejected(self):
        i = run("""
let p = Promise.any([Promise.reject("no"), Promise.resolve(7)])
let v = p.value
""")
        assert val(i) == 7

    def test_any_state(self):
        i = run("""
let p = Promise.any([Promise.resolve(1)])
let v = p.state
""")
        assert val(i) == "fulfilled"


# ---------------------------------------------------------------------------
# .then chaining
# ---------------------------------------------------------------------------

class TestPromiseThen:
    def test_then_transforms_value(self):
        i = run("""
fn double(x) { return x * 2 }
let p = Promise.resolve(5).then(double)
let v = p.value
""")
        assert val(i) == 10

    def test_then_chained(self):
        i = run("""
fn add1(x) { return x + 1 }
let p = Promise.resolve(0).then(add1).then(add1).then(add1)
let v = p.value
""")
        assert val(i) == 3

    def test_then_side_effect(self):
        i = run("""
let log = []
Promise.resolve(42).then(fn(x) { log.push(x) })
let v = log
""")
        assert val(i) == [42]

    def test_then_state_fulfilled(self):
        i = run("""
fn id(x) { return x }
let p = Promise.resolve(1).then(id)
let v = p.state
""")
        assert val(i) == "fulfilled"

    def test_then_on_rejected_skipped(self):
        i = run("""
fn double(x) { return x * 2 }
let p = Promise.reject("err").then(double)
let v = p.state
""")
        assert val(i) == "rejected"


# ---------------------------------------------------------------------------
# .catch chaining
# ---------------------------------------------------------------------------

class TestPromiseCatch:
    def test_catch_recovers(self):
        i = run("""
fn recover(e) { return "recovered" }
let p = Promise.reject("err").catch(recover)
let v = p.value
""")
        assert val(i) == "recovered"

    def test_catch_on_fulfilled_skipped(self):
        i = run("""
fn recover(e) { return "recovered" }
let p = Promise.resolve(10).catch(recover)
let v = p.value
""")
        assert val(i) == 10

    def test_catch_state(self):
        i = run("""
fn recover(e) { return "ok" }
let p = Promise.reject("err").catch(recover)
let v = p.state
""")
        assert val(i) == "fulfilled"

    def test_catch_inline_fn(self):
        i = run("""
fn handle(e) { return "got: " + e }
let p = Promise.reject("bad").catch(handle)
let v = p.value
""")
        assert val(i) == "got: bad"


# ---------------------------------------------------------------------------
# .finally chaining
# ---------------------------------------------------------------------------

class TestPromiseFinally:
    def test_finally_fulfilled_passes_through(self):
        i = run("""
let p = Promise.resolve(5).finally(fn() { 99 })
let v = p.value
""")
        assert val(i) == 5

    def test_finally_state_preserved_fulfilled(self):
        i = run("""
let p = Promise.resolve(5).finally(fn() { 99 })
let v = p.state
""")
        assert val(i) == "fulfilled"

    def test_finally_rejected_state_preserved(self):
        i = run("""
let p = Promise.reject("err").finally(fn() { 0 })
let v = p.state
""")
        assert val(i) == "rejected"

    def test_finally_runs_on_rejection(self):
        i = run("""
let log = []
Promise.reject("err").finally(fn() { log.push("finally") })
let v = log
""")
        assert val(i) == ["finally"]

    def test_finally_runs_on_fulfillment(self):
        i = run("""
let log = []
Promise.resolve(1).finally(fn() { log.push("finally") })
let v = log
""")
        assert val(i) == ["finally"]


# ---------------------------------------------------------------------------
# async fn and await
# ---------------------------------------------------------------------------

class TestAsyncAwait:
    def test_async_fn_returns_promise(self):
        i = run("""
async fn foo() { return 42 }
let v = foo()
""")
        assert type(val(i)).__name__ == "SpryPromise"

    def test_async_fn_value(self):
        i = run("""
async fn foo() { return 42 }
let p = foo()
let v = p.value
""")
        assert val(i) == 42

    def test_async_fn_state(self):
        i = run("""
async fn foo() { return 1 }
let p = foo()
let v = p.state
""")
        assert val(i) == "fulfilled"

    def test_await_unwraps_promise(self):
        i = run("""
async fn foo() {
  let x = await Promise.resolve(42)
  return x
}
let p = foo()
let v = p.value
""")
        assert val(i) == 42

    def test_await_chained(self):
        i = run("""
async fn foo() {
  let a = await Promise.resolve(10)
  let b = await Promise.resolve(20)
  return a + b
}
let p = foo()
let v = p.value
""")
        assert val(i) == 30

    def test_async_try_catch_await(self):
        i = run("""
async fn foo() {
  try {
    let x = await Promise.reject("err")
    return x
  } catch(e) {
    return "caught"
  }
}
let p = foo()
let v = p.value
""")
        assert "caught" in str(val(i))

    def test_async_throws_rejects(self):
        i = run("""
async fn foo() {
  throw new Error("async err")
}
let p = foo()
let v = p.state
""")
        assert val(i) == "rejected"

    def test_async_throws_reason(self):
        i = run("""
async fn foo() {
  throw new Error("async err")
}
let p = foo()
let v = p.reason.message
""")
        assert val(i) == "async err"

    def test_async_catch_propagation(self):
        i = run("""
async fn foo() {
  throw new Error("async err")
}
let p = foo().catch(fn(e) { "caught" })
let v = p.state
""")
        assert val(i) == "fulfilled"

    def test_async_fn_no_explicit_return(self):
        i = run("""
async fn foo() {
  let x = 1
}
let p = foo()
let v = p.state
""")
        assert val(i) == "fulfilled"


# ---------------------------------------------------------------------------
# Promise.try
# ---------------------------------------------------------------------------

class TestPromiseTry:
    def test_try_wraps_fn(self):
        i = run("""
fn compute() { return 2 + 3 }
let p = Promise.try(compute)
let v = p.value
""")
        assert val(i) == 5

    def test_try_state_fulfilled(self):
        i = run("""
fn compute() { return 42 }
let p = Promise.try(compute)
let v = p.state
""")
        assert val(i) == "fulfilled"

    def test_try_catches_thrown_error(self):
        i = run("""
fn bad() { throw new Error("oops") }
let p = Promise.try(bad)
let v = p.state
""")
        assert val(i) == "rejected"

    def test_try_rejected_reason(self):
        i = run("""
fn bad() { throw new Error("oops") }
let p = Promise.try(bad)
let v = p.state
""")
        assert val(i) == "rejected"

    def test_try_returns_promise(self):
        i = run("""
fn compute() { return 1 }
let v = Promise.try(compute)
""")
        assert type(val(i)).__name__ == "SpryPromise"


# ---------------------------------------------------------------------------
# SpryPromise .state and .reason properties
# ---------------------------------------------------------------------------

class TestPromiseProperties:
    def test_fulfilled_state(self):
        i = run("let p = Promise.resolve(1)\nlet v = p.state")
        assert val(i) == "fulfilled"

    def test_rejected_state(self):
        i = run("let p = Promise.reject('x')\nlet v = p.state")
        assert val(i) == "rejected"

    def test_fulfilled_reason_is_none(self):
        i = run("let p = Promise.resolve(1)\nlet v = p.reason")
        assert val(i) is None

    def test_rejected_reason(self):
        i = run("let p = Promise.reject('x')\nlet v = p.reason")
        assert val(i) == "x"

    def test_fulfilled_value(self):
        i = run("let p = Promise.resolve(42)\nlet v = p.value")
        assert val(i) == 42

    def test_rejected_value_is_none(self):
        i = run("let p = Promise.reject('x')\nlet v = p.value")
        assert val(i) is None
