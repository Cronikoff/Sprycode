"""Phase 30: async fn, Object.is(-0), Array.from(SpryMap/Set),
SpryInstance[key] indexing, for-in skips methods, Object.freeze/isFrozen.
"""
from __future__ import annotations

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


def val(i: Interpreter, name: str = "v") -> object:
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# Fix 1 — Object.is distinguishes -0 from +0
# ---------------------------------------------------------------------------

class TestObjectIs:
    def test_negative_zero_vs_positive_zero(self):
        i = run("let v = Object.is(0, -0)")
        assert val(i) is False

    def test_positive_zero_equals_itself(self):
        i = run("let v = Object.is(0, 0)")
        assert val(i) is True

    def test_nan_equals_nan(self):
        i = run("let v = Object.is(0/0, 0/0)")
        assert val(i) is True

    def test_same_integer(self):
        i = run("let v = Object.is(42, 42)")
        assert val(i) is True

    def test_different_integers(self):
        i = run("let v = Object.is(1, 2)")
        assert val(i) is False

    def test_unary_minus_zero_is_float(self):
        """Unary minus on 0 produces float(-0.0) so Object.is can detect it."""
        i = run("let neg = -0\nlet v = Object.is(neg, 0)")
        assert val(i) is False

    def test_minus_zero_value(self):
        import math
        i = run("let v = -0")
        result = val(i)
        assert isinstance(result, float)
        assert math.copysign(1.0, result) < 0


# ---------------------------------------------------------------------------
# Fix 2 — async fn wraps return value in SpryPromise
# ---------------------------------------------------------------------------

class TestAsyncFn:
    def test_typeof_returns_promise(self):
        i = run("async fn f() { return 42 }\nlet v = typeof f()")
        assert val(i) == "object"

    def test_then_receives_value(self):
        i = run(
            "async fn f() { return 42 }\n"
            "var v = 0\n"
            "f().then(x => { v = x })"
        )
        assert val(i) == 42

    def test_then_chaining(self):
        i = run(
            "async fn f() { return 10 }\n"
            "var v = 0\n"
            "f().then(x => x * 2).then(x => { v = x })"
        )
        assert val(i) == 20

    def test_await_unwraps_promise(self):
        i = run(
            "async fn f() { return 42 }\n"
            "async fn g() {\n"
            "  let x = await f()\n"
            "  return x + 1\n"
            "}\n"
            "var v = 0\n"
            "g().then(r => { v = r })"
        )
        assert val(i) == 43

    def test_async_no_return_gives_null(self):
        i = run(
            "async fn f() { let x = 1 }\n"
            "var v = f().status"
        )
        assert val(i) == "fulfilled"

    def test_async_rejected_on_throw(self):
        i = run(
            'async fn f() { throw Error.new("boom") }\n'
            'var v = ""\n'
            'f().catch(e => { v = "caught" })'
        )
        assert val(i) == "caught"

    def test_async_status_fulfilled(self):
        i = run("async fn f() { return 1 }\nlet v = f().status")
        assert val(i) == "fulfilled"

    def test_async_catch_error_message(self):
        i = run(
            'async fn f() { throw Error.new("oops") }\n'
            'var v = ""\n'
            'f().catch(e => { v = e })'
        )
        assert "oops" in str(val(i))

    def test_async_fn_with_computation(self):
        i = run(
            "async fn double(n) { return n * 2 }\n"
            "var v = 0\n"
            "double(21).then(x => { v = x })"
        )
        assert val(i) == 42

    def test_await_in_nested_async(self):
        i = run(
            "async fn getNum() { return 5 }\n"
            "async fn compute() {\n"
            "  let a = await getNum()\n"
            "  let b = await getNum()\n"
            "  return a + b\n"
            "}\n"
            "var v = 0\n"
            "compute().then(r => { v = r })"
        )
        assert val(i) == 10


# ---------------------------------------------------------------------------
# Fix 3 — Array.from(SpryMap) / Array.from(SprySet)
# ---------------------------------------------------------------------------

class TestArrayFromCollections:
    def test_array_from_sprymap(self):
        i = run('let m = Map.new([["a",1],["b",2]])\nlet v = Array.from(m)')
        assert val(i) == [["a", 1], ["b", 2]]

    def test_array_from_spryset(self):
        i = run("let s = Set.new([1,2,3])\nlet v = Array.from(s)")
        assert sorted(val(i)) == [1, 2, 3]

    def test_array_from_empty_map(self):
        i = run("let m = Map.new()\nlet v = Array.from(m)")
        assert val(i) == []

    def test_array_from_empty_set(self):
        i = run("let s = Set.new()\nlet v = Array.from(s)")
        assert val(i) == []

    def test_array_from_map_keys_match(self):
        i = run('let m = Map.new([["x",10]])\nlet v = Array.from(m)[0][0]')
        assert val(i) == "x"

    def test_array_from_map_values_match(self):
        i = run('let m = Map.new([["x",10]])\nlet v = Array.from(m)[0][1]')
        assert val(i) == 10

    def test_spread_sprymap(self):
        """Spread also uses _iter_to_list — should work for SpryMap."""
        i = run('let m = Map.new([["a",1]])\nlet v = [...m]')
        assert val(i) == [["a", 1]]

    def test_spread_spryset(self):
        i = run("let s = Set.new([7,8,9])\nlet v = [...s]")
        assert sorted(val(i)) == [7, 8, 9]


# ---------------------------------------------------------------------------
# Fix 4 — SpryInstance[key] indexing
# ---------------------------------------------------------------------------

class TestInstanceIndexing:
    def test_string_key_access(self):
        i = run(
            'class P { fn init(x,y) { self.x=x\nself.y=y } }\n'
            'let p = P.new(3,4)\n'
            'let v = p["x"] + p["y"]'
        )
        assert val(i) == 7

    def test_computed_key_access(self):
        i = run(
            'class C { fn init(n) { self.n=n } }\n'
            'let obj = C.new(99)\n'
            'let k = "n"\n'
            'let v = obj[k]'
        )
        assert val(i) == 99

    def test_for_in_instance_with_subscript(self):
        i = run(
            'class P { fn init(x,y) { self.x=x\nself.y=y } }\n'
            'let p = P.new(3,4)\n'
            'var v = 0\n'
            'for let k in p { v = v + p[k] }'
        )
        assert val(i) == 7

    def test_for_in_skips_methods(self):
        i = run(
            'class P {\n'
            '  fn init(x) { self.x=x }\n'
            '  fn double() { return self.x * 2 }\n'
            '}\n'
            'let p = P.new(5)\n'
            'let keys = []\n'
            'for let k in p { keys.push(k) }'
        )
        keys = i.globals.get("keys")
        assert "x" in keys
        assert "double" not in keys
        assert "init" not in keys

    def test_instance_setitem(self):
        i = run(
            'class C { fn init() { self.v=0 } }\n'
            'let obj = C.new()\n'
            'obj["v"] = 42\n'
            'let v = obj["v"]'
        )
        assert val(i) == 42

    def test_missing_key_raises(self):
        with pytest.raises(Exception, match="Index error|not found|missing"):
            run(
                'class C { fn init() { self.x=1 } }\n'
                'let obj = C.new()\n'
                'let v = obj["missing"]'
            )


# ---------------------------------------------------------------------------
# Fix 5 — Object.freeze / Object.isFrozen
# ---------------------------------------------------------------------------

class TestObjectFreeze:
    def test_frozen_object_is_frozen(self):
        i = run("let obj = {x:1}\nObject.freeze(obj)\nlet v = Object.isFrozen(obj)")
        assert val(i) is True

    def test_unfrozen_object_is_not_frozen(self):
        i = run("let obj = {x:1}\nlet v = Object.isFrozen(obj)")
        assert val(i) is False

    def test_freeze_returns_object(self):
        i = run("let obj = {x:1}\nlet v = Object.freeze(obj) == null")
        assert val(i) is False  # freeze returns the object, not null

    def test_frozen_instance(self):
        i = run(
            "class C { fn init() { self.x=1 } }\n"
            "let obj = C.new()\n"
            "Object.freeze(obj)\n"
            "let v = Object.isFrozen(obj)"
        )
        assert val(i) is True

    def test_empty_object_freeze(self):
        i = run("let obj = {}\nObject.freeze(obj)\nlet v = Object.isFrozen(obj)")
        assert val(i) is True
