"""Phase 12 feature tests — hex/binary/octal literals, template literals, labeled
break/continue, array destructuring defaults, nested object destructuring, generator
.next()/.return()/.throw() iterator protocol, Symbol, WeakRef, Map.groupBy,
Array.from(src, mapFn), list.copyWithin."""

import pytest
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.interpreter import Interpreter


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str):
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# Hex / binary / octal number literals
# ---------------------------------------------------------------------------


class TestHexLiterals:
    def test_hex_lowercase(self):
        i = run("let v = 0x1f")
        assert val(i, "v") == 31

    def test_hex_uppercase(self):
        i = run("let v = 0xFF")
        assert val(i, "v") == 255

    def test_hex_zero(self):
        i = run("let v = 0x0")
        assert val(i, "v") == 0

    def test_hex_large(self):
        i = run("let v = 0xDEAD")
        assert val(i, "v") == 0xDEAD

    def test_hex_arithmetic(self):
        i = run("let v = 0x10 + 0x10")
        assert val(i, "v") == 32

    def test_hex_with_underscores(self):
        # Underscores in numeric literals are stripped
        i = run("let v = 0xFF_FF")
        assert val(i, "v") == 0xFFFF


class TestBinaryLiterals:
    def test_binary_basic(self):
        i = run("let v = 0b1010")
        assert val(i, "v") == 10

    def test_binary_all_zeros(self):
        i = run("let v = 0b0000")
        assert val(i, "v") == 0

    def test_binary_all_ones(self):
        i = run("let v = 0b1111")
        assert val(i, "v") == 15

    def test_binary_large(self):
        i = run("let v = 0b11001100")
        assert val(i, "v") == 204

    def test_binary_arithmetic(self):
        i = run("let v = 0b1000 + 0b0111")
        assert val(i, "v") == 15


class TestOctalLiterals:
    def test_octal_basic(self):
        i = run("let v = 0o17")
        assert val(i, "v") == 15

    def test_octal_zero(self):
        i = run("let v = 0o0")
        assert val(i, "v") == 0

    def test_octal_large(self):
        i = run("let v = 0o777")
        assert val(i, "v") == 511

    def test_octal_arithmetic(self):
        i = run("let v = 0o10 + 0o10")
        assert val(i, "v") == 16


# ---------------------------------------------------------------------------
# Labeled break / continue
# ---------------------------------------------------------------------------


class TestLabeledBreak:
    def test_labeled_break_exits_outer_loop(self):
        i = run("""
var count = 0
outer: for i in range(3) {
  for j in range(3) {
    if j == 1 { break outer }
    count += 1
  }
}
let v = count
""")
        assert val(i, "v") == 1  # only (i=0, j=0) counted before break outer

    def test_labeled_break_inner_only(self):
        i = run("""
var count = 0
for i in range(3) {
  inner: for j in range(3) {
    if j == 1 { break inner }
    count += 1
  }
}
let v = count
""")
        assert val(i, "v") == 3  # one per outer iteration (j=0 each time)

    def test_plain_break_still_works(self):
        i = run("""
var v = 0
for x in range(10) {
  if x == 5 { break }
  v += 1
}
""")
        assert val(i, "v") == 5


class TestLabeledContinue:
    def test_labeled_continue_skips_outer(self):
        i = run("""
var count = 0
outer: for i in range(3) {
  for j in range(3) {
    if j == 1 { continue outer }
    count += 1
  }
}
let v = count
""")
        assert val(i, "v") == 3  # only j=0 counted per outer i, total 3

    def test_plain_continue_still_works(self):
        i = run("""
var v = 0
for x in range(10) {
  if x % 2 == 0 { continue }
  v += x
}
""")
        assert val(i, "v") == 25  # 1+3+5+7+9


# ---------------------------------------------------------------------------
# Array destructuring with defaults
# ---------------------------------------------------------------------------


class TestListDestructureDefaults:
    def test_missing_element_uses_default(self):
        i = run("let [a, b = 20] = [1]\nlet v = b")
        assert val(i, "v") == 20

    def test_present_element_overrides_default(self):
        i = run("let [a = 99, b = 88] = [1, 2]\nlet v = a")
        assert val(i, "v") == 1

    def test_all_defaults_used(self):
        i = run("let [a = 10, b = 20, c = 30] = []\nlet v = b")
        assert val(i, "v") == 20

    def test_partial_defaults(self):
        i = run("let [a, b = 100] = [5, 7]\nlet v = b")
        assert val(i, "v") == 7

    def test_default_expression(self):
        i = run("let x = 99\nlet [a, b = x] = [1]\nlet v = b")
        assert val(i, "v") == 99

    def test_rest_with_defaults(self):
        i = run("let [a = 1, ...rest] = [10, 20, 30]\nlet v = rest")
        assert val(i, "v") == [20, 30]


# ---------------------------------------------------------------------------
# Nested object destructuring
# ---------------------------------------------------------------------------


class TestNestedObjectDestructure:
    def test_basic_nested(self):
        i = run("let {a: {b}} = {a: {b: 42}}\nlet v = b")
        assert val(i, "v") == 42

    def test_double_nested(self):
        i = run("let {a: {b: {c}}} = {a: {b: {c: 99}}}\nlet v = c")
        assert val(i, "v") == 99

    def test_sibling_nested(self):
        i = run("let {x: {y}, z} = {x: {y: 10}, z: 20}\nlet v = y + z")
        assert val(i, "v") == 30

    def test_nested_with_alias(self):
        i = run("let {a: alias} = {a: 7}\nlet v = alias")
        assert val(i, "v") == 7

    def test_nested_missing_value(self):
        i = run("let {a: {b}} = {a: {}}\nlet v = b")
        assert val(i, "v") is None

    def test_nested_default(self):
        i = run("let {a: x = 5} = {}\nlet v = x")
        assert val(i, "v") == 5


# ---------------------------------------------------------------------------
# Generator .next() / .return() / .throw() iterator protocol
# ---------------------------------------------------------------------------


class TestGeneratorNext:
    def test_next_returns_value_and_done_false(self):
        i = run("fn* gen() { yield 1\nyield 2 }\nlet g = gen()\nlet r = g.next()\nlet v = r.value")
        assert val(i, "v") == 1

    def test_next_sequential(self):
        i = run("""
fn* gen() { yield 10
yield 20
yield 30 }
let g = gen()
g.next()
let r = g.next()
let v = r.value
""")
        assert val(i, "v") == 20

    def test_next_done_false_while_values(self):
        i = run("fn* gen() { yield 1 }\nlet g = gen()\nlet r = g.next()\nlet v = r.done")
        assert val(i, "v") is False

    def test_next_done_true_when_exhausted(self):
        i = run("fn* gen() { yield 1 }\nlet g = gen()\ng.next()\nlet r = g.next()\nlet v = r.done")
        assert val(i, "v") is True

    def test_next_exhausted_value_is_null(self):
        i = run("fn* gen() { yield 1 }\nlet g = gen()\ng.next()\nlet r = g.next()\nlet v = r.value")
        assert val(i, "v") is None

    def test_generator_still_iterable(self):
        i = run("fn* gen() { yield 1\nyield 2\nyield 3 }\nlet v = [x for x in gen()]")
        assert val(i, "v") == [1, 2, 3]

    def test_generator_return(self):
        i = run("fn* gen() { yield 1\nyield 2 }\nlet g = gen()\nlet r = g.return(99)\nlet v = r.done")
        assert val(i, "v") is True

    def test_generator_done_property(self):
        i = run("fn* gen() { yield 1 }\nlet g = gen()\ng.next()\nlet v = g.done")
        assert val(i, "v") is True


# ---------------------------------------------------------------------------
# Symbol
# ---------------------------------------------------------------------------


class TestSymbol:
    def test_symbol_has_description(self):
        i = run('let s = Symbol("foo")\nlet v = s.description')
        assert val(i, "v") == "foo"

    def test_symbol_empty_description(self):
        i = run("let s = Symbol()\nlet v = s.description")
        assert val(i, "v") == ""

    def test_symbols_are_unique(self):
        i = run('let a = Symbol("x")\nlet b = Symbol("x")\nlet v = a == b')
        assert val(i, "v") is False

    def test_symbol_is_same_as_itself(self):
        i = run('let a = Symbol("y")\nlet v = a == a')
        assert val(i, "v") is True

    def test_symbol_for_returns_same(self):
        i = run('let a = Symbol.for("key")\nlet b = Symbol.for("key")\nlet v = a == b')
        assert val(i, "v") is True

    def test_symbol_for_different_keys(self):
        i = run('let a = Symbol.for("k1")\nlet b = Symbol.for("k2")\nlet v = a == b')
        assert val(i, "v") is False

    def test_symbol_repr(self):
        i = run('let s = Symbol("test")\nlet v = str(s)')
        assert "test" in str(val(i, "v"))


# ---------------------------------------------------------------------------
# WeakRef
# ---------------------------------------------------------------------------


class TestWeakRef:
    def test_deref_returns_original(self):
        i = run("let obj = {x: 99}\nlet w = WeakRef.new(obj)\nlet v = w.deref().x")
        assert val(i, "v") == 99

    def test_deref_list(self):
        i = run("let lst = [1, 2, 3]\nlet w = WeakRef.new(lst)\nlet v = w.deref()")
        assert val(i, "v") == [1, 2, 3]

    def test_deref_primitive(self):
        i = run("let w = WeakRef.new(42)\nlet v = w.deref()")
        assert val(i, "v") == 42

    def test_weakref_independence(self):
        i = run("let a = {n: 1}\nlet b = {n: 2}\nlet wa = WeakRef.new(a)\nlet wb = WeakRef.new(b)\nlet v = wa.deref().n + wb.deref().n")
        assert val(i, "v") == 3


# ---------------------------------------------------------------------------
# Map.groupBy
# ---------------------------------------------------------------------------


class TestMapGroupBy:
    def test_group_by_parity(self):
        i = run("let m = Map.groupBy([1,2,3,4], x => x % 2)\nlet v = m.get(0)")
        assert val(i, "v") == [2, 4]

    def test_group_by_odds(self):
        i = run("let m = Map.groupBy([1,2,3,4,5], x => x % 2)\nlet v = m.get(1)")
        assert val(i, "v") == [1, 3, 5]

    def test_group_by_string_length(self):
        i = run('let m = Map.groupBy(["a", "bb", "c", "dd"], s => s.length)\nlet v = m.get(2)')
        assert val(i, "v") == ["bb", "dd"]

    def test_group_by_result_size(self):
        i = run("let m = Map.groupBy([1,2,3,4,5,6], x => x % 3)\nlet v = m.size")
        assert val(i, "v") == 3

    def test_group_by_single(self):
        i = run('let m = Map.groupBy(["x"], s => s)\nlet v = m.get("x")')
        assert val(i, "v") == ["x"]


# ---------------------------------------------------------------------------
# Array.from with map function
# ---------------------------------------------------------------------------


class TestArrayFromMap:
    def test_array_from_with_double(self):
        i = run("let v = Array.from([1,2,3], x => x*2)")
        assert val(i, "v") == [2, 4, 6]

    def test_array_from_string_with_upper(self):
        i = run('let v = Array.from("abc", c => c.toUpper())')
        assert val(i, "v") == ["A", "B", "C"]

    def test_array_from_range_with_map(self):
        i = run("let v = Array.from(range(1, 6), x => x*x)")
        assert val(i, "v") == [1, 4, 9, 16, 25]

    def test_array_from_without_map(self):
        i = run("let v = Array.from([10, 20, 30])")
        assert val(i, "v") == [10, 20, 30]

    def test_array_from_empty_with_map(self):
        i = run("let v = Array.from([], x => x*2)")
        assert val(i, "v") == []


# ---------------------------------------------------------------------------
# list.copyWithin
# ---------------------------------------------------------------------------


class TestListCopyWithin:
    def test_copy_within_basic(self):
        i = run("let v = [1, 2, 3, 4, 5].copyWithin(1, 3)")
        assert val(i, "v") == [1, 4, 5, 4, 5]

    def test_copy_within_with_end(self):
        i = run("let v = [1, 2, 3, 4, 5].copyWithin(0, 3, 4)")
        assert val(i, "v") == [4, 2, 3, 4, 5]

    def test_copy_within_to_start(self):
        i = run("let v = [1, 2, 3, 4, 5].copyWithin(0, 2)")
        assert val(i, "v") == [3, 4, 5, 4, 5]

    def test_copy_within_no_change(self):
        i = run("let v = [1, 2, 3].copyWithin(0, 0)")
        assert val(i, "v") == [1, 2, 3]

    def test_copy_within_does_not_mutate(self):
        # Returns a new list
        i = run("let lst = [1, 2, 3, 4, 5]\nlet v = lst.copyWithin(1, 3)\nlet w = lst")
        assert val(i, "v") == [1, 4, 5, 4, 5]
        assert val(i, "w") == [1, 2, 3, 4, 5]
