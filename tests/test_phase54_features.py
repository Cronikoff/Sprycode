"""Phase 54 feature tests — RegExp namespace, AbortSignal, Error enhancements,
Map.getOrInsert, Symbol.dispose, using declaration."""
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
# RegExp namespace
# ---------------------------------------------------------------------------

class TestRegExpNamespace:
    def test_regexp_constructor(self):
        assert val('let r = new RegExp("\\\\d+")\nlet v = r.test("123")') is True

    def test_regexp_call(self):
        assert val('let r = RegExp("hello")\nlet v = r.test("say hello world")') is True

    def test_regexp_no_match(self):
        assert val('let r = RegExp("xyz")\nlet v = r.test("abcdef")') is False


# ---------------------------------------------------------------------------
# AbortSignal namespace
# ---------------------------------------------------------------------------

class TestAbortSignal:
    def test_abort_signal_abort(self):
        src = """
let sig = AbortSignal.abort("reason")
let v = sig.aborted
"""
        assert val(src) is True

    def test_abort_signal_timeout(self):
        src = """
let sig = AbortSignal.timeout(100)
let v = typeof sig
"""
        assert val(src) == "object"

    def test_abort_signal_any(self):
        src = """
let ctrl = new AbortController()
let sig = AbortSignal.any([ctrl.signal])
let v = typeof sig
"""
        assert val(src) == "object"


# ---------------------------------------------------------------------------
# Error.isError / Error.stackTraceLimit
# ---------------------------------------------------------------------------

class TestErrorEnhancements:
    def test_is_error_true(self):
        src = """
let v = false
try {
  throw new Error("oops")
} catch(e) {
  v = Error.isError(e)
}
"""
        assert val(src) is True

    def test_is_error_false(self):
        assert val('let v = Error.isError("not an error")') is False

    def test_stack_trace_limit(self):
        src = """
Error.stackTraceLimit = 5
let v = Error.stackTraceLimit
"""
        assert val(src) == 5

    def test_capture_stack_trace(self):
        src = """
let obj = {}
Error.captureStackTrace(obj)
let v = typeof obj.stack
"""
        assert val(src) == "string"


# ---------------------------------------------------------------------------
# Map.getOrInsert / getOrInsertComputed
# ---------------------------------------------------------------------------

class TestMapGetOrInsert:
    def test_get_or_insert_existing(self):
        src = """
let m = new Map()
m.set("x", 42)
let v = m.getOrInsert("x", 99)
"""
        assert val(src) == 42

    def test_get_or_insert_missing(self):
        src = """
let m = new Map()
let v = m.getOrInsert("x", 99)
"""
        assert val(src) == 99

    def test_get_or_insert_computed(self):
        src = """
let m = new Map()
let v = m.getOrInsertComputed("x", k => k.length)
"""
        assert val(src) == 1


# ---------------------------------------------------------------------------
# Symbol.dispose / asyncDispose
# ---------------------------------------------------------------------------

class TestSymbolDispose:
    def test_symbol_dispose_defined(self):
        src = 'let v = typeof Symbol.dispose'
        assert val(src) == "symbol"

    def test_symbol_async_dispose_defined(self):
        src = 'let v = typeof Symbol.asyncDispose'
        assert val(src) == "symbol"


# ---------------------------------------------------------------------------
# using declaration
# ---------------------------------------------------------------------------

class TestUsingDeclaration:
    def test_using_basic(self):
        src = """
using x = 42
let v = x
"""
        assert val(src) == 42

    def test_using_expression(self):
        src = """
using greeting = "hello"
let v = greeting
"""
        assert val(src) == "hello"
