"""Tests for Phase 46 features:
- JS-style string coercion in += compound assignment (CompoundAssignment and CompoundMemberAssignment)
- Destructured arrow/lambda parameters: ([a,b]) => ... and ({name}) => ...
- ...rest params in multi-arg arrow functions: (first, ...rest) => ...
- Object destructuring fn params with rename: fn foo({key: localName}) { }
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
# 1. String += coercion
# ---------------------------------------------------------------------------

class TestCompoundAssignStringCoercion:
    def test_string_plus_int(self) -> None:
        i = run("""
var s = 'n='
s += 42
let v = s
""")
        assert val(i) == 'n=42'

    def test_string_plus_bool(self) -> None:
        i = run("""
var s = ''
s += true
let v = s
""")
        assert val(i) == 'true'

    def test_string_plus_null(self) -> None:
        i = run("""
var s = ''
s += null
let v = s
""")
        assert val(i) == 'null'

    def test_string_plus_float(self) -> None:
        i = run("""
var s = 'val='
s += 3.14
let v = s
""")
        assert val(i) == 'val=3.14'

    def test_int_plus_string(self) -> None:
        # rhs is string, coerce lhs
        i = run("""
var n = 10
n += ' items'
let v = n
""")
        assert val(i) == '10 items'

    def test_chained_string_coercion(self) -> None:
        i = run("""
var s = ''
s += 1
s += true
s += null
let v = s
""")
        assert val(i) == '1truenull'

    def test_pure_number_plus(self) -> None:
        # Numbers should still add numerically
        i = run("""
var x = 10
x += 5
let v = x
""")
        assert val(i) == 15

    def test_no_coerce_between_numbers(self) -> None:
        i = run("""
var x = 1.5
x += 2
let v = x
""")
        assert val(i) == 3.5


class TestCompoundMemberAssignStringCoercion:
    def test_member_string_plus_int(self) -> None:
        i = run("""
var obj = {s: '<b>'}
obj.s += 42
obj.s += '</b>'
let v = obj.s
""")
        assert val(i) == '<b>42</b>'

    def test_member_string_plus_null(self) -> None:
        i = run("""
var obj = {label: 'value='}
obj.label += null
let v = obj.label
""")
        assert val(i) == 'value=null'

    def test_member_numeric_plus(self) -> None:
        i = run("""
var obj = {count: 0}
obj.count += 1
obj.count += 1
let v = obj.count
""")
        assert val(i) == 2

    def test_instance_field_string_plus(self) -> None:
        i = run("""
class Builder {
  fn init() { this.html = '<div>' }
  add(s) { this.html += s }
  build() { return this.html + '</div>' }
}
let b = Builder.new()
b.add('hello')
b.add(42)
let v = b.build()
""")
        assert val(i) == '<div>hello42</div>'


# ---------------------------------------------------------------------------
# 2. Destructured array arrow params
# ---------------------------------------------------------------------------

class TestDestructuredArrayArrowParam:
    def test_map_pair_sum(self) -> None:
        i = run("""
let pairs = [[1,2],[3,4],[5,6]]
let v = pairs.map(([a,b]) => a + b)
""")
        assert val(i) == [3, 7, 11]

    def test_entries_map(self) -> None:
        i = run("""
let v = Object.entries({a:1,b:2,c:3}).map(([k,v]) => k + '=' + v)
""")
        assert val(i) == ['a=1', 'b=2', 'c=3']

    def test_forEach_with_destructure(self) -> None:
        i = run("""
let pairs = [[1,2],[3,4]]
var result = []
pairs.forEach(([a,b]) => {
  result.push(a * b)
})
let v = result
""")
        assert val(i) == [2, 12]

    def test_reduce_with_destructure(self) -> None:
        i = run("""
let pairs = [[1,2],[3,4],[5,6]]
let v = pairs.reduce((sum, [a,b]) => sum + a + b, 0)
""")
        assert val(i) == 21

    def test_mixed_normal_and_destructured(self) -> None:
        i = run("""
let pairs = [[10,20],[30,40]]
let v = pairs.map(([a,b], idx) => idx + ':' + (a+b))
""")
        assert val(i) == ['0:30', '1:70']

    def test_nested_array_destructure(self) -> None:
        i = run("""
let triples = [[1,2,3],[4,5,6]]
let v = triples.map(([a,b,c]) => a + b + c)
""")
        assert val(i) == [6, 15]

    def test_zero_arg_lambda_still_works(self) -> None:
        i = run("""
let arr = [1,2,3]
let v = arr.map(() => 0)
""")
        assert val(i) == [0, 0, 0]

    def test_single_plain_arg_lambda_still_works(self) -> None:
        i = run("""
let v = [1,2,3].map(x => x * 2)
""")
        assert val(i) == [2, 4, 6]


# ---------------------------------------------------------------------------
# 3. Destructured object arrow params
# ---------------------------------------------------------------------------

class TestDestructuredObjectArrowParam:
    def test_map_name(self) -> None:
        i = run("""
let people = [{name:'Alice',age:30},{name:'Bob',age:25}]
let v = people.map(({name}) => name)
""")
        assert val(i) == ['Alice', 'Bob']

    def test_map_multiple_fields(self) -> None:
        i = run("""
let people = [{name:'Alice',age:30},{name:'Bob',age:25}]
let v = people.map(({name,age}) => name + ':' + age)
""")
        assert val(i) == ['Alice:30', 'Bob:25']

    def test_forEach_obj_destruct(self) -> None:
        i = run("""
let items = [{id:1,val:'a'},{id:2,val:'b'}]
var result = []
items.forEach(({id,val}) => {
  result.push(id + '=' + val)
})
let v = result
""")
        assert val(i) == ['1=a', '2=b']

    def test_filter_obj_destruct(self) -> None:
        i = run("""
let people = [{name:'Alice',age:30},{name:'Bob',age:17},{name:'Carol',age:25}]
let v = people.filter(({age}) => age >= 18).map(({name}) => name)
""")
        assert val(i) == ['Alice', 'Carol']

    def test_obj_destruct_missing_field(self) -> None:
        # Missing field becomes null/undefined
        i = run("""
let items = [{a:1}]
let v = items.map(({a,b}) => [a, b])
""")
        result = val(i)
        assert result[0][0] == 1
        assert result[0][1] is None


# ---------------------------------------------------------------------------
# 4. Rest params in arrow functions
# ---------------------------------------------------------------------------

class TestArrowRestParams:
    def test_single_rest(self) -> None:
        i = run("""
let myFn = (...args) => args
let v = myFn(1, 2, 3)
""")
        assert val(i) == [1, 2, 3]

    def test_first_then_rest(self) -> None:
        i = run("""
let myFn = (first, ...rest) => [first, rest]
let v = myFn(1, 2, 3)
""")
        assert val(i) == [1, [2, 3]]

    def test_two_then_rest(self) -> None:
        i = run("""
let myFn = (a, b, ...rest) => a + b + rest.length
let v = myFn(10, 20, 1, 2, 3)
""")
        assert val(i) == 33

    def test_rest_empty(self) -> None:
        i = run("""
let myFn = (a, ...rest) => rest
let v = myFn(1)
""")
        assert val(i) == []


# ---------------------------------------------------------------------------
# 5. Object destructuring fn params (extended)
# ---------------------------------------------------------------------------

class TestObjectDestructureFnParam:
    def test_basic_destruct(self) -> None:
        i = run("""
fn greet({name, greeting}) {
  return greeting + ', ' + name + '!'
}
let v = greet({name: 'Alice', greeting: 'Hello'})
""")
        assert val(i) == 'Hello, Alice!'

    def test_rename_destruct(self) -> None:
        i = run("""
fn display({firstName: first, lastName: last}) {
  return first + ' ' + last
}
let v = display({firstName: 'John', lastName: 'Doe'})
""")
        assert val(i) == 'John Doe'

    def test_partial_destruct(self) -> None:
        i = run("""
fn getId({id}) {
  return id
}
let v = getId({id: 42, name: 'test', extra: true})
""")
        assert val(i) == 42


# ---------------------------------------------------------------------------
# 6. Real-world patterns
# ---------------------------------------------------------------------------

class TestRealWorldPatterns:
    def test_tagged_template_with_forEach(self) -> None:
        """Tagged template that uses forEach to build result."""
        i = run("""
fn tag(strings, ...values) {
  var result = ''
  strings.forEach((str, idx) => {
    result += str
    if (idx < values.length) result += String(values[idx]).toUpperCase()
  })
  return result
}
let name = 'world'
let v = tag`hello ${name}!`
""")
        assert val(i) == 'hello WORLD!'

    def test_object_entries_rebuild(self) -> None:
        """Use entries+destructure to transform an object."""
        i = run("""
let prices = {apple: 1.5, banana: 0.8, cherry: 3.0}
let doubled = Object.fromEntries(
  Object.entries(prices).map(([k,v]) => [k, v * 2])
)
let v = doubled.apple
""")
        assert val(i) == 3.0

    def test_string_builder_pattern(self) -> None:
        """Build a string by accumulating with +=."""
        i = run("""
var html = ''
let items = ['one', 'two', 'three']
items.forEach((item, idx) => {
  html += '<li>' + item + '</li>'
})
let v = html
""")
        assert val(i) == '<li>one</li><li>two</li><li>three</li>'

    def test_map_with_index_and_destruct(self) -> None:
        """Combine index and destructuring in map."""
        i = run("""
let data = [{name:'A',score:90},{name:'B',score:85}]
let v = data.map(({name,score}, i) => i + '. ' + name + '=' + score)
""")
        assert val(i) == ['0. A=90', '1. B=85']
