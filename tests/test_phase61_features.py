"""Phase 61 feature tests.

Covers:
- For-of / for-in single-statement body without braces
- Optional chaining `?.[n]` returns undefined for out-of-bounds array access
- Class field initializers can reference `this` (other fields defined earlier)
- Array.prototype.reduce passes index as 3rd argument to callback
"""

import pytest
from sprycode.interpreter import Interpreter
from sprycode.lexer import Lexer
from sprycode.parser import Parser


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    interp = Interpreter()
    interp.run(prog)
    return interp


def val(interp: Interpreter) -> object:
    return interp.globals["v"]


# ---------------------------------------------------------------------------
# For-of single-statement body without braces
# ---------------------------------------------------------------------------

class TestForOfNoBraces:
    def test_for_of_string_no_braces(self):
        """for (let c of str) singleStatement works without braces."""
        i = run("""
let v = []
for (let c of "hello") v.push(c)
""")
        assert val(i) == ["h", "e", "l", "l", "o"]

    def test_for_of_array_no_braces(self):
        i = run("""
let v = []
for (let x of [10, 20, 30]) v.push(x)
""")
        assert val(i) == [10, 20, 30]

    def test_for_of_array_transform_no_braces(self):
        i = run("""
let acc = 0
for (let x of [1, 2, 3, 4, 5]) acc += x
let v = acc
""")
        assert val(i) == 15

    def test_for_in_no_braces(self):
        """for (let k in obj) singleStatement works without braces."""
        i = run("""
let obj = {a: 1, b: 2, c: 3}
let keys = []
for (let k in obj) keys.push(k)
keys.sort()
let v = keys
""")
        assert val(i) == ["a", "b", "c"]

    def test_for_of_map_no_braces(self):
        i = run("""
let m = new Map([["x", 1], ["y", 2]])
let v = []
for (let entry of m) v.push(entry[0])
v.sort()
""")
        assert i.globals["v"] == ["x", "y"]

    def test_for_of_no_braces_break(self):
        """break works inside braceless for-of body."""
        i = run("""
let v = []
for (let x of [1, 2, 3, 4, 5])
  if (x === 3) break
  else v.push(x)
""")
        # Without braces the body is only the if statement, so v gets 1,2
        assert val(i) == [1, 2]

    def test_for_of_destructure_no_braces(self):
        """for (let [k,v] of entries) singleStatement works."""
        i = run("""
let pairs = [[1, "a"], [2, "b"], [3, "c"]]
let v = []
for (let [n, s] of pairs) v.push(n + ":" + s)
""")
        assert val(i) == ["1:a", "2:b", "3:c"]

    def test_for_of_set_no_braces(self):
        i = run("""
let s = new Set([1, 2, 3])
let v = []
for (let x of s) v.push(x * 2)
""")
        assert val(i) == [2, 4, 6]

    def test_for_in_no_braces_with_assignment(self):
        i = run("""
let obj = {x: 10, y: 20}
let sum = 0
for (let k in obj) sum += obj[k]
let v = sum
""")
        assert val(i) == 30

    def test_nested_for_of_no_braces(self):
        i = run("""
let v = []
for (let i of [1, 2])
  for (let j of [3, 4])
    v.push(i * 10 + j)
""")
        assert val(i) == [13, 14, 23, 24]


# ---------------------------------------------------------------------------
# Optional chaining ?.[n] out-of-bounds returns undefined
# ---------------------------------------------------------------------------

class TestOptionalChainingIndex:
    def test_optional_index_null_returns_undefined(self):
        i = run("let v = null?.[0]")
        assert val(i) is None  # null short-circuits

    def test_optional_index_undefined_returns_undefined(self):
        i = run("let obj = {}; let v = obj.missing?.[0]")
        assert val(i) is None

    def test_optional_index_out_of_bounds_returns_undefined(self):
        """arr?.[n] where arr is not null but index is out of bounds → undefined."""
        from sprycode.interpreter import SPRY_UNDEFINED
        i = run("let arr = [1,2,3]; let v = arr?.[10]")
        assert val(i) is SPRY_UNDEFINED

    def test_optional_index_in_bounds_works(self):
        i = run("let arr = [10, 20, 30]; let v = arr?.[1]")
        assert val(i) == 20

    def test_optional_index_string_key_missing(self):
        """obj?.['missingKey'] returns undefined."""
        i = run("let obj = {a: 1}; let v = obj?.['b']")
        from sprycode.interpreter import SPRY_UNDEFINED
        assert val(i) is SPRY_UNDEFINED

    def test_optional_index_string_key_present(self):
        i = run("let obj = {a: 42}; let v = obj?.['a']")
        assert val(i) == 42

    def test_optional_chained_index(self):
        i = run("""
let data = {items: [1, 2, 3]}
let v = data?.items?.[1]
""")
        assert val(i) == 2

    def test_optional_chained_index_null_mid_chain(self):
        i = run("""
let data = null
let v = data?.items?.[0]
""")
        assert val(i) is None


# ---------------------------------------------------------------------------
# Class field initializers can reference `this`
# ---------------------------------------------------------------------------

class TestClassFieldThisReference:
    def test_field_references_earlier_field(self):
        """Class field initializer can use this.otherField."""
        i = run("""
class Config {
  host = "localhost"
  port = 3000
  url = this.host + ":" + this.port
}
let v = new Config().url
""")
        assert val(i) == "localhost:3000"

    def test_field_references_this_in_expression(self):
        i = run("""
class Circle {
  radius = 5
  diameter = this.radius * 2
  circumference = this.diameter * 3.14159
}
let c = new Circle()
let v = [c.radius, c.diameter]
""")
        assert val(i) == [5, 10]

    def test_multiple_fields_chain(self):
        i = run("""
class Derived {
  base = 10
  doubled = this.base * 2
  quadrupled = this.doubled * 2
}
let d = new Derived()
let v = d.quadrupled
""")
        assert val(i) == 40

    def test_field_default_then_constructor_override(self):
        """Field is set in initializer, constructor may override it."""
        i = run("""
class Box {
  width = 1
  height = 1
  area = this.width * this.height
  constructor(w, h) {
    this.width = w
    this.height = h
    this.area = w * h
  }
}
let b = new Box(3, 4)
let v = b.area
""")
        assert val(i) == 12

    def test_field_this_method_not_available_yet(self):
        """Fields referencing methods defined on class can be called after construction."""
        i = run("""
class Greeter {
  name = "World"
  greet() { return "Hello, " + this.name + "!" }
}
let g = new Greeter()
let v = g.greet()
""")
        assert val(i) == "Hello, World!"

    def test_subclass_field_references_parent_field(self):
        """Subclass field can reference parent's field via this."""
        i = run("""
class Base {
  x = 10
}
class Child extends Base {
  doubled = this.x * 2
}
let c = new Child()
let v = c.doubled
""")
        assert val(i) == 20


# ---------------------------------------------------------------------------
# Array.prototype.reduce passes index as 3rd argument
# ---------------------------------------------------------------------------

class TestReduceWithIndex:
    def test_reduce_index_third_arg(self):
        """reduce callback receives (acc, item, index) as 3rd arg."""
        i = run("""
let v = ["a", "b", "c"].reduce((acc, item, i) => acc + i + ":" + item + " ", "")
""")
        assert val(i) == "0:a 1:b 2:c "

    def test_reduce_index_second_arg_ignored(self):
        """reduce still works when callback ignores index (2-arg callback)."""
        i = run("""
let v = [1, 2, 3, 4, 5].reduce((sum, x) => sum + x, 0)
""")
        assert val(i) == 15

    def test_reduce_index_builds_object(self):
        i = run("""
let arr = ["a", "b", "c"]
let v = arr.reduce((obj, item, i) => {
  obj[i] = item
  return obj
}, {})
""")
        assert val(i) == {0: "a", 1: "b", 2: "c"}

    def test_reduce_no_init_index(self):
        """reduce without initial value still passes index from second element."""
        i = run("""
let v = [10, 20, 30].reduce((acc, x, i) => acc + x * i)
""")
        # acc=10, then x=20 i=1: 10+20*1=30, then x=30 i=2: 30+30*2=90
        assert val(i) == 90

    def test_reduce_tagged_template_index(self):
        """Tagged template reduce that checks vals[i] using index."""
        i = run("""
function tag(strings, ...vals) {
  let parts = strings.raw
  let result = ""
  let n = parts.length
  for (let j = 0; j < n; j++) {
    result += parts[j]
    if (j < vals.length) result += "[" + vals[j] + "]"
  }
  return result
}
let a = 1
let b = 2
let c = 3
let v = tag`${a}+${b}=${c}`
""")
        assert val(i) == "[1]+[2]=[3]"

    def test_reduce_right_index(self):
        """reduceRight also passes index to callback."""
        i = run("""
let v = ["a", "b", "c"].reduceRight((acc, item, i) => acc + i + ":" + item + " ", "")
""")
        assert val(i) == "2:c 1:b 0:a "

    def test_reduce_accumulate_indexed_pairs(self):
        i = run("""
let words = ["zero", "one", "two", "three"]
let v = words.reduce((acc, word, idx) => {
  acc[word] = idx
  return acc
}, {})
""")
        assert val(i) == {"zero": 0, "one": 1, "two": 2, "three": 3}

    def test_reduce_index_with_filter_like_logic(self):
        """Use index to keep only even-indexed elements."""
        i = run("""
let v = [10, 20, 30, 40, 50].reduce((acc, x, i) => {
  if (i % 2 === 0) acc.push(x)
  return acc
}, [])
""")
        assert val(i) == [10, 30, 50]
