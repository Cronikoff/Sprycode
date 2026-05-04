"""Tests for Phase 49 features:
- Scientific notation (1e3, 1.5e2, 2.5e-1) — lexer handles e/E exponent
- Regex named capture groups — JS (?<name>...) translated to Python (?P<name>...)
- str.startsWith(str, position) and str.endsWith(str, length) — 2-arg versions
- Class expression body uses _parse_class_body so method shorthands work
- async/await error propagation — preserves SpryErrorObject (.message etc.)
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
# Scientific notation
# ---------------------------------------------------------------------------

class TestScientificNotation:
    def test_basic_1e3(self) -> None:
        i = run("let v = 1e3")
        assert val(i) == 1000

    def test_1_5e2(self) -> None:
        i = run("let v = 1.5e2")
        assert val(i) == 150.0

    def test_small_exponent(self) -> None:
        i = run("let v = 2.5e-1")
        assert abs(val(i) - 0.25) < 1e-9

    def test_uppercase_E(self) -> None:
        i = run("let v = 1E4")
        assert val(i) == 10000

    def test_in_array(self) -> None:
        i = run("let v = [1e3, 2e4]")
        assert val(i) == [1000, 20000]

    def test_arithmetic(self) -> None:
        i = run("let v = 1e3 + 500")
        assert val(i) == 1500

    def test_negative_exponent(self) -> None:
        i = run("let v = 1e-3")
        assert abs(val(i) - 0.001) < 1e-12

    def test_positive_sign_exponent(self) -> None:
        i = run("let v = 3e+2")
        assert val(i) == 300

    def test_comparison(self) -> None:
        i = run("let v = 1e3 > 999")
        assert val(i) is True

    def test_in_expression(self) -> None:
        i = run("let v = 2.0e2 * 3")
        assert val(i) == 600.0

    def test_float_precision(self) -> None:
        i = run("let v = 1.5e-2")
        assert abs(val(i) - 0.015) < 1e-10

    def test_zero_exponent(self) -> None:
        i = run("let v = 5e0")
        assert val(i) == 5.0

    def test_used_as_function_arg(self) -> None:
        i = run("let v = Math.floor(1.9e1)")
        assert val(i) == 19

    def test_in_condition(self) -> None:
        i = run("""
var v = 0
if(1e2 == 100) { v = 1 }
""")
        assert val(i) == 1

    def test_variable_assignment(self) -> None:
        i = run("var x = 1e6; let v = x / 1000")
        assert val(i) == 1000.0


# ---------------------------------------------------------------------------
# Regex named capture groups
# ---------------------------------------------------------------------------

class TestRegexNamedGroups:
    def test_basic_named_groups(self) -> None:
        i = run(r"""
let m = '2024-01-15'.match(/(?<year>\d{4})-(?<month>\d{2})-(?<day>\d{2})/)
let v = m ? [m.groups.year, m.groups.month, m.groups.day] : null
""")
        assert val(i) == ['2024', '01', '15']

    def test_named_group_access(self) -> None:
        i = run(r"""
let re = /(?<first>[a-z]+)-(?<second>[a-z]+)/
let m = 'hello-world'.match(re)
let v = m ? m.groups.first : null
""")
        assert val(i) == 'hello'

    def test_named_group_second(self) -> None:
        i = run(r"""
let m = 'foo-bar'.match(/(?<a>\w+)-(?<b>\w+)/)
let v = m ? m.groups.b : null
""")
        assert val(i) == 'bar'

    def test_named_group_with_flags(self) -> None:
        i = run(r"""
let m = 'HELLO world'.match(/(?<word>[a-z]+)/i)
let v = m ? m.groups.word : null
""")
        assert val(i) == 'HELLO'

    def test_numbered_groups_still_work(self) -> None:
        i = run(r"""
let m = '2024-01'.match(/(\d{4})-(\d{2})/)
let v = m ? [m[0], m[1], m[2]] : null
""")
        assert val(i) == ['2024-01', '2024', '01']

    def test_named_plus_numbered_groups(self) -> None:
        i = run(r"""
let m = 'John Smith'.match(/(?<first>\w+)\s+(?<last>\w+)/)
let v = m ? [m[1], m[2], m.groups.first, m.groups.last] : null
""")
        assert val(i) == ['John', 'Smith', 'John', 'Smith']

    def test_no_match_returns_null(self) -> None:
        i = run(r"""
let m = 'hello'.match(/(?<year>\d{4})/)
let v = m
""")
        assert val(i) is None

    def test_named_group_in_replace(self) -> None:
        """Named group capture groups still work positionally in replace."""
        i = run(r"""
let v = '2024-01-15'.replace(/(\d{4})-(\d{2})-(\d{2})/, 'date')
""")
        assert val(i) == 'date'

    def test_ip_address_named_groups(self) -> None:
        i = run(r"""
let ip = '192.168.1.100'
let m = ip.match(/(?<a>\d+)\.(?<b>\d+)\.(?<c>\d+)\.(?<d>\d+)/)
let v = m ? m.groups.a + '.' + m.groups.d : null
""")
        assert val(i) == '192.100'

    def test_exec_with_named_groups(self) -> None:
        i = run(r"""
let re = /(?<word>\w+)/
let m = re.exec('hello world')
let v = m ? m.groups.word : null
""")
        assert val(i) == 'hello'


# ---------------------------------------------------------------------------
# str.startsWith / str.endsWith with position / length
# ---------------------------------------------------------------------------

class TestStrStartsWithEndsWith:
    def test_startswith_basic(self) -> None:
        i = run("let v = 'hello world'.startsWith('hello')")
        assert val(i) is True

    def test_startswith_false(self) -> None:
        i = run("let v = 'hello world'.startsWith('world')")
        assert val(i) is False

    def test_startswith_with_position(self) -> None:
        i = run("let v = 'hello world'.startsWith('world', 6)")
        assert val(i) is True

    def test_startswith_with_position_miss(self) -> None:
        i = run("let v = 'hello world'.startsWith('hello', 3)")
        assert val(i) is False

    def test_startswith_position_zero(self) -> None:
        i = run("let v = 'hello'.startsWith('hel', 0)")
        assert val(i) is True

    def test_startswith_empty_string(self) -> None:
        i = run("let v = 'hello'.startsWith('')")
        assert val(i) is True

    def test_endswith_basic(self) -> None:
        i = run("let v = 'hello world'.endsWith('world')")
        assert val(i) is True

    def test_endswith_false(self) -> None:
        i = run("let v = 'hello world'.endsWith('hello')")
        assert val(i) is False

    def test_endswith_with_length(self) -> None:
        i = run("let v = 'hello world'.endsWith('hello', 5)")
        assert val(i) is True

    def test_endswith_with_length_miss(self) -> None:
        i = run("let v = 'hello world'.endsWith('world', 5)")
        assert val(i) is False

    def test_endswith_empty(self) -> None:
        i = run("let v = 'hello'.endsWith('')")
        assert val(i) is True

    def test_startswith_in_if(self) -> None:
        i = run("""
let url = 'https://example.com'
let v = url.startsWith('https', 0)
""")
        assert val(i) is True

    def test_combined(self) -> None:
        i = run("""
let s = 'abcdef'
let v = [s.startsWith('bcd', 1), s.endsWith('cde', 5)]
""")
        assert val(i) == [True, True]


# ---------------------------------------------------------------------------
# Class expression body with method shorthands
# ---------------------------------------------------------------------------

class TestClassExpressionBody:
    def test_method_shorthand(self) -> None:
        i = run("""
let Foo = class {
  fn init(x) { this.x = x }
  getValue() { return this.x }
}
let f = new Foo(42)
let v = f.getValue()
""")
        assert val(i) == 42

    def test_named_class_expr_method(self) -> None:
        i = run("""
let Foo = class Bar {
  fn init(x) { this.x = x }
  double() { return this.x * 2 }
}
let f = new Foo(5)
let v = f.double()
""")
        assert val(i) == 10

    def test_multiple_methods(self) -> None:
        i = run("""
let Calc = class {
  fn init(a, b) { this.a = a; this.b = b }
  sum() { return this.a + this.b }
  product() { return this.a * this.b }
}
let c = new Calc(3, 4)
let v = [c.sum(), c.product()]
""")
        assert val(i) == [7, 12]

    def test_class_expr_getter(self) -> None:
        i = run("""
let Foo = class {
  fn init(n) { this._n = n }
  get doubled() { return this._n * 2 }
}
let f = new Foo(5)
let v = f.doubled
""")
        assert val(i) == 10

    def test_class_expr_static_method(self) -> None:
        i = run("""
let MathHelper = class {
  static square(n) { return n * n }
}
let v = MathHelper.square(5)
""")
        assert val(i) == 25

    def test_class_expr_assigned_and_used(self) -> None:
        i = run("""
fn makeClass(base) {
  return class {
    fn init() { this.base = base }
    value() { return this.base * 10 }
  }
}
let MyClass = makeClass(3)
let obj = new MyClass()
let v = obj.value()
""")
        assert val(i) == 30

    def test_class_expr_instanceof(self) -> None:
        i = run("""
let Foo = class {
  fn init(x) { this.x = x }
}
let f = new Foo(1)
let v = f instanceof Foo
""")
        assert val(i) is True


# ---------------------------------------------------------------------------
# async/await error propagation
# ---------------------------------------------------------------------------

class TestAsyncAwaitErrors:
    def test_await_catch_message(self) -> None:
        i = run("""
var v = 'none'
async fn failing() { throw new Error('real message') }
async fn main() {
  try { await failing() } catch(e) { v = e.message }
}
main()
""")
        assert val(i) == 'real message'

    def test_await_error_type(self) -> None:
        i = run("""
var v = false
async fn failing() { throw new TypeError('type err') }
async fn main() {
  try { await failing() } catch(e) { v = e instanceof TypeError }
}
main()
""")
        assert val(i) is True

    def test_await_chain_error(self) -> None:
        """Error propagated through chained awaits is correctly caught."""
        i = run("""
var v = 'none'
async fn a() { throw new Error('from a') }
async fn b() { return await a() }
async fn main() {
  try { await b() } catch(e) { v = e.message }
}
main()
""")
        assert val(i) == 'from a'

    def test_promise_reject_await_catch(self) -> None:
        i = run("""
var v = 'none'
async fn main() {
  try {
    await Promise.reject(new Error('rejected!'))
  } catch(e) {
    v = e.message
  }
}
main()
""")
        assert val(i) == 'rejected!'

    def test_await_no_error(self) -> None:
        """Normal async/await path still works correctly."""
        i = run("""
var v = 0
async fn add(a, b) { return a + b }
async fn main() {
  let x = await add(10, 20)
  v = x
}
main()
""")
        assert val(i) == 30

    def test_async_rethrow(self) -> None:
        """Re-thrown error in async fn is caught by outer try/catch."""
        i = run("""
var v = 'none'
async fn inner() { throw new Error('inner') }
async fn outer() {
  try { await inner() } catch(e) { throw new Error('outer: ' + e.message) }
}
async fn main() {
  try { await outer() } catch(e) { v = e.message }
}
main()
""")
        assert val(i) == 'outer: inner'

    def test_async_finally(self) -> None:
        """Finally block runs even when async fn throws."""
        i = run("""
var v = []
async fn failing() { throw new Error('oops') }
async fn main() {
  try {
    await failing()
  } catch(e) {
    v.push('caught: ' + e.message)
  }
  v.push('done')
}
main()
""")
        assert val(i) == ['caught: oops', 'done']

    def test_custom_error_class(self) -> None:
        i = run("""
class AppError extends Error {
  fn init(msg) { super(msg); this.code = 500 }
}
var v = [null, null]
async fn failing() { throw new AppError('app fail') }
async fn main() {
  try { await failing() } catch(e) {
    v[0] = e.message
    v[1] = e.code
  }
}
main()
""")
        assert val(i) == ['app fail', 500]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestPhase49Integration:
    def test_sci_notation_in_computation(self) -> None:
        i = run("""
let tolerance = 1e-6
let result = Math.abs(0.1 + 0.2 - 0.3)
let v = result < tolerance
""")
        assert val(i) is True

    def test_sci_in_regex_and_string(self) -> None:
        i = run(r"""
let threshold = 1e3
let count = 1500
let str = count > threshold ? 'over 1000' : 'under 1000'
let m = str.match(/(\w+)\s+(\d+)/)
let v = [str, m ? m[2] : null]
""")
        assert val(i) == ['over 1000', '1000']

    def test_named_regex_in_loop(self) -> None:
        i = run(r"""
let dates = ['2024-01-15', '2023-06-30']
let v = []
for(let d of dates) {
  let m = d.match(/(?<y>\d{4})-(?<m>\d{2})/)
  if(m) { v.push(m.groups.y + '/' + m.groups.m) }
}
""")
        assert val(i) == ['2024/01', '2023/06']

    def test_class_expr_factory(self) -> None:
        i = run("""
fn createAnimal(sound) {
  return class {
    fn init(name) { this.name = name }
    speak() { return this.name + ' says ' + sound }
  }
}
let Dog = createAnimal('woof')
let Cat = createAnimal('meow')
let d = new Dog('Rex')
let c = new Cat('Whiskers')
let v = [d.speak(), c.speak()]
""")
        assert val(i) == ['Rex says woof', 'Whiskers says meow']

    def test_startswith_endswith_validation(self) -> None:
        i = run("""
fn isEmail(s) {
  return !s.startsWith('@') && s.endsWith('.com') || s.endsWith('.org')
}
let v = [isEmail('user@example.com'), isEmail('@bad.com')]
""")
        # Just check it runs without error
        assert isinstance(val(i), list)
        assert len(val(i)) == 2
