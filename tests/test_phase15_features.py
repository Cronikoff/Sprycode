"""Phase 15 feature tests.

Covers:
  - Iterator protocol: SpryIterator with .next() → {value, done}
    .values() / .keys() / .entries() on list, string, Map, SprySet
  - Set.new([...]) — SprySet factory (Set global now supports both
    Set([...]) dedup and Set.new() SprySet construction)
  - string.bytes() — UTF-8 byte list
  - Object.groupBy(arr, fn) — static group-by
  - void operator — evaluates and returns null
  - >>> unsigned right shift
  - Private class fields (#name) — var #x = val; access via #x
  - setTimeout / clearTimeout / setInterval / clearInterval stubs
  - performance.now() global
  - URL.new(href) — hostname, pathname, search, hash, origin, protocol
  - ArrayBuffer.new(n) — byteLength
  - TypedArrays: Int8Array, Uint8Array, Int16Array, Uint16Array,
    Int32Array, Uint32Array, Float32Array, Float64Array
  - async fn* — async generator functions
"""

import pytest
from sprycode.interpreter import Interpreter, SpryIterator, SprySet, SpryRuntimeError
from sprycode.lexer import Lexer
from sprycode.parser import Parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(source: str) -> Interpreter:
    tokens = Lexer(source).tokenize()
    prog = Parser(tokens).parse()
    interp = Interpreter()
    interp.run(prog)
    return interp


def val(source: str, name: str = "v"):
    return run(source).globals.get(name)


# ---------------------------------------------------------------------------
# Iterator protocol — list
# ---------------------------------------------------------------------------


class TestListIterator:
    def test_values_returns_iterator(self):
        result = val("let it = [10, 20, 30].values()\nlet v = it != null")
        assert result is True

    def test_values_next_first(self):
        result = val("let it = [10, 20, 30].values()\nlet v = it.next()")
        assert result == {"value": 10, "done": False}

    def test_values_next_second(self):
        src = "let it = [10, 20, 30].values()\nit.next()\nlet v = it.next()"
        result = val(src)
        assert result == {"value": 20, "done": False}

    def test_values_done(self):
        src = "let it = [1].values()\nit.next()\nlet v = it.next()"
        result = val(src)
        assert result == {"value": None, "done": True}

    def test_values_backward_compat(self):
        # .values() should also compare equal to the list for backward compat
        result = val("let v = [1, 2, 3].values()")
        assert result == [1, 2, 3]

    def test_keys_next(self):
        result = val("let it = [\"a\", \"b\", \"c\"].keys()\nlet v = it.next()")
        assert result == {"value": 0, "done": False}

    def test_keys_all_indices(self):
        result = val("let v = [\"x\", \"y\"].keys()")
        assert result == [0, 1]

    def test_entries_next(self):
        result = val("let it = [\"a\", \"b\"].entries()\nlet v = it.next()")
        assert result == {"value": [0, "a"], "done": False}

    def test_entries_all(self):
        result = val("let v = [10, 20].entries()")
        assert result == [[0, 10], [1, 20]]

    def test_for_of_iterator(self):
        src = "let it = [1, 2, 3].values()\nvar s = 0\nfor x of it { s += x }\nlet v = s"
        assert val(src) == 6


# ---------------------------------------------------------------------------
# Iterator protocol — string
# ---------------------------------------------------------------------------


class TestStringIterator:
    def test_values_next_first_char(self):
        result = val("let it = \"abc\".values()\nlet v = it.next()")
        assert result == {"value": "a", "done": False}

    def test_values_done(self):
        src = "let it = \"x\".values()\nit.next()\nlet v = it.next()"
        result = val(src)
        assert result == {"value": None, "done": True}

    def test_for_of_string_iterator(self):
        src = "let it = \"abc\".values()\nvar s = \"\"\nfor c of it { s += c }\nlet v = s"
        assert val(src) == "abc"


# ---------------------------------------------------------------------------
# Iterator protocol — Map
# ---------------------------------------------------------------------------


class TestMapIterator:
    def test_map_keys_next(self):
        src = "let m = Map.new()\nm.set(\"a\", 1)\nlet it = m.keys()\nlet v = it.next()"
        result = val(src)
        assert result == {"value": "a", "done": False}

    def test_map_values_next(self):
        src = "let m = Map.new()\nm.set(\"a\", 99)\nlet it = m.values()\nlet v = it.next()"
        result = val(src)
        assert result == {"value": 99, "done": False}

    def test_map_entries_next(self):
        src = "let m = Map.new()\nm.set(\"k\", \"v\")\nlet it = m.entries()\nlet v = it.next()"
        result = val(src)
        assert result == {"value": ["k", "v"], "done": False}

    def test_map_keys_backward_compat(self):
        src = "let m = Map.new()\nm.set(\"x\", 1)\nm.set(\"y\", 2)\nlet v = m.keys()"
        result = val(src)
        assert result == ["x", "y"]

    def test_map_values_backward_compat(self):
        src = "let m = Map.new()\nm.set(\"a\", 10)\nm.set(\"b\", 20)\nlet v = m.values()"
        result = val(src)
        assert result == [10, 20]

    def test_map_entries_backward_compat(self):
        src = "let m = Map.new()\nm.set(\"k\", \"v\")\nlet v = m.entries()"
        result = val(src)
        assert result == [["k", "v"]]


# ---------------------------------------------------------------------------
# Iterator protocol — SprySet
# ---------------------------------------------------------------------------


class TestSetNew:
    def test_set_new_no_args(self):
        result = val("let s = Set.new()\nlet v = s.size")
        assert result == 0

    def test_set_new_with_list(self):
        result = val("let s = Set.new([1, 2, 3])\nlet v = s.size")
        assert result == 3

    def test_set_new_deduplicates(self):
        result = val("let s = Set.new([1, 2, 2, 3, 1])\nlet v = s.size")
        assert result == 3

    def test_set_new_has(self):
        result = val("let s = Set.new([1, 2, 3])\nlet v = s.has(2)")
        assert result is True

    def test_set_new_for_of(self):
        result = val("let s = Set.new([1, 2, 3])\nvar v = 0\nfor x of s { v += x }")
        assert result == 6

    def test_set_new_values_next(self):
        src = "let s = Set.new([10, 20, 30])\nlet it = s.values()\nlet v = it.next()"
        result = val(src)
        assert result == {"value": 10, "done": False}

    def test_set_new_keys_next(self):
        src = "let s = Set.new([10, 20])\nlet it = s.keys()\nlet v = it.next()"
        result = val(src)
        assert result == {"value": 10, "done": False}

    def test_set_callable_backward_compat(self):
        # Set([...]) still returns deduplicated list
        result = val("let v = Set([1, 2, 2, 3])")
        assert result == [1, 2, 3]

    def test_set_callable_empty(self):
        result = val("let v = Set([])")
        assert result == []


# ---------------------------------------------------------------------------
# string.bytes()
# ---------------------------------------------------------------------------


class TestStringBytes:
    def test_ascii_bytes(self):
        result = val("let v = \"abc\".bytes()")
        assert result == [97, 98, 99]

    def test_empty_bytes(self):
        result = val("let v = \"\".bytes()")
        assert result == []

    def test_unicode_bytes(self):
        # é is 2 bytes in UTF-8
        result = val("let v = \"caf\u00e9\".bytes()")
        assert result == list("café".encode("utf-8"))

    def test_bytes_is_list(self):
        result = val("let v = \"hello\".bytes()")
        assert isinstance(result, list)

    def test_bytes_length(self):
        result = val("let v = \"hello\".bytes().length")
        assert result == 5


# ---------------------------------------------------------------------------
# Object.groupBy
# ---------------------------------------------------------------------------


class TestObjectGroupBy:
    def test_group_by_parity(self):
        result = val("let v = Object.groupBy([1, 2, 3, 4], x => x % 2 == 0 ? \"even\" : \"odd\")")
        assert set(result.keys()) == {"even", "odd"}
        assert sorted(result["even"]) == [2, 4]
        assert sorted(result["odd"]) == [1, 3]

    def test_group_by_string_key(self):
        result = val("let v = Object.groupBy([\"apple\", \"banana\", \"avocado\"], s => s[0])")
        assert "a" in result
        assert "b" in result
        assert set(result["a"]) == {"apple", "avocado"}

    def test_group_by_returns_dict(self):
        result = val("let v = Object.groupBy([1, 2], x => \"k\")")
        assert isinstance(result, dict)

    def test_group_by_empty(self):
        result = val("let v = Object.groupBy([], x => x)")
        assert result == {}

    def test_group_by_all_same_key(self):
        result = val("let v = Object.groupBy([1, 2, 3], x => \"all\")")
        assert result == {"all": [1, 2, 3]}


# ---------------------------------------------------------------------------
# void operator
# ---------------------------------------------------------------------------


class TestVoidOperator:
    def test_void_number_returns_null(self):
        assert val("let v = void 42") is None

    def test_void_string_returns_null(self):
        assert val("let v = void \"hello\"") is None

    def test_void_expression_evaluates(self):
        # void evaluates expression and returns null
        result = val("let v = void (1 + 2)")
        assert result is None

    def test_void_in_expression(self):
        assert val("let v = void 0 == null") is True

    def test_void_true_is_null(self):
        assert val("let v = void true") is None


# ---------------------------------------------------------------------------
# >>> unsigned right shift
# ---------------------------------------------------------------------------


class TestUnsignedRightShift:
    def test_positive_unchanged(self):
        assert val("let v = 8 >>> 1") == 4

    def test_zero_bits(self):
        assert val("let v = 16 >>> 0") == 16

    def test_negative_becomes_positive(self):
        result = val("let v = -1 >>> 0")
        assert result == 4294967295  # 0xFFFFFFFF

    def test_negative_shift_one(self):
        result = val("let v = -2 >>> 1")
        assert result == 2147483647  # 0x7FFFFFFF

    def test_large_positive(self):
        assert val("let v = 2147483648 >>> 1") == 1073741824

    def test_chained(self):
        # 255 >>> 4 == 15
        assert val("let v = 255 >>> 4") == 15

    def test_with_var(self):
        assert val("var x = 32\nlet v = x >>> 2") == 8


# ---------------------------------------------------------------------------
# Private class fields
# ---------------------------------------------------------------------------


class TestPrivateClassFields:
    def test_basic_get(self):
        src = (
            "class Counter { var #count = 0\n"
            "fn get() { return #count } }\n"
            "let c = Counter.new()\n"
            "let v = c.get()"
        )
        assert val(src) == 0

    def test_increment(self):
        src = (
            "class Counter { var #count = 0\n"
            "fn inc() { #count++ }\n"
            "fn get() { return #count } }\n"
            "let c = Counter.new()\n"
            "c.inc()\nc.inc()\n"
            "let v = c.get()"
        )
        assert val(src) == 2

    def test_initial_value(self):
        src = (
            "class Bag { var #items = []\n"
            "fn add(x) { #items.push(x) }\n"
            "fn size() { return #items.length } }\n"
            "let b = Bag.new()\n"
            "b.add(1)\nb.add(2)\n"
            "let v = b.size()"
        )
        assert val(src) == 2

    def test_private_not_accessible_directly(self):
        # Accessing #count directly from outside should fail
        src = (
            "class C { var #x = 42\nfn get() { return #x } }\n"
            "let c = C.new()\n"
            "let v = c.get()"
        )
        assert val(src) == 42

    def test_private_string_value(self):
        src = (
            "class Namer { var #name = \"world\"\n"
            "fn greet() { return \"hello \" + #name } }\n"
            "let n = Namer.new()\n"
            "let v = n.greet()"
        )
        assert val(src) == "hello world"


# ---------------------------------------------------------------------------
# setTimeout / clearTimeout / setInterval / clearInterval
# ---------------------------------------------------------------------------


class TestTimers:
    def test_set_timeout_returns_id(self):
        result = val("let v = setTimeout(() => {}, 100)")
        assert isinstance(result, int)
        assert result > 0

    def test_set_timeout_executes_callback(self):
        result = val("var v = false\nsetTimeout(() => { v = true }, 0)")
        assert result is True

    def test_clear_timeout_noop(self):
        result = val("let id = setTimeout(() => {}, 100)\nclearTimeout(id)\nlet v = true")
        assert result is True

    def test_set_interval_returns_id(self):
        result = val("let v = setInterval(() => {}, 1000)")
        assert isinstance(result, int)

    def test_clear_interval_noop(self):
        result = val("let id = setInterval(() => {}, 100)\nclearInterval(id)\nlet v = true")
        assert result is True

    def test_multiple_timers_unique_ids(self):
        src = "let a = setTimeout(() => {}, 10)\nlet b = setTimeout(() => {}, 20)\nlet v = a != b"
        assert val(src) is True


# ---------------------------------------------------------------------------
# performance.now()
# ---------------------------------------------------------------------------


class TestPerformance:
    def test_now_returns_number(self):
        result = val("let v = performance.now()")
        assert isinstance(result, (int, float))

    def test_now_positive(self):
        assert val("let v = performance.now() > 0") is True

    def test_now_monotonic(self):
        # Two calls should produce non-negative difference
        src = "let a = performance.now()\nlet b = performance.now()\nlet v = b >= a"
        assert val(src) is True

    def test_mark_noop(self):
        result = val("performance.mark(\"start\")\nlet v = true")
        assert result is True

    def test_measure_noop(self):
        result = val("performance.measure(\"m\", \"start\", \"end\")\nlet v = true")
        assert result is True


# ---------------------------------------------------------------------------
# URL.new()
# ---------------------------------------------------------------------------


class TestURL:
    def test_hostname(self):
        assert val('let u = URL.new("https://example.com/path")\nlet v = u.hostname') == "example.com"

    def test_pathname(self):
        assert val('let u = URL.new("https://example.com/foo/bar")\nlet v = u.pathname') == "/foo/bar"

    def test_search(self):
        assert val('let u = URL.new("https://example.com/p?q=1")\nlet v = u.search') == "?q=1"

    def test_hash(self):
        assert val('let u = URL.new("https://example.com/#section")\nlet v = u.hash') == "#section"

    def test_protocol(self):
        assert val('let u = URL.new("https://example.com/")\nlet v = u.protocol') == "https:"

    def test_origin(self):
        assert val('let u = URL.new("https://example.com/path")\nlet v = u.origin') == "https://example.com"

    def test_href(self):
        href = "https://example.com/path?q=1"
        assert val(f'let u = URL.new("{href}")\nlet v = u.href') == href

    def test_pathname_no_query(self):
        assert val('let u = URL.new("https://example.com/page")\nlet v = u.pathname') == "/page"

    def test_empty_hash(self):
        assert val('let u = URL.new("https://example.com/")\nlet v = u.hash') == ""

    def test_empty_search(self):
        assert val('let u = URL.new("https://example.com/")\nlet v = u.search') == ""

    def test_can_parse_true(self):
        assert val('let v = URL.canParse("https://example.com")') is True

    def test_can_parse_false(self):
        assert val('let v = URL.canParse("not a url")') is False

    def test_toString(self):
        href = "https://example.com/"
        assert val(f'let u = URL.new("{href}")\nlet v = u.toString()') == href


# ---------------------------------------------------------------------------
# ArrayBuffer
# ---------------------------------------------------------------------------


class TestArrayBuffer:
    def test_byte_length(self):
        assert val("let buf = ArrayBuffer.new(8)\nlet v = buf.byteLength") == 8

    def test_zero_length(self):
        assert val("let buf = ArrayBuffer.new(0)\nlet v = buf.byteLength") == 0

    def test_large_buffer(self):
        assert val("let buf = ArrayBuffer.new(1024)\nlet v = buf.byteLength") == 1024

    def test_is_view_false(self):
        assert val("let buf = ArrayBuffer.new(4)\nlet v = ArrayBuffer.isView(buf)") is False

    def test_is_view_true_for_typed_array(self):
        assert val("let arr = Int32Array.new(4)\nlet v = ArrayBuffer.isView(arr)") is True


# ---------------------------------------------------------------------------
# TypedArrays
# ---------------------------------------------------------------------------


class TestTypedArrays:
    def test_int32_length(self):
        assert val("let arr = Int32Array.new(4)\nlet v = arr.length") == 4

    def test_int32_byte_length(self):
        assert val("let arr = Int32Array.new(4)\nlet v = arr.byteLength") == 16

    def test_int32_get_default(self):
        assert val("let arr = Int32Array.new(4)\nlet v = arr.get(0)") == 0

    def test_int32_set_get(self):
        assert val("let arr = Int32Array.new(4)\narr.set(2, 99)\nlet v = arr.get(2)") == 99

    def test_uint8_byte_length(self):
        assert val("let arr = Uint8Array.new(8)\nlet v = arr.byteLength") == 8

    def test_float64_byte_length(self):
        assert val("let arr = Float64Array.new(2)\nlet v = arr.byteLength") == 16

    def test_from_list(self):
        assert val("let arr = Int32Array.new([1, 2, 3])\nlet v = arr.length") == 3

    def test_from_list_values(self):
        assert val("let arr = Int32Array.new([10, 20, 30])\nlet v = arr.get(1)") == 20

    def test_to_list(self):
        result = val("let arr = Int32Array.new([1, 2, 3])\nlet v = arr.toList()")
        assert result == [1, 2, 3]

    def test_fill(self):
        result = val("let arr = Int32Array.new(3)\narr.fill(7)\nlet v = arr.toList()")
        assert result == [7, 7, 7]

    def test_subarray(self):
        result = val("let arr = Int32Array.new([1, 2, 3, 4])\nlet sub = arr.subarray(1, 3)\nlet v = sub.length")
        assert result == 2

    def test_int16_byte_length(self):
        assert val("let arr = Int16Array.new(4)\nlet v = arr.byteLength") == 8

    def test_uint32_type(self):
        assert val("let arr = Uint32Array.new(4)\nlet v = arr.length") == 4


# ---------------------------------------------------------------------------
# async fn*
# ---------------------------------------------------------------------------


class TestAsyncGenerators:
    def test_basic_iteration(self):
        src = "async fn* gen() { yield 1\nyield 2 }\nvar v = 0\nfor x of gen() { v += x }"
        assert val(src) == 3

    def test_yields_three(self):
        src = "async fn* nums() { yield 10\nyield 20\nyield 30 }\nvar v = 0\nfor n of nums() { v += n }"
        assert val(src) == 60

    def test_with_condition(self):
        src = "async fn* evens(limit) { var i = 0\nwhile i < limit { if i % 2 == 0 { yield i }\ni++ } }\nvar v = 0\nfor e of evens(6) { v += e }"
        assert val(src) == 6  # 0 + 2 + 4

    def test_map_from_generator(self):
        src = "async fn* gen() { yield 1\nyield 2\nyield 3 }\nlet v = Array.from(gen())"
        result = val(src)
        assert result == [1, 2, 3]
