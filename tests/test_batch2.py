"""
Tests for batch 2 features:

- Missing string methods: at, charAt, lastIndexOf, substring
- Missing list methods: reduce (both arg orders), findIndex, concat, unshift, splice,
  fill, zip (method), chunk, take, drop, flatten (deep)
- Missing dict methods: get, size, toList, clone
- throw/catch: raw thrown value bound to catch variable
- Pipeline stages with call-expression form: filter(pred), map(fn), each(fn)
"""

import pytest

from sprycode.interpreter import Interpreter, SpryRuntimeError
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.runtime.stdlib import SpryLogger


def run(source: str) -> Interpreter:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    out: list[str] = []
    interp = Interpreter(logger=SpryLogger(output=out))
    interp.run(program)
    return interp


# ---------------------------------------------------------------------------
# String methods
# ---------------------------------------------------------------------------


class TestStringMethods:
    def test_at_positive(self):
        i = run('let v = "hello".at(1)')
        assert i.globals.get("v") == "e"

    def test_at_negative(self):
        i = run('let v = "hello".at(-1)')
        assert i.globals.get("v") == "o"

    def test_at_out_of_range(self):
        i = run('let v = "hi".at(99)')
        assert i.globals.get("v") is None

    def test_char_at_first(self):
        i = run('let v = "hello".charAt(0)')
        assert i.globals.get("v") == "h"

    def test_char_at_last(self):
        i = run('let v = "hello".charAt(4)')
        assert i.globals.get("v") == "o"

    def test_char_at_out_of_range(self):
        i = run('let v = "hello".charAt(99)')
        assert i.globals.get("v") == ""

    def test_last_index_of(self):
        i = run('let v = "hello".lastIndexOf("l")')
        assert i.globals.get("v") == 3

    def test_last_index_of_not_found(self):
        i = run('let v = "hello".lastIndexOf("z")')
        assert i.globals.get("v") == -1

    def test_substring_two_args(self):
        i = run('let v = "hello".substring(1, 3)')
        assert i.globals.get("v") == "el"

    def test_substring_one_arg(self):
        i = run('let v = "hello".substring(2)')
        assert i.globals.get("v") == "llo"

    def test_substring_from_zero(self):
        i = run('let v = "hello".substring(0, 5)')
        assert i.globals.get("v") == "hello"

    def test_substr_alias(self):
        i = run('let v = "hello world".substr(6, 11)')
        assert i.globals.get("v") == "world"

    def test_match_all(self):
        i = run('let v = "abc123def456".matchAll("[0-9]+")')
        val = i.globals.get("v")
        assert isinstance(val, list)
        assert len(val) == 2

    def test_search_found(self):
        i = run('let v = "hello world".search("world")')
        assert i.globals.get("v") == 6

    def test_search_not_found(self):
        i = run('let v = "hello".search("xyz")')
        assert i.globals.get("v") == -1


# ---------------------------------------------------------------------------
# List methods
# ---------------------------------------------------------------------------


class TestListMethods:
    def test_reduce_fn_only(self):
        i = run("let v = [1, 2, 3, 4].reduce((acc, x) => acc + x)")
        assert i.globals.get("v") == 10

    def test_reduce_fn_init_new_order(self):
        # reduce(fn, init) — JS/SpryCode convention
        i = run("let v = [1, 2, 3, 4].reduce((acc, x) => acc + x, 0)")
        assert i.globals.get("v") == 10

    def test_reduce_init_fn_legacy_order(self):
        # reduce(init, fn) — legacy convention
        i = run("let v = [1, 2, 3, 4].reduce(0, (acc, x) => acc + x)")
        assert i.globals.get("v") == 10

    def test_reduce_product(self):
        i = run("let v = [1, 2, 3, 4].reduce((acc, x) => acc * x, 1)")
        assert i.globals.get("v") == 24

    def test_reduce_string_concat(self):
        i = run('let v = ["a", "b", "c"].reduce((acc, x) => acc + x, "")')
        assert i.globals.get("v") == "abc"

    def test_reduce_empty_no_init(self):
        i = run("let v = [5].reduce((acc, x) => acc + x)")
        assert i.globals.get("v") == 5

    def test_find_index_found(self):
        i = run("let v = [1, 2, 3, 4].findIndex(x => x > 2)")
        assert i.globals.get("v") == 2

    def test_find_index_not_found(self):
        i = run("let v = [1, 2, 3].findIndex(x => x > 100)")
        assert i.globals.get("v") == -1

    def test_find_index_first(self):
        i = run("let v = [10, 20, 30].findIndex(x => x == 10)")
        assert i.globals.get("v") == 0

    def test_concat(self):
        i = run("let v = [1, 2].concat([3, 4])")
        assert i.globals.get("v") == [1, 2, 3, 4]

    def test_concat_empty(self):
        i = run("let v = [1, 2].concat([])")
        assert i.globals.get("v") == [1, 2]

    def test_unshift(self):
        i = run("""
var a = [2, 3]
a.unshift(1)
let v = a
""")
        assert i.globals.get("v") == [1, 2, 3]

    def test_unshift_returns_length(self):
        i = run("""
var a = [2, 3]
let v = a.unshift(1)
""")
        assert i.globals.get("v") == 3

    def test_splice_delete(self):
        i = run("""
var a = [1, 2, 3, 4]
a.splice(1, 2)
let v = a
""")
        assert i.globals.get("v") == [1, 4]

    def test_splice_delete_one(self):
        i = run("""
var a = [1, 2, 3]
a.splice(1, 1)
let v = a
""")
        assert i.globals.get("v") == [1, 3]

    def test_fill_range(self):
        i = run("let v = [1, 2, 3, 4].fill(0, 1, 3)")
        assert i.globals.get("v") == [1, 0, 0, 4]

    def test_fill_all(self):
        i = run("let v = [1, 2, 3].fill(9, 0, 3)")
        assert i.globals.get("v") == [9, 9, 9]

    def test_zip_method(self):
        i = run('let v = [1, 2, 3].zip(["a", "b", "c"])')
        assert i.globals.get("v") == [[1, "a"], [2, "b"], [3, "c"]]

    def test_zip_shorter(self):
        i = run("let v = [1, 2].zip([10, 20, 30])")
        assert i.globals.get("v") == [[1, 10], [2, 20]]

    def test_chunk_even(self):
        i = run("let v = [1, 2, 3, 4, 5, 6].chunk(2)")
        assert i.globals.get("v") == [[1, 2], [3, 4], [5, 6]]

    def test_chunk_uneven(self):
        i = run("let v = [1, 2, 3, 4, 5].chunk(2)")
        assert i.globals.get("v") == [[1, 2], [3, 4], [5]]

    def test_chunk_by_three(self):
        i = run("let v = [1, 2, 3, 4, 5, 6].chunk(3)")
        assert i.globals.get("v") == [[1, 2, 3], [4, 5, 6]]

    def test_take(self):
        i = run("let v = [1, 2, 3, 4, 5].take(3)")
        assert i.globals.get("v") == [1, 2, 3]

    def test_take_all(self):
        i = run("let v = [1, 2, 3].take(10)")
        assert i.globals.get("v") == [1, 2, 3]

    def test_take_zero(self):
        i = run("let v = [1, 2, 3].take(0)")
        assert i.globals.get("v") == []

    def test_drop(self):
        i = run("let v = [1, 2, 3, 4, 5].drop(2)")
        assert i.globals.get("v") == [3, 4, 5]

    def test_drop_all(self):
        i = run("let v = [1, 2, 3].drop(10)")
        assert i.globals.get("v") == []

    def test_drop_zero(self):
        i = run("let v = [1, 2, 3].drop(0)")
        assert i.globals.get("v") == [1, 2, 3]

    def test_flatten_nested(self):
        i = run("let v = [[1, [2]], 3].flatten()")
        assert i.globals.get("v") == [1, 2, 3]

    def test_flatten_deeply_nested(self):
        i = run("let v = [[[1, 2], 3], [4, [5, [6]]]].flatten()")
        assert i.globals.get("v") == [1, 2, 3, 4, 5, 6]

    def test_flatten_already_flat(self):
        i = run("let v = [1, 2, 3].flatten()")
        assert i.globals.get("v") == [1, 2, 3]

    def test_copy(self):
        i = run("""
let a = [1, 2, 3]
let v = a.clone()
""")
        assert i.globals.get("v") == [1, 2, 3]

    def test_to_set(self):
        i = run("let v = [1, 2, 2, 3, 3, 3].toSet()")
        assert i.globals.get("v") == [1, 2, 3]


# ---------------------------------------------------------------------------
# Dict methods
# ---------------------------------------------------------------------------


class TestDictMethods:
    def test_get_existing(self):
        i = run("""
let m = {a: 1, b: 2}
let v = m.get("a")
""")
        assert i.globals.get("v") == 1

    def test_get_missing_no_default(self):
        i = run("""
let m = {a: 1}
let v = m.get("z")
""")
        assert i.globals.get("v") is None

    def test_get_missing_with_default(self):
        i = run("""
let m = {a: 1}
let v = m.get("z", 99)
""")
        assert i.globals.get("v") == 99

    def test_get_default_zero(self):
        i = run("""
let m = {a: 1}
let v = m.get("missing", 0)
""")
        assert i.globals.get("v") == 0

    def test_size(self):
        i = run("""
let m = {a: 1, b: 2, c: 3}
let v = m.size
""")
        assert i.globals.get("v") == 3

    def test_size_empty(self):
        i = run("""
let m = {}
let v = m.size
""")
        assert i.globals.get("v") == 0

    def test_length_alias(self):
        i = run("""
let m = {x: 1, y: 2}
let v = m.length
""")
        assert i.globals.get("v") == 2

    def test_to_list(self):
        i = run("""
let m = {a: 1}
let v = m.toList()
""")
        assert i.globals.get("v") == [["a", 1]]

    def test_clone(self):
        i = run("""
let original = {x: 10, y: 20}
let cloned = original.clone()
let v = cloned
""")
        assert i.globals.get("v") == {"x": 10, "y": 20}

    def test_clone_is_independent(self):
        i = run("""
var m = {a: 1}
let snapshot = m.clone()
m.set("b", 2)
let v = snapshot
""")
        # The clone should not reflect changes to original
        assert i.globals.get("v") == {"a": 1}

    def test_to_json(self):
        import json
        i = run("""
let m = {name: "Alice", age: 30}
let v = m.toJSON()
""")
        val = i.globals.get("v")
        assert isinstance(val, str)
        parsed = json.loads(val)
        assert parsed == {"name": "Alice", "age": 30}


# ---------------------------------------------------------------------------
# throw / catch — raw value binding
# ---------------------------------------------------------------------------


class TestThrowCatch:
    def test_throw_string_is_bound_raw(self):
        i = run("""
var caught = null
try {
    throw "something went wrong"
} catch e {
    caught = e
}
let v = caught
""")
        assert i.globals.get("v") == "something went wrong"

    def test_throw_number(self):
        i = run("""
var caught = null
try {
    throw 42
} catch e {
    caught = e
}
let v = caught
""")
        assert i.globals.get("v") == 42

    def test_throw_dict_preserves_code(self):
        i = run("""
var code = 0
try {
    throw {code: 404, message: "not found"}
} catch e {
    code = e.code
}
let v = code
""")
        assert i.globals.get("v") == 404

    def test_throw_dict_preserves_message(self):
        i = run("""
var msg = ""
try {
    throw {code: 500, message: "server error"}
} catch e {
    msg = e.message
}
let v = msg
""")
        assert i.globals.get("v") == "server error"

    def test_throw_dict_without_message_gets_one(self):
        i = run("""
var msg = null
try {
    throw {code: 404}
} catch e {
    msg = e.message
}
let v = msg != null
""")
        assert i.globals.get("v") is True

    def test_catch_without_throw(self):
        i = run("""
var v = "ok"
try {
    v = "in try"
} catch e {
    v = "in catch"
}
""")
        assert i.globals.get("v") == "in try"

    def test_throw_rethrow_pattern(self):
        i = run("""
var result = ""
try {
    try {
        throw "inner error"
    } catch inner_e {
        result = inner_e
        throw inner_e
    }
} catch outer_e {
    result = result + " + " + outer_e
}
let v = result
""")
        assert i.globals.get("v") == "inner error + inner error"


# ---------------------------------------------------------------------------
# Pipeline with call-expression form: |> filter(pred) / |> map(fn)
# ---------------------------------------------------------------------------


class TestPipelineCallForm:
    def test_pipeline_filter_parens(self):
        i = run("let v = [1, 2, 3, 4, 5] |> filter(x => x > 2)")
        assert i.globals.get("v") == [3, 4, 5]

    def test_pipeline_map_parens(self):
        i = run("let v = [1, 2, 3] |> map(x => x * 10)")
        assert i.globals.get("v") == [10, 20, 30]

    def test_pipeline_chained_parens(self):
        i = run("let v = [1, 2, 3, 4, 5] |> filter(x => x > 2) |> map(x => x * 10)")
        assert i.globals.get("v") == [30, 40, 50]

    def test_pipeline_filter_no_parens(self):
        # Original syntax without parens should still work
        i = run("let v = [1, 2, 3, 4, 5] |> filter x => x > 3")
        assert i.globals.get("v") == [4, 5]

    def test_pipeline_map_no_parens(self):
        i = run("let v = [1, 2, 3] |> map x => x * 2")
        assert i.globals.get("v") == [2, 4, 6]

    def test_pipeline_each_parens(self):
        # each is side-effect only — value passes through
        i = run("""
var side = []
let items = [10, 20, 30]
items |> each(x => side.push(x))
let v = side
""")
        assert i.globals.get("v") == [10, 20, 30]

    def test_pipeline_mixed_parens_and_bare(self):
        i = run("let v = [1, 2, 3, 4, 5] |> filter(x => x % 2 == 0) |> map x => x * 100")
        assert i.globals.get("v") == [200, 400]

    def test_pipeline_reduce_with_parens(self):
        i = run("let v = [1, 2, 3, 4, 5] |> reduce (acc, x) => acc + x")
        assert i.globals.get("v") == 15
