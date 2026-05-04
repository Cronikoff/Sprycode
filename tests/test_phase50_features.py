"""Tests for Phase 50 features:
- `let` is mutable (reassignable like JS); only `const` stays immutable
- `str.matchAll` returns SpryRegexMatch objects with `.groups` dict
- *[Symbol.iterator]() generator computed method in class body
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
# let is mutable (reassignable)
# ---------------------------------------------------------------------------

class TestLetMutable:
    def test_let_basic_reassign(self) -> None:
        i = run("let a = 0; a = 5; let v = a")
        assert val(i) == 5

    def test_let_increment(self) -> None:
        i = run("let a = 0; a++; let v = a")
        assert val(i) == 1

    def test_let_decrement(self) -> None:
        i = run("let a = 5; a--; let v = a")
        assert val(i) == 4

    def test_let_plus_assign(self) -> None:
        i = run("let a = 5; a += 3; let v = a")
        assert val(i) == 8

    def test_let_minus_assign(self) -> None:
        i = run("let a = 10; a -= 3; let v = a")
        assert val(i) == 7

    def test_let_logical_or_assign(self) -> None:
        i = run("let a = 0; a ||= 10; let v = a")
        assert val(i) == 10

    def test_let_logical_or_assign_truthy(self) -> None:
        i = run("let b = 5; b ||= 99; let v = b")
        assert val(i) == 5

    def test_let_logical_and_assign(self) -> None:
        i = run("let a = 5; a &&= 10; let v = a")
        assert val(i) == 10

    def test_let_logical_and_assign_falsy(self) -> None:
        i = run("let b = 0; b &&= 99; let v = b")
        assert val(i) == 0

    def test_let_nullish_assign(self) -> None:
        i = run("let a = null; a ??= 42; let v = a")
        assert val(i) == 42

    def test_let_nullish_assign_non_null(self) -> None:
        i = run("let b = 5; b ??= 99; let v = b")
        assert val(i) == 5

    def test_let_in_while_loop(self) -> None:
        i = run("""
let v = 0
let i = 0
while(i < 5) { v += i; i++ }
""")
        assert val(i) == 10

    def test_let_closure_capture_mutable(self) -> None:
        i = run("""
fn makeCounter() {
  let count = 0
  return {
    increment() { count++; return count },
    get() { return count }
  }
}
let counter = makeCounter()
counter.increment()
counter.increment()
counter.increment()
let v = counter.get()
""")
        assert val(i) == 3

    def test_let_in_for_of_closure(self) -> None:
        """Each for-of iteration captures its own binding."""
        i = run("""
let fns = []
for(let x of [10, 20, 30]) {
  fns.push(() => x)
}
let v = fns.map(f => f())
""")
        assert val(i) == [10, 20, 30]

    def test_let_destructure_reassignable(self) -> None:
        i = run("""
let [x, y] = [1, 2]
x = 10
y = 20
let v = [x, y]
""")
        assert val(i) == [10, 20]

    def test_let_object_destruct_reassignable(self) -> None:
        i = run("""
let {a, b} = {a: 1, b: 2}
a = 10
let v = [a, b]
""")
        assert val(i) == [10, 2]

    def test_let_multiple_decls_reassignable(self) -> None:
        i = run("""
let a = 1, b = 2
a = 10
b = 20
let v = [a, b]
""")
        assert val(i) == [10, 20]


# ---------------------------------------------------------------------------
# const stays immutable
# ---------------------------------------------------------------------------

class TestConstImmutable:
    def test_const_immutable(self) -> None:
        with pytest.raises(Exception):
            run("const x = 42; x = 99")

    def test_const_value_accessible(self) -> None:
        i = run("const PI = 3.14159; let v = PI")
        assert abs(val(i) - 3.14159) < 1e-9

    def test_const_prevents_increment(self) -> None:
        with pytest.raises(Exception):
            run("const x = 0; x++")

    def test_const_prevents_compound_assign(self) -> None:
        with pytest.raises(Exception):
            run("const x = 5; x += 3")

    def test_const_in_try_catch(self) -> None:
        i = run("""
const PI = 3.14
var v = false
try { PI = 99 } catch(e) { v = true }
""")
        assert val(i) is True

    def test_const_multiple_decls_immutable(self) -> None:
        with pytest.raises(Exception):
            run("const a = 1, b = 2; a = 10")


# ---------------------------------------------------------------------------
# str.matchAll returns SpryRegexMatch with .groups
# ---------------------------------------------------------------------------

class TestMatchAllGroups:
    def test_matchall_named_groups(self) -> None:
        i = run(r"""
let v = []
for(let m of 'one1two2three3'.matchAll(/(?<word>[a-z]+)(?<num>\d)/g)) {
  v.push(m.groups.word + ':' + m.groups.num)
}
""")
        assert val(i) == ['one:1', 'two:2', 'three:3']

    def test_matchall_index_groups(self) -> None:
        i = run(r"""
let matches = [...'foo1 foo2 foo3'.matchAll(/foo(\d)/g)]
let v = matches.map(m => m[1])
""")
        assert val(i) == ['1', '2', '3']

    def test_matchall_full_match(self) -> None:
        i = run(r"""
let matches = [...'cat bat sat'.matchAll(/[a-z]at/g)]
let v = matches.map(m => m[0])
""")
        assert val(i) == ['cat', 'bat', 'sat']

    def test_matchall_multiple_named_groups(self) -> None:
        i = run(r"""
let dates = '2024-01-15 and 2023-06-30'
let v = []
for(let m of dates.matchAll(/(?<y>\d{4})-(?<mo>\d{2})-(?<d>\d{2})/g)) {
  v.push(m.groups.y + '/' + m.groups.mo)
}
""")
        assert val(i) == ['2024/01', '2023/06']

    def test_matchall_no_groups(self) -> None:
        i = run(r"""
let v = [...'aabbcc'.matchAll(/(.)\1/g)].map(m => m[0])
""")
        assert val(i) == ['aa', 'bb', 'cc']

    def test_matchall_empty_result(self) -> None:
        i = run(r"""
let v = [...'hello'.matchAll(/\d+/g)]
""")
        assert val(i) == []

    def test_matchall_mixed_positional_named(self) -> None:
        i = run(r"""
let m = [...'John Smith'.matchAll(/(?<first>\w+)\s+(?<last>\w+)/g)][0]
let v = [m[1], m[2], m.groups.first, m.groups.last]
""")
        assert val(i) == ['John', 'Smith', 'John', 'Smith']

    def test_matchall_index_property(self) -> None:
        i = run(r"""
let matches = [...'ab cd ef'.matchAll(/\w+/g)]
let v = matches.map(m => m.index)
""")
        assert val(i) == [0, 3, 6]

    def test_matchall_spread_operator(self) -> None:
        i = run(r"""
let v = [...'1 22 333'.matchAll(/(\d+)/g)].length
""")
        assert val(i) == 3


# ---------------------------------------------------------------------------
# *[Symbol.iterator]() generator computed method
# ---------------------------------------------------------------------------

class TestGeneratorComputedMethod:
    def test_basic_range_spread(self) -> None:
        i = run("""
class Range {
  fn init(s, e) { this.s = s; this.e = e }
  *[Symbol.iterator]() {
    for(let i = this.s; i <= this.e; i++) { yield i }
  }
}
let v = [...new Range(1, 5)]
""")
        assert val(i) == [1, 2, 3, 4, 5]

    def test_basic_range_for_of(self) -> None:
        i = run("""
class Range {
  fn init(s, e) { this.s = s; this.e = e }
  *[Symbol.iterator]() {
    for(let i = this.s; i <= this.e; i++) { yield i }
  }
}
let v = []
for(let x of new Range(0, 3)) { v.push(x) }
""")
        assert val(i) == [0, 1, 2, 3]

    def test_fibonacci_generator(self) -> None:
        i = run("""
class Fibonacci {
  fn init(max) { this.max = max }
  *[Symbol.iterator]() {
    let a = 0
    let b = 1
    while(a <= this.max) {
      yield a
      let tmp = a + b
      a = b
      b = tmp
    }
  }
}
let v = [...new Fibonacci(20)]
""")
        assert val(i) == [0, 1, 1, 2, 3, 5, 8, 13]

    def test_generator_iter_with_map(self) -> None:
        i = run("""
class Step {
  fn init(start, step, count) { this.start = start; this.step = step; this.count = count }
  *[Symbol.iterator]() {
    let v2 = this.start
    let remaining = this.count
    while(remaining-- > 0) { yield v2; v2 += this.step }
  }
}
let v = [...new Step(0, 5, 4)]
""")
        assert val(i) == [0, 5, 10, 15]

    def test_destructure_from_custom_iter(self) -> None:
        i = run("""
class Triple {
  fn init(x) { this.x = x }
  *[Symbol.iterator]() { yield this.x; yield this.x * 2; yield this.x * 3 }
}
let [a, b, c] = new Triple(3)
let v = [a, b, c]
""")
        assert val(i) == [3, 6, 9]

    def test_nested_generator_iter(self) -> None:
        i = run("""
class Matrix {
  fn init(rows) { this.rows = rows }
  *[Symbol.iterator]() {
    for(let row of this.rows) {
      for(let cell of row) { yield cell }
    }
  }
}
let v = [...new Matrix([[1,2],[3,4],[5,6]])]
""")
        assert val(i) == [1, 2, 3, 4, 5, 6]

    def test_generator_iter_with_break(self) -> None:
        i = run("""
class Infinite {
  *[Symbol.iterator]() {
    let n = 0
    while(true) { yield n++ }
  }
}
let v = []
for(let x of new Infinite()) {
  if(x >= 5) { break }
  v.push(x)
}
""")
        assert val(i) == [0, 1, 2, 3, 4]

    def test_generator_iter_sum(self) -> None:
        i = run("""
class Range {
  fn init(s, e) { this.s = s; this.e = e }
  *[Symbol.iterator]() {
    for(let i = this.s; i <= this.e; i++) { yield i }
  }
}
let sum = 0
for(let x of new Range(1, 10)) { sum += x }
let v = sum
""")
        assert val(i) == 55

    def test_custom_iter_in_array_from(self) -> None:
        i = run("""
class Chars {
  fn init(s) { this.s = s }
  *[Symbol.iterator]() { for(let c of this.s) { yield c } }
}
let v = Array.from(new Chars('hello'))
""")
        assert val(i) == ['h', 'e', 'l', 'l', 'o']


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestPhase50Integration:
    def test_let_counter_pattern(self) -> None:
        """Classic counter pattern using mutable let."""
        i = run("""
fn makeAdder(start) {
  let total = start
  return (n) => { total += n; return total }
}
let add = makeAdder(0)
add(5)
add(3)
let v = add(2)
""")
        assert val(i) == 10

    def test_matchall_and_let_collect(self) -> None:
        i = run(r"""
let words = []
for(let m of 'hello world foo bar'.matchAll(/(?<w>[a-z]+)/g)) {
  words.push(m.groups.w)
}
let v = words.length
""")
        assert val(i) == 4

    def test_generator_with_let_accumulate(self) -> None:
        i = run("""
class Powers {
  fn init(base, count) { this.base = base; this.count = count }
  *[Symbol.iterator]() {
    let p = 1
    for(let i = 0; i < this.count; i++) { yield p; p *= this.base }
  }
}
let total = 0
for(let p of new Powers(2, 5)) { total += p }
let v = total
""")
        assert val(i) == 31  # 1+2+4+8+16

    def test_const_let_coexist(self) -> None:
        """const and let can coexist; const prevents mutation, let allows it."""
        i = run("""
const MULTIPLIER = 3
let result = 0
for(let i = 1; i <= 5; i++) {
  result += i * MULTIPLIER
}
let v = result
""")
        assert val(i) == 45  # (1+2+3+4+5) * 3

    def test_linked_list_with_generator(self) -> None:
        i = run("""
class LinkedList {
  fn init() { this.head = null }
  push(val) {
    this.head = {val: val, next: this.head}
  }
  *[Symbol.iterator]() {
    let cur = this.head
    while(cur != null) { yield cur.val; cur = cur.next }
  }
}
let list = new LinkedList()
list.push(3)
list.push(2)
list.push(1)
let v = [...list]
""")
        assert val(i) == [1, 2, 3]
