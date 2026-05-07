"""Tests for Phase 107: TypedArray array-like methods, URL.searchParams,
Date.getTimezoneOffset, SuppressedError, and regex 'd' flag (hasIndices)."""
from __future__ import annotations

from typing import Any

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
# Regex 'd' flag — hasIndices
# ---------------------------------------------------------------------------

class TestRegexDFlag:
    def test_literal_d_flag_hasIndices_true(self):
        i = run("let v = /a/d.hasIndices;")
        assert val(i) is True

    def test_no_d_flag_hasIndices_false(self):
        i = run("let v = /a/.hasIndices;")
        assert val(i) is False

    def test_regexp_constructor_d_flag(self):
        i = run('let r = new RegExp("a", "d"); let v = r.hasIndices;')
        assert val(i) is True

    def test_d_flag_in_flags_string(self):
        i = run("let r = /a/d; let v = r.flags.includes(\"d\");")
        assert val(i) is True

    def test_d_flag_combined(self):
        i = run("let r = /a/dg; let v = r.hasIndices && r.global;")
        assert val(i) is True

    def test_d_flag_exec_still_works(self):
        i = run('let r = /a/d; let m = r.exec("cat"); let v = m !== null;')
        assert val(i) is True


# ---------------------------------------------------------------------------
# Date.getTimezoneOffset
# ---------------------------------------------------------------------------

class TestDateGetTimezoneOffset:
    def test_returns_zero(self):
        """SpryCode has no timezone support — offset is always 0."""
        i = run("let v = new Date(2024, 0, 15).getTimezoneOffset();")
        assert val(i) == 0

    def test_returns_number(self):
        i = run("let v = typeof new Date(2024, 0, 15).getTimezoneOffset();")
        assert val(i) == "number"

    def test_consistent_across_dates(self):
        i = run("""
let a = new Date(2024, 0, 1).getTimezoneOffset();
let b = new Date(2024, 6, 1).getTimezoneOffset();
let v = a === b;
""")
        assert val(i) is True


# ---------------------------------------------------------------------------
# URL.searchParams
# ---------------------------------------------------------------------------

class TestURLSearchParams:
    def test_searchParams_get_existing_key(self):
        i = run('let u = new URL("https://example.com/?a=1&b=2"); let v = u.searchParams.get("a");')
        assert val(i) == "1"

    def test_searchParams_get_second_key(self):
        i = run('let u = new URL("https://example.com/?a=1&b=hello"); let v = u.searchParams.get("b");')
        assert val(i) == "hello"

    def test_searchParams_get_missing_key_returns_null(self):
        i = run('let u = new URL("https://example.com/?a=1"); let v = u.searchParams.get("z");')
        assert val(i) is None

    def test_searchParams_has_key(self):
        i = run('let u = new URL("https://example.com/?a=1"); let v = u.searchParams.has("a");')
        assert val(i) is True

    def test_searchParams_has_missing_key(self):
        i = run('let u = new URL("https://example.com/?a=1"); let v = u.searchParams.has("z");')
        assert val(i) is False

    def test_searchParams_size(self):
        i = run('let u = new URL("https://example.com/?a=1&b=2"); let v = u.searchParams.size;')
        assert val(i) == 2

    def test_searchParams_set_and_get(self):
        i = run("""
let u = new URL("https://example.com/?a=1");
u.searchParams.set("a", "99");
let v = u.searchParams.get("a");
""")
        assert val(i) == "99"

    def test_searchParams_append(self):
        i = run("""
let u = new URL("https://example.com/?a=1");
u.searchParams.append("b", "2");
let v = u.searchParams.has("b");
""")
        assert val(i) is True

    def test_searchParams_delete(self):
        i = run("""
let u = new URL("https://example.com/?a=1&b=2");
u.searchParams.delete("a");
let v = u.searchParams.has("a");
""")
        assert val(i) is False

    def test_searchParams_no_query_empty(self):
        i = run('let u = new URL("https://example.com/"); let v = u.searchParams.size;')
        assert val(i) == 0

    def test_searchParams_getAll(self):
        i = run("""
let u = new URL("https://example.com/?a=1&a=2&a=3");
let v = u.searchParams.getAll("a");
""")
        assert val(i) == ["1", "2", "3"]

    def test_searchParams_keys_iterable(self):
        i = run("""
let u = new URL("https://example.com/?x=1&y=2");
let r = [];
for (let k of u.searchParams.keys()) { r.push(k); }
let v = r;
""")
        assert val(i) == ["x", "y"]

    def test_searchParams_values_iterable(self):
        i = run("""
let u = new URL("https://example.com/?x=10&y=20");
let r = [];
for (let v2 of u.searchParams.values()) { r.push(v2); }
let v = r;
""")
        assert val(i) == ["10", "20"]

    def test_searchparams_toString(self):
        i = run("""
let u = new URL("https://example.com/?a=1&b=2");
let v = typeof u.searchParams.toString();
""")
        assert val(i) == "string"


# ---------------------------------------------------------------------------
# SuppressedError
# ---------------------------------------------------------------------------

class TestSuppressedError:
    def test_suppressed_error_error_property(self):
        i = run('let e = new SuppressedError("outer", "inner", "msg"); let v = e.error;')
        assert val(i) == "outer"

    def test_suppressed_error_suppressed_property(self):
        i = run('let e = new SuppressedError("outer", "inner", "msg"); let v = e.suppressed;')
        assert val(i) == "inner"

    def test_suppressed_error_message(self):
        i = run('let e = new SuppressedError("outer", "inner", "msg"); let v = e.message;')
        assert val(i) == "msg"

    def test_suppressed_error_name(self):
        i = run('let e = new SuppressedError("outer", "inner"); let v = e.name;')
        assert val(i) == "SuppressedError"

    def test_suppressed_error_instanceof_error(self):
        i = run('let e = new SuppressedError("a", "b"); let v = e instanceof Error;')
        assert val(i) is True

    def test_suppressed_error_instanceof_suppressed_error(self):
        i = run('let e = new SuppressedError("a", "b"); let v = e instanceof SuppressedError;')
        assert val(i) is True

    def test_suppressed_error_with_error_objects(self):
        i = run("""
let outer = new Error("outer");
let suppressed = new TypeError("suppressed");
let e = new SuppressedError(outer, suppressed, "both");
let v = e.error.message;
""")
        assert val(i) == "outer"

    def test_suppressed_error_no_message(self):
        i = run('let e = new SuppressedError("a", "b"); let v = e.message;')
        assert val(i) == ""

    def test_suppressed_error_stack_is_string(self):
        i = run('let e = new SuppressedError("a", "b", "x"); let v = typeof e.stack;')
        assert val(i) == "string"

    def test_suppressed_error_can_be_thrown_and_caught(self):
        i = run("""
let v = false;
try {
  throw new SuppressedError("e", "s", "test");
} catch (e) {
  v = e instanceof SuppressedError;
}
""")
        assert val(i) is True

    def test_suppressed_error_cause(self):
        i = run("""
let root = new Error("root");
let e = new SuppressedError("outer", "inner", "msg", {cause: root});
let v = e.cause === root;
""")
        assert val(i) is True


# ---------------------------------------------------------------------------
# TypedArray — callback methods
# ---------------------------------------------------------------------------

class TestTypedArrayMap:
    def test_map_doubles_values(self):
        i = run("let a = new Uint8Array([1,2,3]); let v = Array.from(a.map(x => x*2));")
        assert val(i) == [2, 4, 6]

    def test_map_index_available(self):
        i = run("let a = new Uint8Array([10,10,10]); let v = Array.from(a.map((x,i) => i));")
        assert val(i) == [0, 1, 2]

    def test_map_returns_typed_array(self):
        i = run("let a = new Uint8Array([1,2,3]); let v = typeof a.map(x => x*2);")
        assert val(i) == "object"

    def test_map_float32_array(self):
        i = run("let a = new Float32Array([1.0, 2.0, 3.0]); let v = Array.from(a.map(x => x+0.5));")
        assert val(i) == [1.5, 2.5, 3.5]


class TestTypedArrayFilter:
    def test_filter_even(self):
        i = run("let a = new Uint8Array([1,2,3,4,5,6]); let v = Array.from(a.filter(x => x%2===0));")
        assert val(i) == [2, 4, 6]

    def test_filter_none(self):
        i = run("let a = new Uint8Array([1,3,5]); let v = Array.from(a.filter(x => x%2===0));")
        assert val(i) == []

    def test_filter_all(self):
        i = run("let a = new Uint8Array([2,4,6]); let v = Array.from(a.filter(x => x%2===0));")
        assert val(i) == [2, 4, 6]


class TestTypedArrayFind:
    def test_find_existing(self):
        i = run("let a = new Uint8Array([1,2,3,4]); let v = a.find(x => x > 2);")
        assert val(i) == 3

    def test_find_missing(self):
        i = run("let a = new Uint8Array([1,2,3]); let v = typeof a.find(x => x > 10);")
        # undefined when not found — JS semantics
        assert val(i) == "undefined"

    def test_findIndex_existing(self):
        i = run("let a = new Uint8Array([1,2,3,4]); let v = a.findIndex(x => x > 2);")
        assert val(i) == 2

    def test_findIndex_missing(self):
        i = run("let a = new Uint8Array([1,2,3]); let v = a.findIndex(x => x > 10);")
        assert val(i) == -1

    def test_findLast_existing(self):
        i = run("let a = new Uint8Array([1,2,3,4,5]); let v = a.findLast(x => x%2===0);")
        assert val(i) == 4

    def test_findLastIndex_existing(self):
        i = run("let a = new Uint8Array([1,2,3,4,5]); let v = a.findLastIndex(x => x%2===0);")
        assert val(i) == 3


class TestTypedArrayEveryAndSome:
    def test_every_true(self):
        i = run("let a = new Uint8Array([2,4,6]); let v = a.every(x => x%2===0);")
        assert val(i) is True

    def test_every_false(self):
        i = run("let a = new Uint8Array([2,3,6]); let v = a.every(x => x%2===0);")
        assert val(i) is False

    def test_some_true(self):
        i = run("let a = new Uint8Array([1,3,4]); let v = a.some(x => x%2===0);")
        assert val(i) is True

    def test_some_false(self):
        i = run("let a = new Uint8Array([1,3,5]); let v = a.some(x => x%2===0);")
        assert val(i) is False


class TestTypedArrayForEach:
    def test_forEach_sums(self):
        i = run("""
let a = new Uint8Array([1,2,3,4]);
let sum = 0;
a.forEach(x => { sum += x; });
let v = sum;
""")
        assert val(i) == 10

    def test_forEach_index_available(self):
        i = run("""
let a = new Uint8Array([10,20,30]);
let indices = [];
a.forEach((x, i) => { indices.push(i); });
let v = indices;
""")
        assert val(i) == [0, 1, 2]


class TestTypedArrayReduce:
    def test_reduce_sum_with_initial(self):
        i = run("let a = new Uint8Array([1,2,3,4]); let v = a.reduce((acc, x) => acc + x, 0);")
        assert val(i) == 10

    def test_reduce_sum_no_initial(self):
        i = run("let a = new Uint8Array([1,2,3,4]); let v = a.reduce((acc, x) => acc + x);")
        assert val(i) == 10

    def test_reduceRight_string(self):
        i = run("let a = new Uint8Array([1,2,3]); let v = a.reduceRight((acc, x) => acc + String(x), \"\");")
        assert val(i) == "321"

    def test_reduceRight_no_initial(self):
        i = run("let a = new Uint8Array([1,2,3]); let v = a.reduceRight((acc, x) => acc + x);")
        assert val(i) == 6


class TestTypedArraySort:
    def test_sort_default_ascending(self):
        i = run("let a = new Uint8Array([3,1,2]); a.sort(); let v = Array.from(a);")
        assert val(i) == [1, 2, 3]

    def test_sort_with_comparator_descending(self):
        i = run("let a = new Uint8Array([3,1,2]); a.sort((a,b) => b-a); let v = Array.from(a);")
        assert val(i) == [3, 2, 1]

    def test_sort_mutates_in_place(self):
        i = run("let a = new Uint8Array([3,1,2]); a.sort(); let v = a.at(0);")
        assert val(i) == 1


# ---------------------------------------------------------------------------
# TypedArray — pure (non-callback) methods
# ---------------------------------------------------------------------------

class TestTypedArrayPureMethods:
    def test_reverse_in_place(self):
        i = run("let a = new Uint8Array([1,2,3]); a.reverse(); let v = Array.from(a);")
        assert val(i) == [3, 2, 1]

    def test_copyWithin(self):
        i = run("let a = new Uint8Array([1,2,3,4,5]); a.copyWithin(0, 3); let v = Array.from(a);")
        assert val(i) == [4, 5, 3, 4, 5]

    def test_copyWithin_with_end(self):
        i = run("let a = new Uint8Array([1,2,3,4,5]); a.copyWithin(1, 3, 5); let v = Array.from(a);")
        assert val(i) == [1, 4, 5, 4, 5]

    def test_join_default_separator(self):
        i = run("let a = new Uint8Array([1,2,3]); let v = a.join(\",\");")
        assert val(i) == "1,2,3"

    def test_join_custom_separator(self):
        i = run("let a = new Uint8Array([1,2,3]); let v = a.join(\"-\");")
        assert val(i) == "1-2-3"

    def test_includes_true(self):
        i = run("let a = new Uint8Array([1,2,3]); let v = a.includes(2);")
        assert val(i) is True

    def test_includes_false(self):
        i = run("let a = new Uint8Array([1,2,3]); let v = a.includes(99);")
        assert val(i) is False

    def test_indexOf_found(self):
        i = run("let a = new Uint8Array([1,2,3]); let v = a.indexOf(2);")
        assert val(i) == 1

    def test_indexOf_not_found(self):
        i = run("let a = new Uint8Array([1,2,3]); let v = a.indexOf(99);")
        assert val(i) == -1

    def test_lastIndexOf_found(self):
        i = run("let a = new Uint8Array([1,2,3,2]); let v = a.lastIndexOf(2);")
        assert val(i) == 3

    def test_at_positive(self):
        i = run("let a = new Uint8Array([10,20,30]); let v = a.at(1);")
        assert val(i) == 20

    def test_at_negative(self):
        i = run("let a = new Uint8Array([10,20,30]); let v = a.at(-1);")
        assert val(i) == 30

    def test_at_out_of_bounds(self):
        i = run("let a = new Uint8Array([10,20]); let v = a.at(99);")
        assert val(i) is None

    def test_entries_for_of(self):
        i = run("""
let a = new Uint8Array([10,20,30]);
let idxs = [];
for (let [i, x] of a.entries()) { idxs.push(i); }
let v = idxs;
""")
        assert val(i) == [0, 1, 2]

    def test_keys_for_of(self):
        i = run("""
let a = new Uint8Array([10,20,30]);
let ks = [];
for (let k of a.keys()) { ks.push(k); }
let v = ks;
""")
        assert val(i) == [0, 1, 2]

    def test_values_for_of(self):
        i = run("""
let a = new Uint8Array([10,20,30]);
let vs = [];
for (let x of a.values()) { vs.push(x); }
let v = vs;
""")
        assert val(i) == [10, 20, 30]

    def test_toReversed_non_mutating(self):
        i = run("""
let a = new Uint8Array([1,2,3]);
let b = a.toReversed();
let v = Array.from(a);
""")
        assert val(i) == [1, 2, 3]  # original unchanged

    def test_toReversed_result(self):
        i = run("let a = new Uint8Array([1,2,3]); let v = Array.from(a.toReversed());")
        assert val(i) == [3, 2, 1]

    def test_toSorted_non_mutating(self):
        i = run("""
let a = new Uint8Array([3,1,2]);
let b = a.toSorted();
let v = Array.from(a);
""")
        assert val(i) == [3, 1, 2]  # original unchanged

    def test_toSorted_result(self):
        i = run("let a = new Uint8Array([3,1,2]); let v = Array.from(a.toSorted());")
        assert val(i) == [1, 2, 3]
