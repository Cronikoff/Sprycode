"""Phase 26: for let/var of, chained assignment, nested destructuring,
   rest in object destructuring, array.unshift variadic, static field ++/--."""

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


def v(interp: Interpreter, name: str = "v"):
    return interp.globals.get(name)


# ---------------------------------------------------------------------------
# Fix 1: for let/var x of / in
# ---------------------------------------------------------------------------

def test_for_let_of_basic():
    i = run("var v = 0\nfor let x of [1, 2, 3] { v = v + x }")
    assert v(i) == 6


def test_for_var_of_basic():
    i = run("var v = 0\nfor var x of [1, 2, 3] { v = v + x }")
    assert v(i) == 6


def test_for_let_in_basic():
    i = run("var v = 0\nfor let k in {a: 1, b: 2, c: 3} { v = v + 1 }")
    assert v(i) == 3


def test_for_let_of_string():
    i = run('var v = ""\nfor let c of "abc" { v = v + c }')
    assert v(i) == "abc"


def test_for_let_of_range():
    i = run("var v = 0\nfor let i in 0..4 { v = v + i }")
    assert v(i) == 6  # 0+1+2+3


def test_for_var_of_map():
    i = run("var v = 0\nfor let pair of Map.new([['a',1],['b',2]]) { v = v + pair[1] }")
    assert v(i) == 3


def test_for_let_of_generator():
    src = "fn* gen() { yield 1\n yield 2\n yield 3 }\nvar sum = 0\nfor let x of gen() { sum = sum + x }\nlet v = sum"
    i = run(src)
    assert v(i) == 6


# ---------------------------------------------------------------------------
# Fix 2: Chained assignment
# ---------------------------------------------------------------------------

def test_chained_assign_simple():
    i = run("var a = 0\nvar b = 0\na = b = 5\nlet v = a + b")
    assert v(i) == 10


def test_chained_assign_three():
    i = run("var a = 0\nvar b = 0\nvar c = 0\na = b = c = 7\nlet v = a + b + c")
    assert v(i) == 21


def test_chained_member_assign():
    i = run("let o = {x: 0}\nvar b = 0\no.x = 42\nb = o.x\nlet v = b")
    assert v(i) == 42


def test_assignment_as_expr():
    i = run("var a = 0\nvar b = (a = 99)\nlet v = b")
    assert v(i) == 99


# ---------------------------------------------------------------------------
# Fix 3 (parser only): Array destructure assignment [a, b] = [...]
# ---------------------------------------------------------------------------

def test_list_destructure_assign_basic():
    i = run("var a = 0; var b = 0; [a, b] = [1, 2]\nlet v = a + b")
    assert v(i) == 3


def test_list_destructure_assign_with_rest():
    i = run("var a = 0; [a, ...rest] = [1, 2, 3]\nlet v = rest")
    assert v(i) == [2, 3]


# ---------------------------------------------------------------------------
# Fix 4: Nested array destructuring
# ---------------------------------------------------------------------------

def test_nested_array_destruct():
    i = run("let [[a, b], c] = [[1, 2], 3]\nlet v = a + b + c")
    assert v(i) == 6


def test_nested_array_three_deep():
    i = run("let [[[x]]] = [[[42]]]\nlet v = x")
    assert v(i) == 42


def test_nested_array_mixed():
    i = run("let [[a, b], c, d] = [[10, 20], 30, 40]\nlet v = a + b + c + d")
    assert v(i) == 100


def test_nested_obj_in_array():
    i = run("let {a: [x, y]} = {a: [10, 20]}\nlet v = x + y")
    assert v(i) == 30


def test_nested_array_in_obj():
    i = run("let {nums: [first, second]} = {nums: [3, 4]}\nlet v = first + second")
    assert v(i) == 7


# ---------------------------------------------------------------------------
# Fix 5: Rest in object destructuring
# ---------------------------------------------------------------------------

def test_obj_destruct_rest_basic():
    i = run("let {x, ...rest} = {x: 1, y: 2, z: 3}\nlet v = Object.keys(rest)")
    assert sorted(v(i)) == ["y", "z"]


def test_obj_destruct_rest_values():
    i = run("let {a, ...rest} = {a: 1, b: 2, c: 3}\nlet v = rest.b + rest.c")
    assert v(i) == 5


def test_obj_destruct_rest_empty():
    i = run("let {x, ...rest} = {x: 42}\nlet v = Object.keys(rest)")
    assert v(i) == []


def test_var_obj_destruct_rest():
    i = run("var {a, ...rest} = {a: 1, b: 2}\nlet v = rest.b")
    assert v(i) == 2


# ---------------------------------------------------------------------------
# Fix 6: array.unshift variadic
# ---------------------------------------------------------------------------

def test_unshift_single():
    i = run("let a = [2, 3]\na.unshift(1)\nlet v = a")
    assert v(i) == [1, 2, 3]


def test_unshift_multiple():
    i = run("let a = [2, 3]\na.unshift(0, 1)\nlet v = a")
    assert v(i) == [0, 1, 2, 3]


def test_unshift_three_items():
    i = run("let a = [3]\na.unshift(0, 1, 2)\nlet v = a")
    assert v(i) == [0, 1, 2, 3]


def test_unshift_returns_length():
    i = run("let a = [3, 4]\nlet v = a.unshift(1, 2)")
    assert v(i) == 4


def test_unshift_empty_array():
    i = run("let a = []\na.unshift(1, 2, 3)\nlet v = a")
    assert v(i) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Fix 7: Static field ++ / -- on SpryClass
# ---------------------------------------------------------------------------

def test_static_field_postfix_increment():
    src = "class Counter { static var count = 0 }\nCounter.count++\nCounter.count++\nlet v = Counter.count"
    i = run(src)
    assert v(i) == 2


def test_static_field_prefix_increment():
    src = "class Counter { static var count = 0 }\n++Counter.count; ++Counter.count\nlet v = Counter.count"
    i = run(src)
    assert v(i) == 2


def test_static_field_postfix_decrement():
    src = "class Counter { static var count = 10 }\nCounter.count = Counter.count - 1\nlet v = Counter.count"
    i = run(src)
    assert v(i) == 9


def test_static_field_in_method():
    src = """class Counter {
  static var count = 0
  static fn increment() { Counter.count++ }
  static fn get() { return Counter.count }
}
Counter.increment()
Counter.increment()
Counter.increment()
let v = Counter.get()"""
    i = run(src)
    assert v(i) == 3


def test_static_field_increment_returns_old():
    src = "class C { static var n = 5 }\nlet v = C.n++"
    i = run(src)
    assert v(i) == 5
    assert i.globals.get("v") == 5
