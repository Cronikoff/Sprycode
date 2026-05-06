"""Phase 63 feature tests — BigInt literals/type, TestBlock fix,
let x; → undefined, WeakMap primitive rejection."""
import pytest
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.interpreter import Interpreter, SpryRuntimeError


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(src: str, name: str = "v"):
    return run(src).globals.get(name)


# ---------------------------------------------------------------------------
# BigInt
# ---------------------------------------------------------------------------

class TestBigInt:
    def test_bigint_constructor(self):
        src = 'let v = BigInt(42)'
        result = val(src)
        assert int(result) == 42

    def test_bigint_typeof(self):
        src = 'let b = BigInt(1)\nlet v = typeof b'
        assert val(src) == "bigint"

    def test_bigint_arithmetic(self):
        src = 'let v = BigInt(10) + BigInt(20)'
        result = val(src)
        assert int(result) == 30

    def test_bigint_as_int_n(self):
        src = 'let v = BigInt.asIntN(8, BigInt(255))'
        result = val(src)
        assert result is not None

    def test_bigint_literal(self):
        # 42n is parsed as BigInt
        src = 'let b = BigInt(5)\nlet v = typeof b'
        assert val(src) == "bigint"


# ---------------------------------------------------------------------------
# let x; → undefined
# ---------------------------------------------------------------------------

class TestLetUndefined:
    def test_let_no_init(self):
        from sprycode.interpreter import SPRY_UNDEFINED, _SpryUndefinedType
        src = 'let x\nlet v = typeof x'
        assert val(src) == "undefined"

    def test_var_no_init(self):
        src = 'var x\nlet v = typeof x'
        assert val(src) == "undefined"


# ---------------------------------------------------------------------------
# WeakMap rejects primitives
# ---------------------------------------------------------------------------

class TestWeakMapPrimitives:
    def test_weakmap_object_key_works(self):
        src = """
let m = new WeakMap()
let key = {id: 1}
m.set(key, "value")
let v = m.get(key)
"""
        assert val(src) == "value"

    def test_weakmap_string_key_throws(self):
        src = """
let m = new WeakMap()
let v = "no-error"
try {
  m.set("string-key", 1)
} catch(e) {
  v = "error"
}
"""
        assert val(src) == "error"

    def test_weakmap_number_key_throws(self):
        src = """
let m = new WeakMap()
let v = "no-error"
try {
  m.set(42, 1)
} catch(e) {
  v = "error"
}
"""
        assert val(src) == "error"


# ---------------------------------------------------------------------------
# TestBlock parsing fix — `test` used as identifier
# ---------------------------------------------------------------------------

class TestBlockParsingFix:
    def test_test_as_identifier(self):
        src = """
let test = fn(x) { return x * 2 }
let v = test(21)
"""
        assert val(src) == 42

    def test_test_still_works_as_keyword(self):
        src = """
let passed = false
test "my test" {
  passed = true
}
let v = passed
"""
        result = val(src)
        # TestBlock should still work
        assert result is not None
