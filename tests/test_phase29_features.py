"""Phase 29 feature tests.

Covers:
- Fix 1: `+` operator coerces SpryInstance to string via toString() 
- Fix 2: generator.throw(err) injects error into generator's try/catch
- Fix 3: Array.from({length, "0": x, ...}) — array-like objects with numeric string keys
- Fix 4: Array destructure holes: let [a, , b] = [1, 2, 3]
- Fix 5: for let [a, b] of list — array destructuring pattern in for-of loop variable
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
# Fix 1: + operator coerces SpryInstance to string via toString()
# ---------------------------------------------------------------------------

class TestToStringCoercion:
    def test_string_plus_instance(self):
        src = """class T { fn toString() { return "world" } }
let t = T.new()
let v = "hello " + t"""
        assert val(run(src), "v") == "hello world"

    def test_instance_plus_string(self):
        src = """class N { fn toString() { return "42" } }
let v = N.new() + " items" """
        assert val(run(src), "v") == "42 items"

    def test_toString_with_field(self):
        src = """class Point {
  fn init(x, y) { self.x = x\n self.y = y }
  fn toString() { return "(" + self.x + "," + self.y + ")" }
}
let v = "Point: " + Point.new(1, 2)"""
        assert val(run(src), "v") == "Point: (1,2)"

    def test_string_plus_number(self):
        assert val(run('let v = "x=" + 5'), "v") == "x=5"

    def test_number_plus_string(self):
        assert val(run('let v = 5 + " items"'), "v") == "5 items"

    def test_string_plus_bool(self):
        assert val(run('let v = "flag=" + true'), "v") == "flag=true"

    def test_string_plus_null(self):
        assert val(run('let v = "val=" + null'), "v") == "val=null"

    def test_multiple_concat(self):
        src = """class T { fn toString() { return "X" } }
let t = T.new()
let v = "a" + t + "b" """
        assert val(run(src), "v") == "aXb"

    def test_number_plus_non_string_not_affected(self):
        # Normal number addition still works
        assert val(run("let v = 2 + 3"), "v") == 5

    def test_string_plus_string_not_affected(self):
        assert val(run('let v = "a" + "b"'), "v") == "ab"


# ---------------------------------------------------------------------------
# Fix 2: generator.throw(err) injects error into generator
# ---------------------------------------------------------------------------

class TestGeneratorThrow:
    def test_throw_caught_by_try_catch_in_generator(self):
        src = """fn* g() {
  try { yield 1 } catch e { yield e.message }
}
let it = g()
it.next()
let r = it.throw(Error.new("boom"))
let v = r.value"""
        assert val(run(src), "v") == "boom"

    def test_throw_done_false_when_caught(self):
        src = """fn* g() {
  try { yield 1 } catch e { yield "caught" }
}
let it = g()
it.next()
let r = it.throw(Error.new("oops"))
let v = r.done"""
        assert val(run(src), "v") is False

    def test_throw_propagates_when_uncaught(self):
        src = """fn* g() { yield 1 }
let it = g()
it.next()
var v = "no error"
try { it.throw(Error.new("x")) } catch e { v = "caught" }"""
        assert val(run(src), "v") == "caught"

    def test_throw_with_custom_message(self):
        src = """fn* gen() {
  try { yield 0 } catch err { yield err.message + "!" }
}
let it = gen()
it.next()
let r = it.throw(Error.new("test"))
let v = r.value"""
        assert val(run(src), "v") == "test!"

    def test_return_still_works(self):
        src = """fn* g() { yield 1\n yield 2 }
let it = g()
it.next()
let r = it.return(99)
let v = r.value"""
        assert val(run(src), "v") == 99


# ---------------------------------------------------------------------------
# Fix 3: Array.from array-like objects {length, "0": x, "1": y, ...}
# ---------------------------------------------------------------------------

class TestArrayFromArrayLike:
    def test_basic_arraylike(self):
        src = 'let al = {"length": 2, "0": "a", "1": "b"}\nlet v = Array.from(al)'
        assert val(run(src), "v") == ["a", "b"]

    def test_arraylike_with_numbers(self):
        src = 'let al = {"length": 3, "0": 10, "1": 20, "2": 30}\nlet v = Array.from(al)'
        assert val(run(src), "v") == [10, 20, 30]

    def test_arraylike_length_zero(self):
        src = 'let al = {"length": 0}\nlet v = Array.from(al)'
        assert val(run(src), "v") == []

    def test_arraylike_missing_key_is_null(self):
        # {length: 3, "0": "a"} — missing "1" and "2" should be null
        src = 'let al = {"length": 3, "0": "a"}\nlet v = Array.from(al)'
        assert val(run(src), "v") == ["a", None, None]

    def test_arraylike_with_mapfn(self):
        src = 'let al = {"length": 3, "0": 1, "1": 2, "2": 3}\nlet v = Array.from(al, x => x * 2)'
        assert val(run(src), "v") == [2, 4, 6]

    def test_string_still_works(self):
        assert val(run('let v = Array.from("abc")'), "v") == ["a", "b", "c"]

    def test_list_still_works(self):
        assert val(run("let v = Array.from([1, 2, 3])"), "v") == [1, 2, 3]


# ---------------------------------------------------------------------------
# Fix 4: Array destructure holes [a, , b]
# ---------------------------------------------------------------------------

class TestArrayDestructureHoles:
    def test_skip_middle_element(self):
        i = run("let [a, , b] = [1, 2, 3]\nlet v = a + b")
        assert val(i, "v") == 4

    def test_skip_first_element(self):
        i = run("let [, b] = [10, 20]\nlet v = b")
        assert val(i, "v") == 20

    def test_skip_multiple(self):
        i = run("let [a, , , d] = [1, 2, 3, 4]\nlet v = a + d")
        assert val(i, "v") == 5

    def test_hole_at_end(self):
        # Hole at end just means last element is skipped (no variable bound)
        i = run("let [a, b, ] = [1, 2, 3]\nlet v = a + b")
        assert val(i, "v") == 3

    def test_no_binding_for_hole(self):
        # Hole variable should not be defined
        src = "let [a, , b] = [1, 2, 3]"
        i = run(src)
        assert val(i, "a") == 1
        assert val(i, "b") == 3

    def test_with_default_after_hole(self):
        i = run("let [a, , b = 99] = [1, 2]\nlet v = b")
        assert val(i, "v") == 99

    def test_hole_with_rest(self):
        i = run("let [a, , ...rest] = [1, 2, 3, 4]\nlet v = rest")
        assert val(i, "v") == [3, 4]


# ---------------------------------------------------------------------------
# Fix 5: for let [a, b] of list — array destructuring in for-of
# ---------------------------------------------------------------------------

class TestForOfArrayDestructure:
    def test_basic_for_of_array_destruct(self):
        src = """var v = 0
for let [a, b] of [[1,2],[3,4]] { v = v + a + b }"""
        assert val(run(src), "v") == 10  # (1+2)+(3+4)

    def test_for_of_array_destruct_multiply(self):
        src = """var v = 0
for let [a, b] of [[2,3],[4,5]] { v = v + a * b }"""
        assert val(run(src), "v") == 26  # 2*3 + 4*5

    def test_for_of_array_destruct_without_let(self):
        src = """var v = 0
for [a, b] of [[1,2],[3,4]] { v = v + a + b }"""
        assert val(run(src), "v") == 10

    def test_for_of_array_destruct_strings(self):
        src = """var v = ""
for let [key, val] of [["a","1"],["b","2"]] { v = v + key + "=" + val + "," }"""
        assert val(run(src), "v") == "a=1,b=2,"

    def test_for_of_map_entries(self):
        src = """let m = Map.new()
m.set("x", 10)
m.set("y", 20)
var v = 0
for let [k, val] of m { v = v + val }"""
        assert val(run(src), "v") == 30

    def test_for_of_array_destruct_3_elements(self):
        src = """var v = 0
for let [a, b, c] of [[1,2,3],[4,5,6]] { v = v + a + b + c }"""
        assert val(run(src), "v") == 21  # 1+2+3+4+5+6

    def test_for_of_with_hole(self):
        src = """var v = 0
for let [a, , c] of [[1,2,3],[4,5,6]] { v = v + a + c }"""
        assert val(run(src), "v") == 14  # (1+3)+(4+6)
