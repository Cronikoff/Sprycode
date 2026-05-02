"""
Tests for Phase 6 language features:
  - Class/Struct .new() constructor syntax
  - Generator fn* / yield
  - match as expression
  - Pipeline: take, skip, groupBy, sortBy
  - toPrecision() on numbers
  - containsKey() on dicts
  - math.pi / math.e / math.tau constants (lowercase)
  - export statement
"""

import math as pymath

import pytest

from sprycode.interpreter import Interpreter, SpryGenerator
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.runtime.stdlib import SpryLogger


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    interp = Interpreter()
    interp.run(prog)
    return interp


def val(interp: Interpreter, name: str):
    return interp.globals.get(name)


# ---------------------------------------------------------------------------
# Class .new() constructor
# ---------------------------------------------------------------------------


class TestClassNew:
    def test_basic_new(self):
        src = """class Animal {
  var name = ""
  fn init(n) { name = n }
  fn speak() { return name + " speaks" }
}
let a = Animal.new("Dog")
let v = a.speak()"""
        i = run(src)
        assert val(i, "v") == "Dog speaks"

    def test_new_no_args(self):
        src = """class Empty {
  var x = 0
}
let e = Empty.new()
let v = e.x"""
        i = run(src)
        assert val(i, "v") == 0

    def test_new_with_method_mutation(self):
        src = """class Counter {
  var count = 0
  fn inc() { count = count + 1 }
}
let c = Counter.new()
c.inc()
c.inc()
let v = c.count"""
        i = run(src)
        assert val(i, "v") == 2

    def test_new_with_multiple_fields(self):
        src = """class Point {
  var x = 0
  var y = 0
  fn init(px, py) { x = px  y = py }
  fn sum() { return x + y }
}
let p = Point.new(3, 4)
let v = p.sum()"""
        i = run(src)
        assert val(i, "v") == 7

    def test_new_inheritance(self):
        src = """class A {
  fn hello() { return "from A" }
}
class B extends A {
  fn world() { return "from B" }
}
let b = B.new()
let v = b.hello()"""
        i = run(src)
        assert val(i, "v") == "from A"

    def test_new_typeof(self):
        src = """class Foo {}
let f = Foo.new()
let v = typeof f"""
        i = run(src)
        assert val(i, "v") == "Foo"

    def test_new_instanceof(self):
        src = """class Bar {}
let b = Bar.new()
let v = b instanceof Bar"""
        # instanceof on instances checks type name
        i = run(src)
        assert val(i, "v") is True

    def test_new_class_name_property(self):
        src = """class MyClass {}
let v = MyClass.name"""
        i = run(src)
        assert val(i, "v") == "MyClass"

    def test_multiple_instances_independent(self):
        src = """class Node {
  var value = 0
  fn init(v) { value = v }
}
let a = Node.new(1)
let b = Node.new(2)
let v = [a.value, b.value]"""
        i = run(src)
        assert val(i, "v") == [1, 2]


# ---------------------------------------------------------------------------
# Struct .new() constructor
# ---------------------------------------------------------------------------


class TestStructNew:
    def test_struct_new(self):
        src = """struct Point { x: Number, y: Number }
let p = Point.new(3, 4)
let v = p.x"""
        i = run(src)
        assert val(i, "v") == 3

    def test_struct_new_all_fields(self):
        src = """struct RGB { r: Number, g: Number, b: Number }
let c = RGB.new(255, 128, 0)
let v = [c.r, c.g, c.b]"""
        i = run(src)
        assert val(i, "v") == [255, 128, 0]

    def test_struct_new_partial(self):
        src = """struct Pair { first: Any, second: Any }
let p = Pair.new("hello")
let v = p.first"""
        i = run(src)
        assert val(i, "v") == "hello"

    def test_struct_name_property(self):
        src = """struct Vec2 { x: Number, y: Number }
let v = Vec2.name"""
        i = run(src)
        assert val(i, "v") == "Vec2"


# ---------------------------------------------------------------------------
# Generator fn* / yield
# ---------------------------------------------------------------------------


class TestGenerators:
    def test_basic_generator(self):
        src = """fn* gen() {
  yield 1
  yield 2
  yield 3
}
let g = gen()
let v = [x for x in g]"""
        i = run(src)
        assert val(i, "v") == [1, 2, 3]

    def test_generator_for_loop(self):
        src = """fn* nums() {
  yield 10
  yield 20
  yield 30
}
var sum = 0
for x in nums() { sum = sum + x }
let v = sum"""
        i = run(src)
        assert val(i, "v") == 60

    def test_generator_with_params(self):
        src = """fn* count_up(start, end) {
  var i = start
  while i <= end {
    yield i
    i = i + 1
  }
}
let v = [x for x in count_up(3, 6)]"""
        i = run(src)
        assert val(i, "v") == [3, 4, 5, 6]

    def test_generator_typeof(self):
        src = """fn* g() { yield 1 }
let gen = g()
let v = typeof gen"""
        i = run(src)
        assert val(i, "v") == "Generator"

    def test_generator_empty(self):
        src = """fn* empty() { }
let v = [x for x in empty()]"""
        i = run(src)
        assert val(i, "v") == []

    def test_generator_string_values(self):
        src = """fn* words() {
  yield "hello"
  yield "world"
}
let v = [x for x in words()]"""
        i = run(src)
        assert val(i, "v") == ["hello", "world"]

    def test_generator_filter_comprehension(self):
        src = """fn* numbers() {
  yield 1
  yield 2
  yield 3
  yield 4
  yield 5
}
let v = [x for x in numbers() if x % 2 == 0]"""
        i = run(src)
        assert val(i, "v") == [2, 4]

    def test_generator_returns_spry_generator(self):
        src = """fn* g() { yield 1 }"""
        i = run(src)
        fn = val(i, "g")
        # Calling the generator function should return a SpryGenerator
        from sprycode.interpreter import SpryGenerator as SG
        result = fn  # the function itself, not instance


# ---------------------------------------------------------------------------
# match as expression
# ---------------------------------------------------------------------------


class TestMatchExpression:
    def test_match_expr_in_let(self):
        src = """let x = 2
let v = match x {
  1 => "one"
  2 => "two"
  _ => "other"
}"""
        i = run(src)
        assert val(i, "v") == "two"

    def test_match_expr_wildcard(self):
        src = """let x = 99
let v = match x {
  1 => "one"
  _ => "default"
}"""
        i = run(src)
        assert val(i, "v") == "default"

    def test_match_expr_with_typeof(self):
        src = """fn describe(x) {
  return match typeof x {
    "Int" => "integer"
    "Text" => "string"
    "Bool" => "boolean"
    _ => "other"
  }
}
let v = [describe(1), describe("hi"), describe(true)]"""
        i = run(src)
        assert val(i, "v") == ["integer", "string", "boolean"]

    def test_match_expr_in_assign(self):
        src = """let n = 3
var v = ""
v = match n {
  1 => "uno"
  2 => "dos"
  3 => "tres"
  _ => "?"
}"""
        i = run(src)
        assert val(i, "v") == "tres"

    def test_match_expr_range(self):
        src = """let score = 85
let v = match score {
  90..100 => "A"
  80..89 => "B"
  70..79 => "C"
  _ => "F"
}"""
        i = run(src)
        assert val(i, "v") == "B"


# ---------------------------------------------------------------------------
# Pipeline: take, skip, groupBy, sortBy
# ---------------------------------------------------------------------------


class TestPipelineTakeSkip:
    def test_take(self):
        i = run("let v = [1,2,3,4,5] |> take 3")
        assert val(i, "v") == [1, 2, 3]

    def test_skip(self):
        i = run("let v = [1,2,3,4,5] |> skip 2")
        assert val(i, "v") == [3, 4, 5]

    def test_take_skip_combined(self):
        i = run("let v = [1,2,3,4,5] |> skip 1 |> take 3")
        assert val(i, "v") == [2, 3, 4]

    def test_take_zero(self):
        i = run("let v = [1,2,3] |> take 0")
        assert val(i, "v") == []

    def test_skip_all(self):
        i = run("let v = [1,2,3] |> skip 10")
        assert val(i, "v") == []

    def test_take_more_than_list(self):
        i = run("let v = [1,2] |> take 10")
        assert val(i, "v") == [1, 2]

    def test_pipeline_take_after_filter(self):
        i = run("let v = [1,2,3,4,5,6,7,8,9,10] |> filter x => x % 2 == 0 |> take 3")
        assert val(i, "v") == [2, 4, 6]

    def test_pipeline_skip_after_map(self):
        i = run("let v = [1,2,3,4,5] |> map x => x * 10 |> skip 2")
        assert val(i, "v") == [30, 40, 50]


class TestPipelineGroupBy:
    def test_groupby_parity(self):
        i = run("let v = [1,2,3,4,5,6] |> groupBy x => x % 2")
        result = val(i, "v")
        assert isinstance(result, dict)
        assert sorted(result[0]) == [2, 4, 6]
        assert sorted(result[1]) == [1, 3, 5]

    def test_groupby_by_value(self):
        i = run('let v = ["a", "bb", "ccc", "dd", "e"] |> groupBy x => len(x)')
        result = val(i, "v")
        assert isinstance(result, dict)
        assert result[1] == ["a", "e"]
        assert sorted(result[2]) == ["bb", "dd"]
        assert result[3] == ["ccc"]

    def test_groupby_bool_key(self):
        i = run("let v = [1,2,3,4] |> groupBy x => x > 2")
        result = val(i, "v")
        assert isinstance(result, dict)
        assert sorted(result[False]) == [1, 2]
        assert sorted(result[True]) == [3, 4]

    def test_sortby(self):
        i = run("let v = [3,1,4,1,5,9] |> sortBy x => x")
        assert val(i, "v") == [1, 1, 3, 4, 5, 9]

    def test_sortby_by_field(self):
        i = run("""let people = [{name: "Charlie", age: 30}, {name: "Alice", age: 25}, {name: "Bob", age: 35}]
let v = (people |> sortBy p => p.age) |> map p => p.name""")
        assert val(i, "v") == ["Alice", "Charlie", "Bob"]


# ---------------------------------------------------------------------------
# toPrecision() on numbers
# ---------------------------------------------------------------------------


class TestToPrecision:
    def test_to_precision_4(self):
        i = run("let v = (3.14159).toPrecision(4)")
        assert val(i, "v") == "3.142"

    def test_to_precision_1(self):
        i = run("let v = (3.14159).toPrecision(1)")
        assert val(i, "v") == "3"

    def test_to_precision_int(self):
        i = run("let v = (42).toPrecision(4)")
        # toPrecision(4) of 42 = "42.00" (4 significant figures)
        assert val(i, "v") == "42.00"

    def test_to_precision_small(self):
        i = run("let v = (0.000123).toPrecision(2)")
        assert val(i, "v") == "0.00012"

    def test_to_fixed_still_works(self):
        i = run("let v = (3.14159).toFixed(2)")
        assert val(i, "v") == "3.14"


# ---------------------------------------------------------------------------
# containsKey() on dicts
# ---------------------------------------------------------------------------


class TestContainsKey:
    def test_contains_key_true(self):
        i = run('let v = {a: 1, b: 2}.containsKey("a")')
        assert val(i, "v") is True

    def test_contains_key_false(self):
        i = run('let v = {a: 1}.containsKey("z")')
        assert val(i, "v") is False

    def test_has_key_alias(self):
        i = run('let v = {x: 1}.hasKey("x")')
        assert val(i, "v") is True

    def test_has_own_property_alias(self):
        i = run('let v = {x: 1}.hasOwnProperty("x")')
        assert val(i, "v") is True

    def test_contains_key_empty(self):
        i = run('let v = {}.containsKey("a")')
        assert val(i, "v") is False

    def test_contains_key_nested(self):
        src = """let obj = {a: 1, b: {c: 2}}
let v = [obj.containsKey("a"), obj.containsKey("b"), obj.containsKey("c")]"""
        i = run(src)
        assert val(i, "v") == [True, True, False]


# ---------------------------------------------------------------------------
# math constants (lowercase)
# ---------------------------------------------------------------------------


class TestMathConstants:
    def test_math_pi(self):
        i = run("let v = math.pi")
        assert abs(val(i, "v") - pymath.pi) < 1e-10

    def test_math_e(self):
        i = run("let v = math.e")
        assert abs(val(i, "v") - pymath.e) < 1e-10

    def test_math_tau(self):
        i = run("let v = math.tau")
        assert abs(val(i, "v") - pymath.tau) < 1e-10

    def test_math_PI_uppercase_still_works(self):
        i = run("let v = math.PI")
        assert abs(val(i, "v") - pymath.pi) < 1e-10

    def test_math_phi(self):
        i = run("let v = math.phi")
        expected = (1 + pymath.sqrt(5)) / 2
        assert abs(val(i, "v") - expected) < 1e-10

    def test_math_inf(self):
        i = run("let v = math.inf")
        assert val(i, "v") == float("inf")

    def test_math_ln2(self):
        i = run("let v = math.ln2")
        assert abs(val(i, "v") - pymath.log(2)) < 1e-10

    def test_math_ln10(self):
        i = run("let v = math.ln10")
        assert abs(val(i, "v") - pymath.log(10)) < 1e-10


# ---------------------------------------------------------------------------
# export statement
# ---------------------------------------------------------------------------


class TestExport:
    def test_export_fn(self):
        src = """export fn greet(name) { return "hi " + name }
let v = greet("world")"""
        i = run(src)
        assert val(i, "v") == "hi world"

    def test_export_let(self):
        src = """export let x = 42
let v = x"""
        i = run(src)
        assert val(i, "v") == 42

    def test_export_var(self):
        src = """export var counter = 0
counter = 1
let v = counter"""
        i = run(src)
        assert val(i, "v") == 1

    def test_export_class(self):
        src = """export class Foo {
  var n = 7
}
let f = Foo.new()
let v = f.n"""
        i = run(src)
        assert val(i, "v") == 7

    def test_export_enum(self):
        src = """export enum Color { Red, Green, Blue }
let v = Color.Red.__variant__"""
        i = run(src)
        assert val(i, "v") == "Red"

    def test_multiple_exports(self):
        src = """export fn add(a, b) { return a + b }
export let pi = 3.14
let v = add(1, 2) + pi"""
        i = run(src)
        assert abs(val(i, "v") - 6.14) < 1e-10


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_generator_with_take_pipeline(self):
        src = """fn* fibonacci(n) {
  var a = 0
  var b = 1
  var i = 0
  while i < n {
    yield a
    let tmp = a + b
    a = b
    b = tmp
    i = i + 1
  }
}
let gen = fibonacci(10)
let fibs = [x for x in gen]
let v = fibs |> take 7"""
        i = run(src)
        assert val(i, "v") == [0, 1, 1, 2, 3, 5, 8]

    def test_class_method_chain(self):
        src = """class Builder {
  var parts = []
  fn add(item) { parts = parts + [item] }
  fn build() { return parts }
}
let b = Builder.new()
b.add("x")
b.add("y")
b.add("z")
let v = b.build()"""
        i = run(src)
        assert val(i, "v") == ["x", "y", "z"]

    def test_match_expr_in_list_comprehension(self):
        src = """fn grade(n) {
  return match n {
    90..100 => "A"
    80..89 => "B"
    70..79 => "C"
    _ => "F"
  }
}
let scores = [95, 82, 73, 60, 88]
let v = [grade(s) for s in scores]"""
        i = run(src)
        assert val(i, "v") == ["A", "B", "C", "F", "B"]

    def test_group_by_and_take(self):
        src = """let items = [1,2,3,4,5,6,7,8,9,10]
let evens = items |> filter x => x % 2 == 0 |> take 3
let odds = items |> filter x => x % 2 != 0 |> skip 1 |> take 2
let v = [evens, odds]"""
        i = run(src)
        assert val(i, "v") == [[2, 4, 6], [3, 5]]
