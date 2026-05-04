"""Tests for Phase 51 features:
- Dict/object bracket index with missing key returns `undefined` (not raises)
- Catch destructuring: catch({a, b}) and catch([a, b, c])
- Catch binding is mutable: catch(e) { e = newValue } works
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
# Dict bracket-index with missing key → undefined
# ---------------------------------------------------------------------------

class TestDictMissingKeyReturnsUndefined:
    def test_missing_key_string(self) -> None:
        i = run("let obj = {a: 1}; let v = obj['b']")
        assert val(i) is None or str(val(i)) == "undefined"

    def test_missing_key_is_undefined(self) -> None:
        i = run("let obj = {}; let v = obj['x'] === undefined")
        assert val(i) is True

    def test_present_key_works(self) -> None:
        i = run("let obj = {a: 42}; let v = obj['a']")
        assert val(i) == 42

    def test_missing_falsy_check(self) -> None:
        i = run("let obj = {}; let v = !obj['nope']")
        assert val(i) is True

    def test_missing_key_nullish_coalesce(self) -> None:
        i = run("let obj = {a: 1}; let v = (obj['b'] ?? 'default')")
        assert val(i) == "default"

    def test_present_key_not_nullish(self) -> None:
        i = run("let obj = {x: 0}; let v = (obj['x'] ?? 99)")
        assert val(i) == 0

    def test_accumulate_pattern(self) -> None:
        i = run("""
let v = [1,2,3,4,5,6].reduce((acc, x) => {
  let key = x % 2 === 0 ? 'even' : 'odd'
  if(!acc[key]) acc[key] = []
  acc[key].push(x)
  return acc
}, {})
""")
        result = val(i)
        assert result['odd'] == [1, 3, 5]
        assert result['even'] == [2, 4, 6]

    def test_nested_missing_key(self) -> None:
        i = run("let obj = {a: {b: 1}}; let v = obj['a']['c']")
        assert val(i) is None or str(val(i)) == "undefined"

    def test_dynamic_key_round_trip(self) -> None:
        i = run("""
let obj = {}
let k = 'name'
obj[k] = 'Alice'
let v = obj[k]
""")
        assert val(i) == "Alice"

    def test_list_still_raises_oob(self) -> None:
        with pytest.raises(Exception):
            run("let v = [1,2,3][10]")

    def test_string_still_raises_oob(self) -> None:
        with pytest.raises(Exception):
            run("let v = 'hello'[99]")

    def test_count_occurrences(self) -> None:
        i = run("""
let words = ['the', 'cat', 'sat', 'on', 'the', 'mat', 'the']
let counts = {}
for(let w of words) {
  counts[w] = (counts[w] ?? 0) + 1
}
let v = counts['the']
""")
        assert val(i) == 3

    def test_optional_index_missing_key(self) -> None:
        i = run("let obj = {a: 1}; let v = obj?.['b']")
        result = val(i)
        assert result is None or str(result) == "undefined"

    def test_in_operator_unaffected(self) -> None:
        i = run("let obj = {a: 1}; let v = ['a' in obj, 'b' in obj]")
        assert val(i) == [True, False]


# ---------------------------------------------------------------------------
# Catch destructuring
# ---------------------------------------------------------------------------

class TestCatchDestructuring:
    def test_catch_object_destructure(self) -> None:
        i = run("""
var v = null
try {
  throw {code: 404, msg: 'not found'}
} catch({code, msg}) {
  v = code + ': ' + msg
}
""")
        assert val(i) == "404: not found"

    def test_catch_array_destructure(self) -> None:
        i = run("""
var v = null
try {
  throw [1, 2, 3]
} catch([a, b, c]) {
  v = a + b + c
}
""")
        assert val(i) == 6

    def test_catch_obj_destruct_defaults(self) -> None:
        i = run("""
var v = null
try {
  throw {code: 500}
} catch({code, msg = 'internal error'}) {
  v = code + ': ' + msg
}
""")
        assert val(i) == "500: internal error"

    def test_catch_array_partial(self) -> None:
        i = run("""
var head = null
try {
  throw [10, 20, 30, 40]
} catch([a]) {
  head = a
}
let v = head
""")
        assert val(i) == 10

    def test_catch_obj_destruct_used_in_body(self) -> None:
        i = run("""
var result = []
try {
  throw {x: 3, y: 4}
} catch({x, y}) {
  result.push(x * x + y * y)
}
let v = result[0]
""")
        assert val(i) == 25

    def test_catch_array_rest(self) -> None:
        i = run("""
var v = null
try {
  throw [1, 2, 3, 4, 5]
} catch([head, ...tail]) {
  v = [head, tail]
}
""")
        result = val(i)
        assert result[0] == 1
        assert result[1] == [2, 3, 4, 5]

    def test_catch_obj_destruct_rename(self) -> None:
        i = run("""
var v = null
try {
  throw {status: 400}
} catch({status: code}) {
  v = code
}
""")
        assert val(i) == 400

    def test_catch_obj_destruct_error_object(self) -> None:
        i = run("""
var v = null
try {
  throw new Error('oops')
} catch({message}) {
  v = message
}
""")
        assert val(i) == "oops"

    def test_catch_finally_with_destruct(self) -> None:
        i = run("""
var v = []
try {
  throw {x: 1, y: 2}
} catch({x, y}) {
  v.push(x + y)
} finally {
  v.push('done')
}
""")
        assert val(i) == [3, "done"]


# ---------------------------------------------------------------------------
# Catch binding is mutable
# ---------------------------------------------------------------------------

class TestCatchBindingMutable:
    def test_catch_binding_reassign(self) -> None:
        i = run("""
var original = null
var v = null
try {
  throw new Error('test')
} catch(e) {
  original = e.message
  e = null
  v = [original, e]
}
""")
        assert val(i) == ["test", None]

    def test_catch_binding_increment(self) -> None:
        i = run("""
var v = null
try {
  throw 5
} catch(e) {
  e += 10
  v = e
}
""")
        assert val(i) == 15

    def test_catch_binding_reassign_string(self) -> None:
        i = run("""
var v = null
try {
  throw new Error('original')
} catch(e) {
  let msg = e.message
  e = 'replaced'
  v = [msg, e]
}
""")
        assert val(i) == ["original", "replaced"]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestPhase51Integration:
    def test_word_frequency(self) -> None:
        i = run("""
fn wordFreq(text) {
  let counts = {}
  for(let w of text.split(' ')) {
    counts[w] = (counts[w] ?? 0) + 1
  }
  return counts
}
let freq = wordFreq('a b a c a b')
let v = [freq['a'], freq['b'], freq['c'], freq['d']]
""")
        result = val(i)
        assert result[0] == 3
        assert result[1] == 2
        assert result[2] == 1
        assert result[3] is None or str(result[3]) == "undefined"

    def test_group_by(self) -> None:
        i = run("""
fn groupItems(arr, keyFn) {
  return arr.reduce((acc, item) => {
    let key = keyFn(item)
    if(!acc[key]) acc[key] = []
    acc[key].push(item)
    return acc
  }, {})
}
let groups = groupItems([1,2,3,4,5,6], x => x % 2 === 0 ? 'even' : 'odd')
let v = [groups['even'].length, groups['odd'].length]
""")
        assert val(i) == [3, 3]

    def test_catch_destruct_retry_pattern(self) -> None:
        i = run("""
var attempts = 0
var v = null
fn tryOp() {
  attempts++
  if(attempts < 3) throw {code: attempts, retry: true}
  return 'success'
}
while(true) {
  try {
    v = tryOp()
    break
  } catch({code, retry}) {
    if(!retry) break
  }
}
""")
        assert val(i) == "success"

    def test_dict_index_in_template_literal(self) -> None:
        i = run("""
let lookup = {'a': 1, 'b': 2}
let v = `a=${lookup['a']} c=${lookup['c']}`
""")
        assert val(i) == "a=1 c=undefined"

    def test_catch_destruct_with_validation(self) -> None:
        i = run("""
fn checkData(data) {
  if(!data.name) throw {field: 'name', message: 'required'}
  if(!data.age) throw {field: 'age', message: 'required'}
  return data
}
var errors = []
try {
  checkData({name: '', age: 0})
} catch({field, message}) {
  errors.push(field + ': ' + message)
}
let v = errors
""")
        assert len(val(i)) == 1
        assert "required" in val(i)[0]
