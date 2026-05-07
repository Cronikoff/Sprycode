"""Tests for Phase 97: Generators"""
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


# ── Basic Generator ───────────────────────────────────────────────────────────

class TestBasicGenerator:
    def test_generator_function_star(self):
        i = run("function* gen() { yield 1; } let g = gen(); let v = typeof g.next;")
        assert val(i) == "function"

    def test_first_next_returns_value(self):
        i = run("function* gen() { yield 42; } let g = gen(); let v = g.next();")
        assert val(i) == {"value": 42, "done": False}

    def test_first_next_value(self):
        i = run("function* gen() { yield 42; } let g = gen(); let v = g.next().value;")
        assert val(i) == 42

    def test_first_next_not_done(self):
        i = run("function* gen() { yield 42; } let g = gen(); let v = g.next().done;")
        assert val(i) is False

    def test_after_exhausted_done_true(self):
        i = run("function* gen() { yield 1; } let g = gen(); g.next(); let v = g.next().done;")
        assert val(i) is True

    def test_after_exhausted_value_undefined(self):
        i = run("function* gen() { yield 1; } let g = gen(); g.next(); let v = g.next().value;")
        assert val(i) is None

    def test_multiple_yields(self):
        i = run("""
function* gen() { yield 1; yield 2; yield 3; }
let g = gen();
let r1 = g.next().value;
let r2 = g.next().value;
let r3 = g.next().value;
let v = [r1, r2, r3];
""")
        assert val(i) == [1, 2, 3]

    def test_three_yields_then_done(self):
        i = run("""
function* gen() { yield 1; yield 2; yield 3; }
let g = gen();
g.next(); g.next(); g.next();
let v = g.next().done;
""")
        assert val(i) is True

    def test_generator_yields_strings(self):
        i = run("""
function* gen() { yield \"a\"; yield \"b\"; }
let g = gen();
let r1 = g.next().value;
let r2 = g.next().value;
let v = r1 + r2;
""")
        assert val(i) == "ab"

    def test_generator_yields_objects(self):
        i = run("""
function* gen() { yield {x: 1}; }
let g = gen();
let v = g.next().value.x;
""")
        assert val(i) == 1

    def test_generator_independent_instances(self):
        i = run("""
function* gen() { yield 1; yield 2; }
let g1 = gen();
let g2 = gen();
g1.next();
let v1 = g1.next().value;
let v2 = g2.next().value;
let v = [v1, v2];
""")
        assert val(i) == [2, 1]

    def test_generator_yields_null(self):
        i = run("function* gen() { yield null; } let g = gen(); let v = g.next().value;")
        assert val(i) is None

    def test_generator_yields_boolean(self):
        i = run("function* gen() { yield true; } let g = gen(); let v = g.next().value;")
        assert val(i) is True

    def test_generator_empty_body(self):
        i = run("function* gen() {} let g = gen(); let v = g.next();")
        assert val(i) == {"value": None, "done": True}


# ── For...of over generator ───────────────────────────────────────────────────

class TestGeneratorForOf:
    def test_for_of_basic(self):
        i = run("""
function* gen() { yield 1; yield 2; yield 3; }
let v = [];
for (let x of gen()) { v.push(x); }
""")
        assert val(i) == [1, 2, 3]

    def test_for_of_collects_all(self):
        i = run("""
function* gen() { yield 10; yield 20; yield 30; }
let s = 0;
for (let x of gen()) { s = s + x; }
let v = s;
""")
        assert val(i) == 60

    def test_for_of_empty_generator(self):
        i = run("""
function* gen() {}
let v = [];
for (let x of gen()) { v.push(x); }
""")
        assert val(i) == []

    def test_for_of_single_yield(self):
        i = run("""
function* gen() { yield 42; }
let v = [];
for (let x of gen()) { v.push(x); }
""")
        assert val(i) == [42]

    def test_for_of_strings(self):
        i = run("""
function* letters() { yield \"a\"; yield \"b\"; yield \"c\"; }
let v = \"\";
for (let c of letters()) { v = v + c; }
""")
        assert val(i) == "abc"


# ── Generator with return value ───────────────────────────────────────────────

class TestGeneratorReturn:
    def test_return_sets_done_true(self):
        i = run("""
function* gen() { yield 1; return 99; }
let g = gen();
g.next();
let v = g.next().done;
""")
        assert val(i) is True

    def test_return_value_in_result(self):
        i = run("""
function* gen() { yield 1; return 99; }
let g = gen();
g.next();
let v = g.next().value;
""")
        assert val(i) == 99

    def test_after_return_done_stays_true(self):
        i = run("""
function* gen() { yield 1; return 99; }
let g = gen();
g.next(); g.next();
let v = g.next().done;
""")
        assert val(i) is True

    def test_return_before_yield(self):
        i = run("""
function* gen() { return 42; yield 1; }
let g = gen();
let v = g.next();
""")
        assert val(i) == {"value": 42, "done": True}

    def test_return_undefined_implicit(self):
        i = run("""
function* gen() { yield 1; }
let g = gen();
g.next();
let r = g.next();
let v = r.done;
""")
        assert val(i) is True


# ── yield* Delegation ─────────────────────────────────────────────────────────

class TestYieldStar:
    def test_yield_star_basic(self):
        i = run("""
function* inner() { yield 1; yield 2; }
function* outer() { yield* inner(); yield 3; }
let v = [];
for (let x of outer()) { v.push(x); }
""")
        assert val(i) == [1, 2, 3]

    def test_yield_star_array(self):
        i = run("""
function* gen() { yield* [10, 20, 30]; }
let v = [];
for (let x of gen()) { v.push(x); }
""")
        assert val(i) == [10, 20, 30]

    def test_yield_star_chained(self):
        i = run("""
function* a() { yield 1; }
function* b() { yield* a(); yield 2; }
function* c() { yield* b(); yield 3; }
let v = [...c()];
""")
        assert val(i) == [1, 2, 3]

    def test_yield_star_before_yield(self):
        i = run("""
function* inner() { yield 1; yield 2; }
function* outer() { yield 0; yield* inner(); }
let v = [...outer()];
""")
        assert val(i) == [0, 1, 2]

    def test_yield_star_empty_inner(self):
        i = run("""
function* inner() {}
function* outer() { yield 0; yield* inner(); yield 1; }
let v = [...outer()];
""")
        assert val(i) == [0, 1]


# ── Generator as iterator (spread) ───────────────────────────────────────────

class TestGeneratorSpread:
    def test_spread_basic(self):
        i = run("function* gen() { yield 1; yield 2; yield 3; } let v = [...gen()];")
        assert val(i) == [1, 2, 3]

    def test_spread_into_array(self):
        i = run("function* gen() { yield 4; yield 5; } let v = [1, 2, 3, ...gen()];")
        assert val(i) == [1, 2, 3, 4, 5]

    def test_spread_empty_generator(self):
        i = run("function* gen() {} let v = [...gen()];")
        assert val(i) == []

    def test_spread_length(self):
        i = run("function* gen() { yield 1; yield 2; yield 3; } let v = [...gen()].length;")
        assert val(i) == 3


# ── Infinite Generator with Early Return ──────────────────────────────────────

class TestInfiniteGenerator:
    def test_break_from_for_of(self):
        i = run("""
function* count() { let i = 0; while(true) { yield i++; } }
let v = [];
for (let x of count()) { v.push(x); if (x >= 4) break; }
""")
        assert val(i) == [0, 1, 2, 3, 4]

    def test_take_first_n(self):
        i = run("""
function* nats() { let n = 1; while(true) { yield n++; } }
let v = [];
let g = nats();
let i = 0;
while (i < 5) { v.push(g.next().value); i++; }
""")
        assert val(i) == [1, 2, 3, 4, 5]

    def test_infinite_with_condition(self):
        i = run("""
function* powers() { let p = 1; while(true) { yield p; p = p * 2; } }
let v = [];
for (let x of powers()) { if (x > 16) break; v.push(x); }
""")
        assert val(i) == [1, 2, 4, 8, 16]

    def test_infinite_fibonacci(self):
        i = run("""
function* fib() {
  let a = 0; let b = 1;
  while(true) {
    yield a;
    let tmp = a + b; a = b; b = tmp;
  }
}
let v = [];
for (let x of fib()) { if (x > 20) break; v.push(x); }
""")
        assert val(i) == [0, 1, 1, 2, 3, 5, 8, 13]


# ── Generator with Parameters ─────────────────────────────────────────────────

class TestGeneratorParameters:
    def test_single_param(self):
        i = run("""
function* genN(n) { let i = 0; while(i < n) { yield i++; } }
let v = [...genN(3)];
""")
        assert val(i) == [0, 1, 2]

    def test_two_params(self):
        i = run("""
function* range(start, n) { let i = 0; while(i < n) { yield start + i; i++; } }
let v = [...range(5, 3)];
""")
        assert val(i) == [5, 6, 7]

    def test_param_used_in_yield(self):
        i = run("""
function* gen(x) { yield x; yield x * 2; yield x * 3; }
let v = [...gen(10)];
""")
        assert val(i) == [10, 20, 30]

    def test_param_with_default(self):
        i = run("""
function* gen(n = 3) { let i = 0; while(i < n) { yield i++; } }
let v = [...gen()];
""")
        assert val(i) == [0, 1, 2]


# ── Generator Storing State ───────────────────────────────────────────────────

class TestGeneratorState:
    def test_accumulating_state(self):
        i = run("""
function* running() {
  let sum = 0;
  while(true) {
    let n = yield sum;
    sum = sum + n;
  }
}
let g = running();
g.next();
g.next(5);
g.next(3);
let v = g.next(7).value;
""")
        assert val(i) == 15

    def test_counter_state(self):
        i = run("""
function* counter() { let n = 0; while(true) { yield n++; } }
let g = counter();
g.next(); g.next(); g.next();
let v = g.next().value;
""")
        assert val(i) == 3

    def test_state_across_multiple_calls(self):
        i = run("""
function* gen() {
  let x = 1;
  yield x;
  x = x * 10;
  yield x;
  x = x + 5;
  yield x;
}
let v = [...gen()];
""")
        assert val(i) == [1, 10, 15]

    def test_closure_state(self):
        i = run("""
function makeCounter() {
  let n = 0;
  function* counter() { while(true) { yield n++; } }
  return counter;
}
let c = makeCounter()();
c.next(); c.next();
let v = c.next().value;
""")
        assert val(i) == 2


# ── next(value) Sending Value Into Generator ──────────────────────────────────

class TestNextValue:
    def test_send_value_basic(self):
        i = run("""
function* gen() {
  let x = yield 1;
  yield x + 10;
}
let g = gen();
g.next();
let v = g.next(5).value;
""")
        assert val(i) == 15

    def test_send_value_chain(self):
        i = run("""
function* gen() {
  let x = yield 0;
  let y = yield x * 2;
  yield y + 100;
}
let g = gen();
g.next();
g.next(5);
let v = g.next(20).value;
""")
        assert val(i) == 120

    def test_first_next_ignores_value(self):
        i = run("""
function* gen() { let x = yield 1; yield x; }
let g = gen();
let r1 = g.next(99);
let v = r1.value;
""")
        assert val(i) == 1

    def test_send_string(self):
        i = run("""
function* gen() {
  let name = yield \"name?\";
  yield \"Hello, \" + name;
}
let g = gen();
g.next();
let v = g.next(\"Alice\").value;
""")
        assert val(i) == "Hello, Alice"


# ── Generator try/finally ──────────────────────────────────────────────────────

class TestGeneratorFinally:
    def test_finally_runs_on_return(self):
        i = run("""
let v = [];
function* gen() {
  try { yield 1; yield 2; }
  finally { v.push(\"finally\"); }
}
let g = gen();
g.next();
g.return(99);
""")
        assert val(i) == ["finally"]

    def test_finally_runs_on_throw(self):
        i = run("""
let v = [];
function* gen() {
  try { yield 1; }
  catch(e) { v.push(\"caught\"); }
  finally { v.push(\"finally\"); }
}
let g = gen();
g.next();
g.throw(\"err\");
""")
        assert "finally" in val(i)

    def test_finally_runs_normally(self):
        i = run("""
let v = [];
function* gen() {
  try { yield 1; }
  finally { v.push(\"done\"); }
}
let g = gen();
g.next();
g.next();
""")
        assert val(i) == ["done"]


# ── gen.return(val) ───────────────────────────────────────────────────────────

class TestGenReturn:
    def test_return_val_done_true(self):
        i = run("""
function* gen() { yield 1; yield 2; yield 3; }
let g = gen();
g.next();
let v = g.return(42);
""")
        assert val(i) == {"value": 42, "done": True}

    def test_return_makes_generator_done(self):
        i = run("""
function* gen() { yield 1; yield 2; }
let g = gen();
g.next();
g.return(0);
let v = g.next().done;
""")
        assert val(i) is True

    def test_return_without_starting(self):
        i = run("""
function* gen() { yield 1; yield 2; }
let g = gen();
let v = g.return(99);
""")
        assert val(i) == {"value": 99, "done": True}

    def test_return_value_is_arg(self):
        i = run("""
function* gen() { yield 1; }
let g = gen();
g.next();
let v = g.return(\"done\").value;
""")
        assert val(i) == "done"


# ── gen.throw(err) ────────────────────────────────────────────────────────────

class TestGenThrow:
    def test_throw_caught_by_generator(self):
        i = run("""
function* gen() {
  try { yield 1; } catch(e) { yield \"caught:\" + e; }
}
let g = gen();
g.next();
let v = g.throw(\"oops\").value;
""")
        assert val(i) == "caught:oops"

    def test_throw_continues_generator(self):
        i = run("""
function* gen() {
  try { yield 1; } catch(e) {}
  yield 2;
}
let g = gen();
g.next();
g.throw(\"err\");
let v = g.next().done;
""")
        assert val(i) is True

    def test_throw_after_catch_yields_next(self):
        i = run("""
function* gen() {
  try { yield 1; } catch(e) { yield \"caught\"; }
  yield 3;
}
let g = gen();
g.next();
let r2 = g.throw(\"err\");
let v = r2.value;
""")
        assert val(i) == "caught"

    def test_throw_returns_done_false_if_caught(self):
        i = run("""
function* gen() {
  try { yield 1; } catch(e) { yield 2; }
}
let g = gen();
g.next();
let v = g.throw(\"e\").done;
""")
        assert val(i) is False


# ── Generator function name ───────────────────────────────────────────────────

class TestGeneratorName:
    def test_named_generator_name_prop(self):
        i = run("function* myGen() { yield 1; } let v = myGen.name;")
        assert val(i) == "myGen"

    def test_generator_name_different(self):
        i = run("function* foo() { yield 1; } function* bar() { yield 2; } let v = foo.name + bar.name;")
        assert val(i) == "foobar"

    def test_generator_name_nonempty(self):
        i = run("function* gen() { yield 1; } let v = gen.name.length > 0;")
        assert val(i) is True
