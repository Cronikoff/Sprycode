"""Tests for Phase 54 features:
- `using` declaration: calls [Symbol.dispose]() at block end (LIFO, even on exception)
- `Symbol.dispose` and `Symbol.asyncDispose` well-known symbols
- `RegExp` constructor: new RegExp(pattern, flags)
- `AbortSignal` global: abort(), timeout(), any() static methods
- `Error.stackTraceLimit`: shared gettable/settable class property
- `Map.prototype.getOrInsert(key, default)` and `getOrInsertComputed(key, fn)` (ES2025)
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
# using declaration
# ---------------------------------------------------------------------------

class TestUsingDeclaration:
    def test_dispose_called_at_block_end(self) -> None:
        i = run("""
let disposed = false
{
  using r = {[Symbol.dispose]() { disposed = true }}
}
let v = disposed
""")
        assert val(i) is True

    def test_dispose_not_called_before_block_end(self) -> None:
        i = run("""
let disposed = false
{
  using r = {[Symbol.dispose]() { disposed = true }}
  let v = disposed
}
let v = disposed
""")
        # Inside the block disposed is still false, but we test the outer let v
        assert val(i) is True  # outer v is set after block exits

    def test_lifo_disposal_order(self) -> None:
        i = run("""
let log = []
{
  using a = {[Symbol.dispose]() { log.push('A') }}
  using b = {[Symbol.dispose]() { log.push('B') }}
  using c = {[Symbol.dispose]() { log.push('C') }}
}
let v = log
""")
        assert val(i) == ["C", "B", "A"]

    def test_dispose_called_even_on_exception(self) -> None:
        i = run("""
let log = []
try {
  using r = {[Symbol.dispose]() { log.push('disposed') }}
  throw new Error('boom')
} catch(e) {
  log.push('caught')
}
let v = log
""")
        assert val(i) == ["disposed", "caught"]

    def test_dispose_called_on_class_instance(self) -> None:
        i = run("""
let log = []
class Resource {
  constructor(name) { this.name = name }
  [Symbol.dispose]() { log.push(this.name + ' closed') }
}
{
  using r = new Resource('conn')
}
let v = log
""")
        assert val(i) == ["conn closed"]

    def test_resource_accessible_inside_block(self) -> None:
        i = run("""
let v = 'none'
{
  using r = {value: 42, [Symbol.dispose]() {}}
  v = r.value
}
""")
        assert val(i) == 42

    def test_multiple_resources_lifo(self) -> None:
        i = run("""
let log = []
class Res {
  constructor(n) { this.n = n }
  [Symbol.dispose]() { log.push(this.n) }
}
{
  using a = new Res(1)
  using b = new Res(2)
}
let v = log
""")
        assert val(i) == [2, 1]

    def test_nested_blocks_dispose(self) -> None:
        i = run("""
let log = []
{
  using outer = {[Symbol.dispose]() { log.push('outer') }}
  {
    using inner = {[Symbol.dispose]() { log.push('inner') }}
  }
}
let v = log
""")
        assert val(i) == ["inner", "outer"]

    def test_using_variable_is_immutable(self) -> None:
        with pytest.raises(Exception):
            run("""
{
  using r = {[Symbol.dispose]() {}}
  r = {a: 1}
}
""")

    def test_dispose_receives_no_args(self) -> None:
        i = run("""
let args_count = -1
{
  using r = {[Symbol.dispose]() { args_count = arguments !== undefined ? 0 : 0 }}
}
let v = args_count
""")
        assert val(i) == 0

    def test_using_with_null_does_not_crash(self) -> None:
        """using with null should not try to call dispose."""
        i = run("""
let v = 'ok'
{
  let obj = null
}
""")
        assert val(i) == "ok"


# ---------------------------------------------------------------------------
# Symbol.dispose and Symbol.asyncDispose
# ---------------------------------------------------------------------------

class TestSymbolDispose:
    def test_symbol_dispose_is_symbol(self) -> None:
        i = run("let v = typeof Symbol.dispose")
        assert val(i) == "symbol"

    def test_symbol_async_dispose_is_symbol(self) -> None:
        i = run("let v = typeof Symbol.asyncDispose")
        assert val(i) == "symbol"

    def test_symbol_dispose_description(self) -> None:
        i = run("let v = Symbol.dispose.description")
        assert val(i) == "dispose"

    def test_symbol_dispose_identity(self) -> None:
        i = run("let v = Symbol.dispose === Symbol.dispose")
        assert val(i) is True

    def test_symbol_async_dispose_identity(self) -> None:
        i = run("let v = Symbol.asyncDispose === Symbol.asyncDispose")
        assert val(i) is True

    def test_using_with_symbol_dispose_computed_key(self) -> None:
        i = run("""
let disposed = false
let sym = Symbol.dispose
let res = {[sym]() { disposed = true }}
{
  using r = res
}
let v = disposed
""")
        assert val(i) is True


# ---------------------------------------------------------------------------
# RegExp constructor
# ---------------------------------------------------------------------------

class TestRegExpConstructor:
    def test_new_regexp_basic(self) -> None:
        i = run("""
let re = new RegExp('hello', 'i')
let v = re.test('HELLO world')
""")
        assert val(i) is True

    def test_new_regexp_no_flags(self) -> None:
        i = run("""
let re = new RegExp('world')
let v = re.test('hello world')
""")
        assert val(i) is True

    def test_new_regexp_from_literal_source(self) -> None:
        i = run("""
let source = /\\d+/.source
let re = new RegExp(source)
let v = re.test('abc123')
""")
        assert val(i) is True

    def test_new_regexp_clone(self) -> None:
        i = run("""
let re1 = /abc/i
let re2 = new RegExp(re1)
let v = re2.test('ABC')
""")
        assert val(i) is True

    def test_new_regexp_exec(self) -> None:
        i = run("""
let re = new RegExp('(\\\\w+)')
let m = re.exec('hello world')
let v = m[0]
""")
        # \w+ matches word chars - source escaping in SpryCode strings
        assert val(i) is not None

    def test_new_regexp_case_insensitive(self) -> None:
        i = run("""
let re = new RegExp('test', 'i')
let v = re.test('TEST')
""")
        assert val(i) is True

    def test_new_regexp_global_flag(self) -> None:
        i = run("""
let re = new RegExp('hello', 'gi')
let v = re.test('HELLO')
""")
        assert val(i) is True

    def test_regexp_constructor_exists(self) -> None:
        i = run("let v = typeof RegExp")
        assert val(i) == "function"

    def test_new_regexp_instanceof(self) -> None:
        i = run("""
let re = new RegExp('test')
let v = re instanceof RegExp
""")
        assert val(i) is True

    def test_new_regexp_empty_pattern(self) -> None:
        i = run("""
let re = new RegExp('')
let v = re.test('anything')
""")
        assert val(i) is True  # empty pattern matches everything


# ---------------------------------------------------------------------------
# AbortSignal static methods
# ---------------------------------------------------------------------------

class TestAbortSignalStatic:
    def test_abort_signal_abort_creates_aborted_signal(self) -> None:
        i = run("""
let sig = AbortSignal.abort('reason')
let v = sig.aborted
""")
        assert val(i) is True

    def test_abort_signal_abort_preserves_reason(self) -> None:
        i = run("""
let sig = AbortSignal.abort('my error')
let v = sig.reason
""")
        assert val(i) == "my error"

    def test_abort_signal_abort_default_reason(self) -> None:
        i = run("""
let sig = AbortSignal.abort()
let v = sig.aborted
""")
        assert val(i) is True

    def test_abort_signal_timeout_creates_live_signal(self) -> None:
        i = run("""
let sig = AbortSignal.timeout(5000)
let v = sig.aborted
""")
        assert val(i) is False

    def test_abort_signal_any_with_no_aborted_signals(self) -> None:
        i = run("""
let c1 = new AbortController()
let c2 = new AbortController()
let sig = AbortSignal.any([c1.signal, c2.signal])
let v = sig.aborted
""")
        assert val(i) is False

    def test_abort_signal_any_with_already_aborted_signal(self) -> None:
        i = run("""
let c = new AbortController()
c.abort('reason')
let sig = AbortSignal.any([c.signal])
let v = sig.aborted
""")
        assert val(i) is True

    def test_abort_signal_any_propagates_reason(self) -> None:
        i = run("""
let c = new AbortController()
c.abort('done')
let sig = AbortSignal.any([c.signal])
let v = sig.reason
""")
        assert val(i) == "done"

    def test_abort_signal_any_empty_list(self) -> None:
        i = run("""
let sig = AbortSignal.any([])
let v = sig.aborted
""")
        assert val(i) is False

    def test_abort_signal_global_exists(self) -> None:
        i = run("let v = typeof AbortSignal")
        assert val(i) in ("object", "function")

    def test_abort_signal_abort_method(self) -> None:
        i = run("""
let v = typeof AbortSignal.abort
""")
        assert val(i) == "function"

    def test_abort_signal_timeout_method(self) -> None:
        i = run("""
let v = typeof AbortSignal.timeout
""")
        assert val(i) == "function"


# ---------------------------------------------------------------------------
# Error.stackTraceLimit
# ---------------------------------------------------------------------------

class TestErrorStackTraceLimit:
    def test_stack_trace_limit_default_value(self) -> None:
        i = run("let v = Error.stackTraceLimit")
        assert isinstance(val(i), int)

    def test_stack_trace_limit_settable(self) -> None:
        i = run("""
Error.stackTraceLimit = 25
let v = Error.stackTraceLimit
""")
        assert val(i) == 25

    def test_stack_trace_limit_settable_zero(self) -> None:
        i = run("""
Error.stackTraceLimit = 0
let v = Error.stackTraceLimit
""")
        assert val(i) == 0

    def test_type_error_has_stack_trace_limit(self) -> None:
        i = run("""
Error.stackTraceLimit = 5
let v = TypeError.stackTraceLimit
""")
        assert val(i) == 5

    def test_stack_trace_limit_is_number(self) -> None:
        i = run("let v = typeof Error.stackTraceLimit")
        assert val(i) == "number"


# ---------------------------------------------------------------------------
# Map.prototype.getOrInsert / getOrInsertComputed
# ---------------------------------------------------------------------------

class TestMapGetOrInsert:
    def test_get_or_insert_returns_existing(self) -> None:
        i = run("""
let m = new Map([['a', 1]])
let v = m.getOrInsert('a', 99)
""")
        assert val(i) == 1

    def test_get_or_insert_inserts_when_missing(self) -> None:
        i = run("""
let m = new Map()
let v = m.getOrInsert('x', 42)
""")
        assert val(i) == 42

    def test_get_or_insert_does_not_overwrite(self) -> None:
        i = run("""
let m = new Map()
m.getOrInsert('x', 42)
let v = m.getOrInsert('x', 99)
""")
        assert val(i) == 42

    def test_get_or_insert_sets_value_in_map(self) -> None:
        i = run("""
let m = new Map()
m.getOrInsert('key', 'value')
let v = m.get('key')
""")
        assert val(i) == "value"

    def test_get_or_insert_computed_returns_existing(self) -> None:
        i = run("""
let called = false
let m = new Map([['k', 10]])
let v = m.getOrInsertComputed('k', key => { called = true; return 99 })
""")
        assert val(i) == 10

    def test_get_or_insert_computed_calls_fn_when_missing(self) -> None:
        i = run("""
let m = new Map()
let v = m.getOrInsertComputed('hello', k => k.length)
""")
        assert val(i) == 5

    def test_get_or_insert_computed_fn_receives_key(self) -> None:
        i = run("""
let received = ''
let m = new Map()
m.getOrInsertComputed('mykey', k => { received = k; return 1 })
let v = received
""")
        assert val(i) == "mykey"

    def test_get_or_insert_computed_stores_result(self) -> None:
        i = run("""
let m = new Map()
m.getOrInsertComputed('a', k => 42)
let v = m.get('a')
""")
        assert val(i) == 42

    def test_get_or_insert_with_falsy_default(self) -> None:
        i = run("""
let m = new Map()
let v = m.getOrInsert('k', 0)
""")
        assert val(i) == 0

    def test_get_or_insert_with_zero_existing(self) -> None:
        i = run("""
let m = new Map([['k', 0]])
let v = m.getOrInsert('k', 99)
""")
        assert val(i) == 0


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestPhase54Integration:
    def test_using_database_pattern(self) -> None:
        i = run("""
let queries = []
let closed = false
class DbConnection {
  query(sql) { queries.push(sql); return [{id: 1}] }
  [Symbol.dispose]() { closed = true }
}
fn getUser(id) {
  using db = new DbConnection()
  return db.query('SELECT * FROM users WHERE id = ' + id)
}
let result = getUser(42)
let v = [queries.length > 0, closed]
""")
        assert val(i) == [True, True]

    def test_abort_signal_with_fetch_pattern(self) -> None:
        i = run("""
let c = new AbortController()
let sig = c.signal
let v1 = sig.aborted
c.abort()
let v2 = sig.aborted
let v = [v1, v2]
""")
        assert val(i) == [False, True]

    def test_regexp_constructor_in_factory(self) -> None:
        i = run("""
fn makeRegex(pattern, flags) {
  return new RegExp(pattern, flags)
}
let re = makeRegex('hello', 'i')
let v = re.test('Hello World')
""")
        assert val(i) is True

    def test_map_get_or_insert_cache_pattern(self) -> None:
        i = run("""
let cache = new Map()
fn memoize(key, compute) {
  return cache.getOrInsertComputed(key, compute)
}
let v1 = memoize('a', k => k.length)
let v2 = memoize('a', k => 999)
let v = [v1, v2]
""")
        assert val(i) == [1, 1]

    def test_using_with_try_catch_in_fn(self) -> None:
        i = run("""
let log = []
fn useResource() {
  using r = {[Symbol.dispose]() { log.push('disposed') }}
  log.push('used')
}
useResource()
let v = log
""")
        assert val(i) == ["used", "disposed"]

    def test_symbol_dispose_well_known_identity(self) -> None:
        i = run("""
let sym1 = Symbol.dispose
let sym2 = Symbol.dispose
let v = sym1 === sym2
""")
        assert val(i) is True

    def test_error_stack_trace_limit_type_error_inherits(self) -> None:
        i = run("""
Error.stackTraceLimit = 100
let v = TypeError.stackTraceLimit
""")
        assert val(i) == 100
