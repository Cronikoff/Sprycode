"""Phase 11 feature tests — bitwise operators, dict comprehension, for...of,
number methods (toHex/toBinary/toOctal/toOrdinal), string methods (charCodeAt/
codePointAt/replaceRegex), list methods (compact/minBy/maxBy/countBy/sumBy/
takeWhile/dropWhile), Map namespace additions (merge/of/filter/map/clone/toEntries)."""

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
# Bitwise binary operators
# ---------------------------------------------------------------------------


class TestBitwiseBinary:
    def test_bitwise_and(self):
        i = run("let v = 5 & 3")
        assert val(i, "v") == 1

    def test_bitwise_or(self):
        i = run("let v = 5 | 2")
        assert val(i, "v") == 7

    def test_bitwise_xor(self):
        i = run("let v = 5 ^ 3")
        assert val(i, "v") == 6

    def test_left_shift(self):
        i = run("let v = 1 << 3")
        assert val(i, "v") == 8

    def test_right_shift(self):
        i = run("let v = 16 >> 2")
        assert val(i, "v") == 4

    def test_bitwise_and_zero(self):
        # 255 & 15 == 15
        i = run("let v = 255 & 15")
        assert val(i, "v") == 15

    def test_bitwise_or_flags(self):
        # 1 | 4 == 5
        i = run("let v = 1 | 4")
        assert val(i, "v") == 5

    def test_bitwise_xor_same(self):
        i = run("let v = 42 ^ 42")
        assert val(i, "v") == 0

    def test_shift_left_multiple(self):
        i = run("let v = 3 << 4")
        assert val(i, "v") == 48

    def test_shift_right_large(self):
        i = run("let v = 256 >> 8")
        assert val(i, "v") == 1

    def test_bitwise_precedence_over_add(self):
        # & has lower precedence than + in most languages; but here it wraps equality
        # 2 + 3 & 3 == (2 + 3) & 3 == 5 & 3 == 1
        i = run("let v = 2 + 3 & 3")
        assert val(i, "v") == 1

    def test_bitwise_pipe_does_not_consume_pipe_arrow(self):
        i = run("let nums = [1, 2, 3]\nlet v = nums |> len")
        assert val(i, "v") == 3


# ---------------------------------------------------------------------------
# Bitwise unary (~)
# ---------------------------------------------------------------------------


class TestBitwiseNot:
    def test_bitwise_not_positive(self):
        i = run("let v = ~5")
        assert val(i, "v") == -6

    def test_bitwise_not_zero(self):
        i = run("let v = ~0")
        assert val(i, "v") == -1

    def test_bitwise_not_negative(self):
        i = run("let v = ~(-1)")
        assert val(i, "v") == 0


# ---------------------------------------------------------------------------
# Bitwise compound assignments
# ---------------------------------------------------------------------------


class TestBitwiseCompoundAssign:
    def test_amp_eq(self):
        i = run("var x = 7\nx &= 3\nlet v = x")
        assert val(i, "v") == 3

    def test_pipe_eq(self):
        i = run("var x = 5\nx |= 2\nlet v = x")
        assert val(i, "v") == 7

    def test_caret_eq(self):
        i = run("var x = 6\nx ^= 3\nlet v = x")
        assert val(i, "v") == 5

    def test_lshift_eq(self):
        i = run("var x = 1\nx <<= 4\nlet v = x")
        assert val(i, "v") == 16

    def test_rshift_eq(self):
        i = run("var x = 32\nx >>= 3\nlet v = x")
        assert val(i, "v") == 4


# ---------------------------------------------------------------------------
# Dict/object comprehension
# ---------------------------------------------------------------------------


class TestDictComprehension:
    def test_basic_dict_comp(self):
        i = run("let v = {k: k*2 for k in [1, 2, 3]}")
        assert val(i, "v") == {1: 2, 2: 4, 3: 6}

    def test_dict_comp_with_if(self):
        i = run("let v = {k: k for k in [1, 2, 3, 4] if k % 2 == 0}")
        assert val(i, "v") == {2: 2, 4: 4}

    def test_dict_comp_string_keys(self):
        i = run('let v = {s: s.length for s in ["a", "bb", "ccc"]}')
        assert val(i, "v") == {"a": 1, "bb": 2, "ccc": 3}

    def test_dict_comp_from_range(self):
        i = run("let v = {n: n*n for n in range(1, 5)}")
        assert val(i, "v") == {1: 1, 2: 4, 3: 9, 4: 16}

    def test_dict_comp_empty_if(self):
        i = run("let v = {k: k for k in [1, 2, 3] if k > 10}")
        assert val(i, "v") == {}

    def test_dict_comp_size(self):
        i = run("let d = {x: x for x in [10, 20, 30]}\nlet v = len(d)")
        assert val(i, "v") == 3

    def test_empty_object_not_dict_comp(self):
        i = run("let v = {}")
        assert val(i, "v") == {}


# ---------------------------------------------------------------------------
# for...of loop
# ---------------------------------------------------------------------------


class TestForOf:
    def test_for_of_sum(self):
        i = run("var s = 0\nfor x of [1, 2, 3] { s += x }\nlet v = s")
        assert val(i, "v") == 6

    def test_for_of_string(self):
        i = run('var s = ""\nfor c of "abc" { s += c }\nlet v = s')
        assert val(i, "v") == "abc"

    def test_for_of_empty(self):
        i = run("var s = 0\nfor x of [] { s += x }\nlet v = s")
        assert val(i, "v") == 0

    def test_for_of_range(self):
        i = run("var s = 0\nfor x of range(1, 6) { s += x }\nlet v = s")
        assert val(i, "v") == 15


# ---------------------------------------------------------------------------
# Number methods: toHex, toBinary, toOctal, toOrdinal
# ---------------------------------------------------------------------------


class TestNumberHexBinaryOctal:
    def test_to_hex_lowercase(self):
        i = run("let v = (255).toHex()")
        assert val(i, "v") == "0xff"

    def test_to_hex_no_prefix(self):
        i = run("let v = (255).toHex(false)")
        assert val(i, "v") == "ff"

    def test_to_hex_zero(self):
        i = run("let v = (0).toHex()")
        assert val(i, "v") == "0x0"

    def test_to_binary(self):
        i = run("let v = (10).toBinary()")
        assert val(i, "v") == "0b1010"

    def test_to_binary_no_prefix(self):
        i = run("let v = (5).toBinary(false)")
        assert val(i, "v") == "101"

    def test_to_octal(self):
        i = run("let v = (8).toOctal()")
        assert val(i, "v") == "0o10"

    def test_to_octal_no_prefix(self):
        i = run("let v = (64).toOctal(false)")
        assert val(i, "v") == "100"


class TestNumberOrdinal:
    def test_ordinal_1st(self):
        i = run("let v = (1).toOrdinal()")
        assert val(i, "v") == "1st"

    def test_ordinal_2nd(self):
        i = run("let v = (2).toOrdinal()")
        assert val(i, "v") == "2nd"

    def test_ordinal_3rd(self):
        i = run("let v = (3).toOrdinal()")
        assert val(i, "v") == "3rd"

    def test_ordinal_4th(self):
        i = run("let v = (4).toOrdinal()")
        assert val(i, "v") == "4th"

    def test_ordinal_11th(self):
        i = run("let v = (11).toOrdinal()")
        assert val(i, "v") == "11th"

    def test_ordinal_12th(self):
        i = run("let v = (12).toOrdinal()")
        assert val(i, "v") == "12th"

    def test_ordinal_13th(self):
        i = run("let v = (13).toOrdinal()")
        assert val(i, "v") == "13th"

    def test_ordinal_21st(self):
        i = run("let v = (21).toOrdinal()")
        assert val(i, "v") == "21st"


# ---------------------------------------------------------------------------
# String methods: charCodeAt, codePointAt, replaceRegex
# ---------------------------------------------------------------------------


class TestStringCharCode:
    def test_char_code_at_first(self):
        i = run('let v = "Hello".charCodeAt(0)')
        assert val(i, "v") == 72

    def test_char_code_at_other(self):
        i = run('let v = "A".charCodeAt(0)')
        assert val(i, "v") == 65

    def test_char_code_at_default(self):
        i = run('let v = "Z".charCodeAt()')
        assert val(i, "v") == 90

    def test_code_point_at(self):
        i = run('let v = "ABC".codePointAt(1)')
        assert val(i, "v") == 66


class TestStringReplaceRegex:
    def test_replace_regex_basic(self):
        i = run('let v = "hello world".replaceRegex("o", "0")')
        assert val(i, "v") == "hell0 w0rld"

    def test_replace_regex_pattern(self):
        i = run('let v = "abc123".replaceRegex("[0-9]", "X")')
        assert val(i, "v") == "abcXXX"

    def test_replace_regex_empty(self):
        i = run('let v = "hello".replaceRegex("l", "")')
        assert val(i, "v") == "heo"

    def test_replace_regex_no_match(self):
        i = run('let v = "hello".replaceRegex("z", "x")')
        assert val(i, "v") == "hello"


# ---------------------------------------------------------------------------
# List methods: compact, minBy, maxBy, countBy, sumBy, takeWhile, dropWhile
# ---------------------------------------------------------------------------


class TestListCompact:
    def test_compact_removes_null(self):
        i = run("let v = [1, null, 2, null, 3].compact")
        assert val(i, "v") == [1, 2, 3]

    def test_compact_removes_false(self):
        i = run("let v = [1, false, 2, false].compact")
        assert val(i, "v") == [1, 2]

    def test_compact_removes_zero(self):
        i = run("let v = [1, 0, 2, 0].compact")
        assert val(i, "v") == [1, 2]

    def test_compact_all_kept(self):
        i = run('let v = [1, "a", true, 3.14].compact')
        assert val(i, "v") == [1, "a", True, 3.14]

    def test_compact_empty(self):
        i = run("let v = [].compact")
        assert val(i, "v") == []


class TestListMinMaxBy:
    def test_min_by(self):
        i = run("let v = [3, 1, 4, 1, 5].minBy(x => x)")
        assert val(i, "v") == 1

    def test_max_by(self):
        i = run("let v = [3, 1, 4, 1, 5].maxBy(x => x)")
        assert val(i, "v") == 5

    def test_min_by_object(self):
        i = run("let v = [{n: 3}, {n: 1}, {n: 4}].minBy(x => x.n)")
        assert val(i, "v") == {"n": 1}

    def test_max_by_string_length(self):
        i = run('let v = ["cat", "elephant", "ox"].maxBy(s => s.length)')
        assert val(i, "v") == "elephant"


class TestListCountBy:
    def test_count_by_length(self):
        i = run('let v = ["a", "bb", "c"].countBy(s => s.length)')
        assert val(i, "v") == {1: 2, 2: 1}

    def test_count_by_parity(self):
        i = run("let v = [1, 2, 3, 4, 5].countBy(n => n % 2)")
        assert val(i, "v") == {1: 3, 0: 2}


class TestListSumBy:
    def test_sum_by_double(self):
        i = run("let v = [1, 2, 3].sumBy(x => x * 2)")
        assert val(i, "v") == 12

    def test_sum_by_length(self):
        i = run('let v = ["a", "bb", "ccc"].sumBy(s => s.length)')
        assert val(i, "v") == 6


class TestListTakeDropWhile:
    def test_take_while(self):
        i = run("let v = [1, 2, 3, 4, 5].takeWhile(x => x < 4)")
        assert val(i, "v") == [1, 2, 3]

    def test_take_while_none(self):
        i = run("let v = [5, 6, 7].takeWhile(x => x < 4)")
        assert val(i, "v") == []

    def test_take_while_all(self):
        i = run("let v = [1, 2, 3].takeWhile(x => x < 10)")
        assert val(i, "v") == [1, 2, 3]

    def test_drop_while(self):
        i = run("let v = [1, 2, 3, 4, 5].dropWhile(x => x < 3)")
        assert val(i, "v") == [3, 4, 5]

    def test_drop_while_none(self):
        i = run("let v = [5, 6, 7].dropWhile(x => x < 1)")
        assert val(i, "v") == [5, 6, 7]

    def test_drop_while_all(self):
        i = run("let v = [1, 2, 3].dropWhile(x => x < 10)")
        assert val(i, "v") == []


# ---------------------------------------------------------------------------
# Map namespace additions
# ---------------------------------------------------------------------------


class TestMapMerge:
    def test_map_merge_two(self):
        i = run("""
let a = Map.from([["x", 1]])
let b = Map.from([["y", 2]])
let c = Map.merge(a, b)
let v = c.size
""")
        assert val(i, "v") == 2

    def test_map_merge_override(self):
        i = run("""
let a = Map.from([["x", 1]])
let b = Map.from([["x", 99]])
let c = Map.merge(a, b)
let v = c.get("x")
""")
        assert val(i, "v") == 99

    def test_map_merge_three(self):
        i = run("""
let a = Map.from([["a", 1]])
let b = Map.from([["b", 2]])
let c = Map.from([["c", 3]])
let d = Map.merge(a, b, c)
let v = d.size
""")
        assert val(i, "v") == 3


class TestMapOf:
    def test_map_of_basic(self):
        i = run('let m = Map.of("a", 1, "b", 2)\nlet v = m.size')
        assert val(i, "v") == 2

    def test_map_of_get(self):
        i = run('let m = Map.of("x", 10, "y", 20)\nlet v = m.get("y")')
        assert val(i, "v") == 20

    def test_map_of_empty(self):
        i = run("let m = Map.of()\nlet v = m.size")
        assert val(i, "v") == 0


class TestMapFilterMap:
    def test_map_filter(self):
        i = run("""
let m = Map.from([["a", 1], ["b", 2], ["c", 3]])
let f = m.filter((v, k) => v > 1)
let v = f.size
""")
        assert val(i, "v") == 2

    def test_map_filter_value(self):
        i = run("""
let m = Map.from([["a", 1], ["b", 10]])
let f = m.filter((v, k) => v > 5)
let v = f.get("b")
""")
        assert val(i, "v") == 10

    def test_map_map(self):
        i = run("""
let m = Map.from([["a", 1], ["b", 2]])
let f = m.map((v, k) => v * 10)
let v = f.get("a")
""")
        assert val(i, "v") == 10

    def test_map_to_entries(self):
        i = run("""
let m = Map.from([["x", 1], ["y", 2]])
let v = m.toEntries()
""")
        assert val(i, "v") == [["x", 1], ["y", 2]]

    def test_map_clone_independent(self):
        i = run("""
let m = Map.from([["a", 1]])
let c = m.clone()
c.set("a", 99)
let v1 = m.get("a")
let v2 = c.get("a")
""")
        assert val(i, "v1") == 1
        assert val(i, "v2") == 99
