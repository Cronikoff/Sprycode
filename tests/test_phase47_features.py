"""Tests for Phase 47 features:
- Symbol as key on plain dicts (IndexAssignment + IndexExpression consistent via str(sym))
- fn.call(thisArg, ...args) and fn.apply(thisArg, args) bind `this` for plain SpryFunctions
- Default values in destructured object function parameters: fn foo({name = 'default'}) {}
- [a, b] = expr destructure assignment at statement level (ASI-like [ line guard in postfix)
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


def val(interp: Interpreter, name: str = "v") -> Any:
    return interp.globals.get(name)


# ---------------------------------------------------------------------------
# 1. Symbol as key on plain dicts
# ---------------------------------------------------------------------------

class TestSymbolKeysOnDicts:
    def test_write_and_read(self) -> None:
        i = run("""
let sym = Symbol('x')
let obj = {}
obj[sym] = 42
let v = obj[sym]
""")
        assert val(i) == 42

    def test_two_symbols_distinct(self) -> None:
        i = run("""
let s1 = Symbol('k')
let s2 = Symbol('k')
let obj = {}
obj[s1] = 'a'
obj[s2] = 'b'
let v = [obj[s1], obj[s2]]
""")
        assert val(i) == ['a', 'b']

    def test_symbol_for_shared_key(self) -> None:
        i = run("""
let sym = Symbol.for('shared')
let obj = {}
obj[sym] = 99
let s2 = Symbol.for('shared')
let v = obj[s2]
""")
        assert val(i) == 99

    def test_overwrite_symbol_key(self) -> None:
        i = run("""
let sym = Symbol('tag')
let obj = {}
obj[sym] = 1
obj[sym] = 2
let v = obj[sym]
""")
        assert val(i) == 2

    def test_symbol_and_string_separate_keys(self) -> None:
        """Symbol key and matching string key are independent."""
        i = run("""
let sym = Symbol('name')
let obj = {name: 'string-val'}
obj[sym] = 'symbol-val'
let v = [obj.name, obj[sym]]
""")
        assert val(i) == ['string-val', 'symbol-val']

    def test_missing_symbol_key_returns_null(self) -> None:
        i = run("""
let sym = Symbol('missing')
let obj = {}
let v = obj[sym]
""")
        assert val(i) is None

    def test_symbol_key_on_existing_object(self) -> None:
        i = run("""
let id = Symbol('id')
let user = {name: 'Alice'}
user[id] = 42
let v = [user.name, user[id]]
""")
        assert val(i) == ['Alice', 42]


# ---------------------------------------------------------------------------
# 2. Function.call / Function.apply with `this` binding
# ---------------------------------------------------------------------------

class TestFunctionCallApplyThis:
    def test_call_no_args(self) -> None:
        i = run("""
fn getX() { return this.x }
let obj = {x: 42}
let v = getX.call(obj)
""")
        assert val(i) == 42

    def test_call_with_args(self) -> None:
        i = run("""
fn greet(msg) { return msg + ', ' + this.name + '!' }
let obj = {name: 'World'}
let v = greet.call(obj, 'Hello')
""")
        assert val(i) == 'Hello, World!'

    def test_call_null_this(self) -> None:
        """call(null) should not crash — this is unbound."""
        i = run("""
fn add(a, b) { return a + b }
let v = add.call(null, 3, 4)
""")
        assert val(i) == 7

    def test_apply_with_args_array(self) -> None:
        i = run("""
fn sum(a, b, c) { return this.base + a + b + c }
let obj = {base: 10}
let v = sum.apply(obj, [1, 2, 3])
""")
        assert val(i) == 16

    def test_apply_null_this(self) -> None:
        i = run("""
fn add(a, b) { return a + b }
let v = add.apply(null, [5, 6])
""")
        assert val(i) == 11

    def test_call_multiple_args(self) -> None:
        i = run("""
fn describe(prefix, suffix) { return prefix + ' ' + this.name + ' ' + suffix }
let obj = {name: 'Alice'}
let v = describe.call(obj, 'Hello,', '!')
""")
        assert val(i) == 'Hello, Alice !'

    def test_method_still_works_normally(self) -> None:
        """Existing method.call(other_instance) still works."""
        i = run("""
class Foo {
  fn init(x) { this.x = x }
  getX() { return this.x }
}
let a = Foo.new(10)
let b = Foo.new(20)
let v = a.getX.call(b)
""")
        assert val(i) == 20

    def test_call_modifies_this(self) -> None:
        i = run("""
fn setVal(v) { this.val = v }
let obj = {val: 0}
setVal.call(obj, 99)
let v = obj.val
""")
        assert val(i) == 99


# ---------------------------------------------------------------------------
# 3. Default values in destructured object function params
# ---------------------------------------------------------------------------

class TestDestructuredFnParamDefaults:
    def test_single_default_applied(self) -> None:
        i = run("""
fn greet({name = 'World'}) { return 'Hello, ' + name + '!' }
let v = greet({})
""")
        assert val(i) == 'Hello, World!'

    def test_provided_value_overrides_default(self) -> None:
        i = run("""
fn greet({name = 'World'}) { return 'Hello, ' + name + '!' }
let v = greet({name: 'Alice'})
""")
        assert val(i) == 'Hello, Alice!'

    def test_null_value_not_replaced_by_default(self) -> None:
        """Explicit null value should not trigger default (JS semantics: only missing key)."""
        i = run("""
fn greet({name = 'World'}) { return 'Hello, ' + name }
let v = greet({name: null})
""")
        # null is explicitly provided, so default should NOT apply; null converted to string "null"
        assert val(i) == 'Hello, null'

    def test_multiple_defaults(self) -> None:
        i = run("""
fn config({host = 'localhost', port = 3000}) {
  return host + ':' + port
}
let v = [config({}), config({host: 'prod.com'}), config({port: 8080})]
""")
        assert val(i) == ['localhost:3000', 'prod.com:3000', 'localhost:8080']

    def test_partial_defaults(self) -> None:
        """Mix of fields with and without defaults."""
        i = run("""
fn connect({host, port = 5432}) {
  return host + ':' + port
}
let v = [connect({host: 'db.local'}), connect({host: 'db.prod', port: 5433})]
""")
        assert val(i) == ['db.local:5432', 'db.prod:5433']

    def test_string_default(self) -> None:
        i = run("""
fn tag({type = 'div', content}) { return '<' + type + '>' + content + '</' + type + '>' }
let v = [tag({content: 'hello'}), tag({type: 'span', content: 'world'})]
""")
        assert val(i) == ['<div>hello</div>', '<span>world</span>']

    def test_number_default(self) -> None:
        i = run("""
fn multiply({a, b = 2}) { return a * b }
let v = [multiply({a: 5}), multiply({a: 5, b: 3})]
""")
        assert val(i) == [10, 15]

    def test_boolean_default(self) -> None:
        i = run("""
fn show({visible = true, label}) { return label + ':' + visible }
let v = [show({label: 'x'}), show({label: 'x', visible: false})]
""")
        assert val(i) == ['x:true', 'x:false']

    def test_default_with_rename(self) -> None:
        i = run("""
fn display({firstName: first, lastName: last = 'Doe'}) {
  return first + ' ' + last
}
let v = [display({firstName: 'John'}), display({firstName: 'Jane', lastName: 'Smith'})]
""")
        assert val(i) == ['John Doe', 'Jane Smith']

    def test_class_method_destructured_defaults(self) -> None:
        i = run("""
class Greeter {
  fn init(prefix) { this.prefix = prefix }
  greet({name = 'stranger', title = ''}) {
    return this.prefix + ' ' + (title ? title + ' ' : '') + name
  }
}
let g = Greeter.new('Hello,')
let v = [g.greet({}), g.greet({name: 'Alice'}), g.greet({name: 'Smith', title: 'Dr.'})]
""")
        assert val(i) == ['Hello, stranger', 'Hello, Alice', 'Hello, Dr. Smith']


# ---------------------------------------------------------------------------
# 4. [a, b] = expr destructure assignment at statement level
# ---------------------------------------------------------------------------

class TestListDestructureAssignmentStatement:
    def test_basic_two_vars(self) -> None:
        i = run("""
var a = 0
var b = 0
[a, b] = [1, 2]
let v = [a, b]
""")
        assert val(i) == [1, 2]

    def test_three_vars(self) -> None:
        i = run("""
var x = 0
var y = 0
var z = 0
[x, y, z] = [10, 20, 30]
let v = [x, y, z]
""")
        assert val(i) == [10, 20, 30]

    def test_swap(self) -> None:
        i = run("""
var a = 1
var b = 2
[a, b] = [b, a]
let v = [a, b]
""")
        assert val(i) == [2, 1]

    def test_assign_after_var_on_prev_line(self) -> None:
        """The ASI fix: [a, b] on a new line is not subscript on previous expression."""
        i = run("""
var a = 0
var b = 0
var c = 3
[a, b] = [c + 1, c + 2]
let v = [a, b]
""")
        assert val(i) == [4, 5]

    def test_rest_in_assignment(self) -> None:
        i = run("""
var first = 0
var rest = []
[first, ...rest] = [1, 2, 3, 4]
let v = [first, rest]
""")
        assert val(i) == [1, [2, 3, 4]]

    def test_from_function_result(self) -> None:
        i = run("""
fn getCoords() { return [3, 4] }
var x = 0
var y = 0
[x, y] = getCoords()
let v = [x, y]
""")
        assert val(i) == [3, 4]

    def test_multiple_rounds(self) -> None:
        """Assign same variables multiple times."""
        i = run("""
var a = 0
var b = 0
[a, b] = [1, 2]
[a, b] = [a + 10, b + 10]
let v = [a, b]
""")
        assert val(i) == [11, 12]

    def test_creates_var_if_missing(self) -> None:
        """Assignment creates the variable if it doesn't exist."""
        i = run("""
[newA, newB] = [100, 200]
let v = [newA, newB]
""")
        assert val(i) == [100, 200]

    def test_subscript_on_same_line_still_works(self) -> None:
        """Same-line [ is still treated as subscript."""
        i = run("""
let arr = [10, 20, 30]
let v = arr[1]
""")
        assert val(i) == 20

    def test_matrix_double_subscript(self) -> None:
        i = run("""
let matrix = [[1,2],[3,4]]
let v = matrix[1][0]
""")
        assert val(i) == 3

    def test_multi_line_method_chain(self) -> None:
        """Multi-line chaining via DOT still works after the ASI fix."""
        i = run("""
let v = [1, 2, 3, 4, 5]
  .filter(x => x % 2 === 0)
  .map(x => x * 10)
""")
        assert val(i) == [20, 40]

    def test_destruct_assign_in_loop(self) -> None:
        i = run("""
var sum = 0
var pairs = [[1,2],[3,4],[5,6]]
for (let pair of pairs) {
  var a = 0
  var b = 0
  [a, b] = pair
  sum = sum + a + b
}
let v = sum
""")
        assert val(i) == 21


# ---------------------------------------------------------------------------
# 5. Real-world integration tests
# ---------------------------------------------------------------------------

class TestPhase47Integration:
    def test_symbol_metadata_pattern(self) -> None:
        """Use Symbol to attach hidden metadata to objects."""
        i = run("""
let META = Symbol('meta')
fn attachMeta(obj, data) { obj[META] = data }
fn getMeta(obj) { return obj[META] }

let user = {name: 'Alice'}
attachMeta(user, {created: 2024, role: 'admin'})
let v = getMeta(user).role
""")
        assert val(i) == 'admin'

    def test_call_for_method_borrowing(self) -> None:
        """Borrow a method from one class and apply to another object."""
        i = run("""
class Validator {
  isValid({minLen = 1, maxLen = 100}) {
    return this.value.length >= minLen && this.value.length <= maxLen
  }
}
let v_obj = new Validator()
let target = {value: 'hello'}
let v = v_obj.isValid.call(target, {minLen: 3, maxLen: 10})
""")
        assert val(i) is True

    def test_destructure_assign_fibonacci(self) -> None:
        """Fibonacci-style swap using destructure assignment."""
        i = run("""
var a = 0
var b = 1
var result = [a, b]
var n = 8
var count = 0
while (count < n) {
  [a, b] = [b, a + b]
  result.push(b)
  count = count + 1
}
let v = result
""")
        # Fibonacci: 0,1,1,2,3,5,8,13,21,34
        expected = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
        assert val(i) == expected

    def test_config_with_all_defaults(self) -> None:
        i = run("""
fn makeServer({
  host = 'localhost',
  port = 3000,
  ssl = false,
  timeout = 30
}) {
  return host + ':' + port
}
let v = makeServer({})
""")
        assert val(i) == 'localhost:3000'

    def test_apply_for_max_of_array(self) -> None:
        """Math.max.apply(null, array) pattern."""
        i = run("""
let nums = [3, 1, 4, 1, 5, 9, 2, 6]
let v = Math.max.apply(null, nums)
""")
        assert val(i) == 9
