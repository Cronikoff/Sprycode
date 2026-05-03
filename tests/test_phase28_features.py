"""Phase 28 feature tests.

Covers:
- Fix 1: >>> / << / >> operator precedence (shift tighter than comparison)
- Fix 2: fn [Symbol.iterator]() computed method in class body (with fn keyword)
- Fix 3: Object.create tracks prototype; Object.getPrototypeOf returns it
- Fix 4: Spread [...set], [...map], [...string], and spread into function args
- Fix 5: _iter_to_list / _consume_iterator — for..of and spread over custom iterables
"""

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


def val(i: Interpreter, name: str):
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# Fix 1: Shift operator precedence  (<<, >>, >>> must bind tighter than < > ==)
# ---------------------------------------------------------------------------

class TestShiftPrecedence:
    def test_unsigned_right_shift_gt_comparison(self):
        # -1 >>> 0 produces 4294967295, which is > 0
        i = run("let v = -1 >>> 0 > 0")
        assert val(i, "v") is True

    def test_left_shift_gt_comparison(self):
        # (1 << 2) > 0  =  4 > 0  = True
        i = run("let v = 1 << 2 > 0")
        assert val(i, "v") is True

    def test_right_shift_eq_comparison(self):
        # (8 >> 1) == 4  = True
        i = run("let v = 8 >> 1 == 4")
        assert val(i, "v") is True

    def test_shift_in_complex_expression(self):
        # In JS, addition (prec 12) is tighter than shift (prec 11)
        # so  2 << 3 + 1  ==  2 << (3+1)  ==  2 << 4  ==  32
        i = run("let v = 2 << 3 + 1")
        assert val(i, "v") == 32  # 2 << 4 = 32

    def test_unsigned_shift_value(self):
        # -1 >>> 0 = 4294967295
        i = run("let v = -1 >>> 0")
        assert val(i, "v") == 4294967295

    def test_shift_within_bitwise_and(self):
        # (1 << 2) & 7  =  4 & 7 = 4
        i = run("let v = 1 << 2 & 7")
        assert val(i, "v") == 4


# ---------------------------------------------------------------------------
# Fix 2: fn [Symbol.iterator]() in class body
# ---------------------------------------------------------------------------

class TestComputedMethodFnSyntax:
    def test_fn_symbol_iterator_spread(self):
        src = """
class Counter {
  fn init(max) { self.max = max }
  fn [Symbol.iterator]() {
    var i = 0
    let max = self.max
    return {
      next: () => {
        if i < max {
          let v = i
          i = i + 1
          return {value: v, done: false}
        } else {
          return {value: null, done: true}
        }
      }
    }
  }
}
let v = [...Counter.new(4)]
"""
        i = run(src)
        assert val(i, "v") == [0, 1, 2, 3]

    def test_fn_symbol_iterator_for_of(self):
        src = """
class Range {
  fn init(n) { self.n = n }
  fn [Symbol.iterator]() {
    var i = 0
    let n = self.n
    return {
      next: () => {
        if i < n {
          let r = {value: i, done: false}
          i = i + 1
          return r
        } else {
          return {value: null, done: true}
        }
      }
    }
  }
}
var v = 0
for let x of Range.new(5) { v = v + x }
"""
        i = run(src)
        assert val(i, "v") == 10  # 0+1+2+3+4

    def test_fn_symbol_iterator_destructure(self):
        src = """
class Pair {
  fn init(a, b) { self.a = a\n self.b = b }
  fn [Symbol.iterator]() {
    let items = [self.a, self.b]
    var idx = 0
    return {
      next: () => {
        if idx < 2 { let r = {value: items[idx], done: false}\n idx = idx + 1\n return r }
        else { return {value: null, done: true} }
      }
    }
  }
}
let [x, y] = [...Pair.new(10, 20)]
let v = x + y
"""
        i = run(src)
        assert val(i, "v") == 30

    def test_computed_bracket_syntax_still_works(self):
        # The no-fn-keyword [Symbol.iterator]() syntax should still work
        src = """
class Seq {
  fn init(n) { self.n = n }
  [Symbol.iterator]() {
    var i = 0
    let n = self.n
    return {
      next: () => {
        if i < n { let r = {value: i * 2, done: false}\n i = i + 1\n return r }
        else { return {value: null, done: true} }
      }
    }
  }
}
let v = [...Seq.new(3)]
"""
        i = run(src)
        assert val(i, "v") == [0, 2, 4]


# ---------------------------------------------------------------------------
# Fix 3: Object.create / Object.getPrototypeOf
# ---------------------------------------------------------------------------

class TestObjectPrototype:
    def test_create_copies_proto_fields(self):
        i = run("let proto = {x: 42}\nlet obj = Object.create(proto)\nlet v = obj.x")
        assert val(i, "v") == 42

    def test_getPrototypeOf_created_object(self):
        i = run("let proto = {y: 99}\nlet obj = Object.create(proto)\nlet v = Object.getPrototypeOf(obj) != null")
        assert val(i, "v") is True

    def test_getPrototypeOf_returns_proto(self):
        i = run("let proto = {z: 7}\nlet obj = Object.create(proto)\nlet v = Object.getPrototypeOf(obj).z")
        assert val(i, "v") == 7

    def test_getPrototypeOf_plain_object_is_null(self):
        # Plain objects (not created with Object.create) return None
        i = run("let v = Object.getPrototypeOf({a: 1})")
        assert val(i, "v") is None

    def test_proto_chain_method_access(self):
        i = run("""let proto = {greet: () => "hello"}
let obj = Object.create(proto)
let v = obj.greet()""")
        assert val(i, "v") == "hello"


# ---------------------------------------------------------------------------
# Fix 4: Spread over SprySet, SpryMap, strings
# ---------------------------------------------------------------------------

class TestSpreadIterables:
    def test_spread_set_into_array(self):
        i = run("let s = Set.new([1, 2, 3])\nlet v = [...s]")
        assert sorted(val(i, "v")) == [1, 2, 3]

    def test_spread_set_no_duplicates(self):
        i = run("let s = Set.new([1, 2, 2, 3, 3])\nlet v = [...s]")
        assert sorted(val(i, "v")) == [1, 2, 3]

    def test_spread_map_into_array(self):
        i = run("let m = Map.new()\nm.set(\"a\", 1)\nm.set(\"b\", 2)\nlet v = [...m]")
        assert val(i, "v") == [["a", 1], ["b", 2]]

    def test_spread_string_into_array(self):
        i = run('let v = [..."abc"]')
        assert val(i, "v") == ["a", "b", "c"]

    def test_spread_set_concat(self):
        i = run("let s = Set.new([3, 4])\nlet v = [1, 2, ...s]")
        assert val(i, "v") == [1, 2, 3, 4]

    def test_spread_map_in_function_args(self):
        # Spread map entries into a function call is valid
        i = run("let m = Map.new()\nm.set(\"x\", 10)\nlet v = [...m].length")
        assert val(i, "v") == 1

    def test_spread_generator_into_array(self):
        i = run("fn* gen() { yield 1\n yield 2\n yield 3 }\nlet v = [...gen()]")
        assert val(i, "v") == [1, 2, 3]

    def test_spread_nested_sets(self):
        i = run("let s1 = Set.new([1])\nlet s2 = Set.new([2, 3])\nlet v = [...s1, ...s2]")
        assert val(i, "v") == [1, 2, 3]


# ---------------------------------------------------------------------------
# Fix 5: _iter_to_list — for..of spread over various custom iterables
# ---------------------------------------------------------------------------

class TestIterToList:
    def test_for_of_set(self):
        i = run("let s = Set.new([10, 20, 30])\nvar v = 0\nfor let x of s { v = v + x }")
        assert val(i, "v") == 60

    def test_for_of_map_entries(self):
        i = run("let m = Map.new()\nm.set(\"a\", 1)\nm.set(\"b\", 2)\nvar v = 0\nfor let entry of m { v = v + entry[1] }")
        assert val(i, "v") == 3

    def test_spread_existing_list(self):
        i = run("let a = [4, 5, 6]\nlet v = [...a]")
        assert val(i, "v") == [4, 5, 6]

    def test_for_of_custom_iterator_sum(self):
        src = """
class Fibonacci {
  fn init(count) { self.count = count }
  fn [Symbol.iterator]() {
    var a = 0
    var b = 1
    var n = self.count
    return {
      next: () => {
        if n > 0 {
          let r = {value: a, done: false}
          let tmp = a + b
          a = b
          b = tmp
          n = n - 1
          return r
        } else {
          return {value: null, done: true}
        }
      }
    }
  }
}
let v = [...Fibonacci.new(6)]
"""
        i = run(src)
        assert val(i, "v") == [0, 1, 1, 2, 3, 5]
