"""Tests for Phase 73: Generators
- fn* gen() { yield val } - basic generator
- Generator .next() returns {value, done}
- Generator .return(val) - early return
- Generator .throw(err) - inject error
- yield* delegate to another iterable
- for...of on generator
- Spread [...generator()]
- Destructuring generator
- Infinite generators with early termination
- async fn* gen() - async generators
- for await...of async generator
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
# Basic generator
# ---------------------------------------------------------------------------

class TestBasicGenerator:
    def test_generator_fn_star(self):
        i = run("fn* gen() { yield 1 }\nlet v = gen()")
        assert type(val(i)).__name__ == "SpryGenerator"

    def test_next_value(self):
        i = run("fn* gen() { yield 42 }\nlet g = gen()\nlet v = g.next()")
        assert val(i) == {"value": 42, "done": False}

    def test_next_done_false(self):
        i = run("fn* gen() { yield 1 }\nlet g = gen()\nlet v = g.next().done")
        assert val(i) is False

    def test_next_value_field(self):
        i = run("fn* gen() { yield 99 }\nlet g = gen()\nlet v = g.next().value")
        assert val(i) == 99

    def test_multiple_yields(self):
        i = run("""
fn* gen() {
  yield 1
  yield 2
  yield 3
}
let g = gen()
let a = g.next().value
let b = g.next().value
let c = g.next().value
let v = [a, b, c]
""")
        assert val(i) == [1, 2, 3]

    def test_done_after_exhausted(self):
        i = run("""
fn* gen() { yield 1 }
let g = gen()
g.next()
let v = g.next()
""")
        assert val(i) == {"value": None, "done": True}

    def test_done_true_after_exhausted(self):
        i = run("""
fn* gen() { yield 1 }
let g = gen()
g.next()
let v = g.next().done
""")
        assert val(i) is True

    def test_value_undefined_after_done(self):
        i = run("""
fn* gen() { yield 1 }
let g = gen()
g.next()
g.next()
let v = g.next().value
""")
        assert val(i) is None

    def test_generator_with_computation(self):
        i = run("""
fn* squares() {
  yield 1 * 1
  yield 2 * 2
  yield 3 * 3
}
let v = []
let g = squares()
v.push(g.next().value)
v.push(g.next().value)
v.push(g.next().value)
""")
        assert val(i) == [1, 4, 9]

    def test_generator_no_yield(self):
        i = run("""
fn* gen() {
  let x = 1
}
let g = gen()
let v = g.next()
""")
        assert val(i)["done"] is True

    def test_generator_with_return(self):
        i = run("""
fn* gen() {
  yield 1
  return 99
}
let g = gen()
g.next()
let v = g.next()
""")
        assert val(i) == {"value": 99, "done": True}


# ---------------------------------------------------------------------------
# Generator .return()
# ---------------------------------------------------------------------------

class TestGeneratorReturn:
    def test_return_stops_generator(self):
        i = run("""
fn* gen() { yield 1; yield 2; yield 3 }
let g = gen()
g.next()
let v = g.return(99)
""")
        assert val(i) == {"value": 99, "done": True}

    def test_return_done_true(self):
        i = run("""
fn* gen() { yield 1 }
let g = gen()
let v = g.return(0).done
""")
        assert val(i) is True

    def test_return_value(self):
        i = run("""
fn* gen() { yield 1; yield 2 }
let g = gen()
g.next()
let v = g.return(42).value
""")
        assert val(i) == 42

    def test_return_before_start(self):
        i = run("""
fn* gen() { yield 1; yield 2 }
let g = gen()
let v = g.return("early").value
""")
        assert val(i) == "early"

    def test_return_subsequent_next_is_done(self):
        i = run("""
fn* gen() { yield 1; yield 2 }
let g = gen()
g.return(0)
let v = g.next()
""")
        assert val(i)["done"] is True


# ---------------------------------------------------------------------------
# Generator .throw()
# ---------------------------------------------------------------------------

class TestGeneratorThrow:
    def test_throw_injects_error(self):
        i = run("""
fn* gen() {
  try {
    yield 1
  } catch(e) {
    yield "caught: " + e
  }
}
let g = gen()
g.next()
let v = g.throw("error!")
""")
        assert val(i)["value"] == "caught: error!"

    def test_throw_done_false_when_caught(self):
        i = run("""
fn* gen() {
  try {
    yield 1
  } catch(e) {
    yield "caught"
  }
}
let g = gen()
g.next()
let v = g.throw("e").done
""")
        assert val(i) is False

    def test_throw_propagates_if_uncaught(self):
        i = run("""
fn* gen() { yield 1 }
let g = gen()
g.next()
let caught = false
try {
  g.throw("err")
} catch(e) {
  caught = true
}
let v = caught
""")
        assert val(i) is True


# ---------------------------------------------------------------------------
# yield*
# ---------------------------------------------------------------------------

class TestYieldStar:
    def test_yield_star_delegates(self):
        i = run("""
fn* inner() { yield 1; yield 2 }
fn* outer() { yield* inner(); yield 3 }
let v = [...outer()]
""")
        assert val(i) == [1, 2, 3]

    def test_yield_star_from_list(self):
        i = run("""
fn* gen() { yield* [1, 2, 3] }
let v = [...gen()]
""")
        assert val(i) == [1, 2, 3]

    def test_yield_star_return_value(self):
        i = run("""
fn* inner() {
  yield 1
  return "inner done"
}
fn* outer() {
  let result = yield* inner()
  yield result
}
let v = [...outer()]
""")
        assert val(i) == [1, "inner done"]

    def test_yield_star_nested(self):
        i = run("""
fn* a() { yield 1 }
fn* b() { yield* a(); yield 2 }
fn* c() { yield* b(); yield 3 }
let v = [...c()]
""")
        assert val(i) == [1, 2, 3]

    def test_yield_star_empty_inner(self):
        i = run("""
fn* inner() {}
fn* outer() { yield* inner(); yield 99 }
let v = [...outer()]
""")
        assert val(i) == [99]


# ---------------------------------------------------------------------------
# for...of on generator
# ---------------------------------------------------------------------------

class TestForOfGenerator:
    def test_for_of_sum(self):
        i = run("""
fn* gen() { yield 1; yield 2; yield 3 }
let v = 0
for (let x of gen()) {
  v = v + x
}
""")
        assert val(i) == 6

    def test_for_of_collect(self):
        i = run("""
fn* gen() { yield "a"; yield "b"; yield "c" }
let v = []
for (let x of gen()) {
  v.push(x)
}
""")
        assert val(i) == ["a", "b", "c"]

    def test_for_of_count(self):
        i = run("""
fn* gen() { yield 1; yield 2; yield 3; yield 4; yield 5 }
let v = 0
for (let x of gen()) {
  v = v + 1
}
""")
        assert val(i) == 5

    def test_for_of_break(self):
        i = run("""
fn* gen() { yield 1; yield 2; yield 3 }
let v = 0
for (let x of gen()) {
  v = v + x
  if (x == 2) break
}
""")
        assert val(i) == 3

    def test_for_of_with_complex_values(self):
        i = run("""
fn* pairs() {
  yield [1, "a"]
  yield [2, "b"]
}
let v = []
for (let p of pairs()) {
  v.push(p[0])
}
""")
        assert val(i) == [1, 2]


# ---------------------------------------------------------------------------
# Spread generator
# ---------------------------------------------------------------------------

class TestSpreadGenerator:
    def test_spread_basic(self):
        i = run("""
fn* gen() { yield 1; yield 2; yield 3 }
let v = [...gen()]
""")
        assert val(i) == [1, 2, 3]

    def test_spread_empty(self):
        i = run("""
fn* gen() {}
let v = [...gen()]
""")
        assert val(i) == []

    def test_spread_into_list(self):
        i = run("""
fn* gen() { yield 2; yield 3 }
let v = [1, ...gen(), 4]
""")
        assert val(i) == [1, 2, 3, 4]

    def test_spread_single_yield(self):
        i = run("""
fn* gen() { yield 42 }
let v = [...gen()]
""")
        assert val(i) == [42]


# ---------------------------------------------------------------------------
# Destructuring generator
# ---------------------------------------------------------------------------

class TestDestructureGenerator:
    def test_destructure_two(self):
        i = run("""
fn* gen() { yield 10; yield 20; yield 30 }
let [a, b] = gen()
let v = a + b
""")
        assert val(i) == 30

    def test_destructure_first(self):
        i = run("""
fn* gen() { yield 100; yield 200 }
let [a] = gen()
let v = a
""")
        assert val(i) == 100

    def test_destructure_three(self):
        i = run("""
fn* gen() { yield 1; yield 2; yield 3 }
let [a, b, c] = gen()
let v = [a, b, c]
""")
        assert val(i) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Infinite generators
# ---------------------------------------------------------------------------

class TestInfiniteGenerator:
    def test_infinite_first_three(self):
        i = run("""
fn* count() {
  let n = 0
  while(true) {
    yield n
    n = n + 1
  }
}
let g = count()
let a = g.next().value
let b = g.next().value
let c = g.next().value
let v = [a, b, c]
""")
        assert val(i) == [0, 1, 2]

    def test_infinite_take_five(self):
        i = run("""
fn* naturals() {
  let n = 1
  while(true) {
    yield n
    n = n + 1
  }
}
let g = naturals()
let v = 0
let i = 0
while(i < 5) {
  v = v + g.next().value
  i = i + 1
}
""")
        assert val(i) == 15

    def test_infinite_early_termination_return(self):
        i = run("""
fn* count() {
  let n = 0
  while(true) { yield n; n = n + 1 }
}
let g = count()
g.next()
g.next()
let v = g.return("stop").value
""")
        assert val(i) == "stop"

    def test_infinite_for_of_break(self):
        i = run("""
fn* count() {
  let n = 0
  while(true) { yield n; n = n + 1 }
}
let collected = []
for (let x of count()) {
  collected.push(x)
  if (x == 4) break
}
let v = collected
""")
        assert val(i) == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Generator state machine
# ---------------------------------------------------------------------------

class TestGeneratorStateMachine:
    def test_state_machine_steps(self):
        i = run("""
fn* stateMachine() {
  yield "init"
  yield "running"
  yield "done"
}
let g = stateMachine()
let s1 = g.next().value
let s2 = g.next().value
let s3 = g.next().value
let v = [s1, s2, s3]
""")
        assert val(i) == ["init", "running", "done"]

    def test_generator_accumulator(self):
        i = run("""
fn* accumulator() {
  let total = 0
  while(true) {
    total = total + 1
    yield total
  }
}
let g = accumulator()
g.next()
g.next()
let v = g.next().value
""")
        assert val(i) == 3


# ---------------------------------------------------------------------------
# Async generators
# ---------------------------------------------------------------------------

class TestAsyncGenerator:
    def test_async_gen_returns_promise(self):
        i = run("""
async fn* asyncGen() { yield 1 }
let g = asyncGen()
let v = g.next()
""")
        assert val(i)["value"] == 1

    def test_async_gen_multiple_yields(self):
        i = run("""
async fn* asyncGen() { yield 1; yield 2; yield 3 }
let g = asyncGen()
let a = g.next().value
let b = g.next().value
let c = g.next().value
let v = [a, b, c]
""")
        assert val(i) == [1, 2, 3]

    def test_for_await_of(self):
        i = run("""
async fn main() {
  let results = []
  async fn* asyncGen() { yield 1; yield 2; yield 3 }
  for await (let x of asyncGen()) {
    results.push(x)
  }
  return results
}
let p = main()
let v = p.value
""")
        assert val(i) == [1, 2, 3]

    def test_for_await_sum(self):
        i = run("""
async fn main() {
  let total = 0
  async fn* nums() { yield 10; yield 20; yield 30 }
  for await (let x of nums()) {
    total = total + x
  }
  return total
}
let p = main()
let v = p.value
""")
        assert val(i) == 60

    def test_async_gen_done_after_exhaust(self):
        i = run("""
async fn* gen() { yield 1 }
let g = gen()
g.next()
let v = g.next().done
""")
        assert val(i) is True
