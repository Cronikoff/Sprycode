"""Tests for Phase 53 features:
- new.target meta-property: returns constructor class inside `new`, undefined outside
- String.prototype.localeCompare: locale-aware string comparison
- Object.getOwnPropertySymbols: returns Symbol-keyed properties
- Object literal computed Symbol keys stored with identity
- JSON.stringify ignores Symbol-keyed properties
- Async generator next()/return()/throw() return Promises
- Intl.Segmenter: Unicode text segmentation (grapheme, word, sentence)
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
# new.target meta-property
# ---------------------------------------------------------------------------

class TestNewTarget:
    def test_new_target_in_constructor_is_class(self) -> None:
        i = run("""
class Foo {
  constructor() {
    this.isNew = new.target === Foo
  }
}
let f = new Foo()
let v = f.isNew
""")
        assert val(i) is True

    def test_new_target_outside_constructor_is_undefined(self) -> None:
        i = run("""
fn notNew() {
  return new.target === undefined
}
let v = notNew()
""")
        assert val(i) is True

    def test_new_target_in_subclass_is_subclass(self) -> None:
        i = run("""
class Animal {
  constructor() {
    this.targetName = new.target.name
  }
}
class Dog extends Animal {}
let d = new Dog()
let v = d.targetName
""")
        assert val(i) == "Dog"

    def test_new_target_in_base_constructor_directly(self) -> None:
        i = run("""
class Base {
  constructor() {
    this.targetName = new.target.name
  }
}
let b = new Base()
let v = b.targetName
""")
        assert val(i) == "Base"

    def test_new_target_not_base_in_subclass(self) -> None:
        i = run("""
class Base {
  constructor() {
    this.isBase = new.target === Base
  }
}
class Child extends Base {}
let c = new Child()
let v = c.isBase
""")
        assert val(i) is False

    def test_new_target_in_function_is_undefined(self) -> None:
        i = run("""
fn plainFn() { return new.target }
let v = plainFn() === undefined
""")
        assert val(i) is True

    def test_new_target_same_class_identity(self) -> None:
        i = run("""
class MyClass {
  constructor() {
    this.target = new.target
  }
}
let m = new MyClass()
let v = m.target === MyClass
""")
        assert val(i) is True

    def test_new_target_abstract_base_pattern(self) -> None:
        i = run("""
class AbstractBase {
  constructor() {
    this.isAbstractCalled = new.target === AbstractBase
  }
}
class Concrete extends AbstractBase {}
let c = new Concrete()
let v = c.isAbstractCalled
""")
        assert val(i) is False

    def test_new_target_in_arrow_fn_inherits_outer(self) -> None:
        i = run("""
let v = false
class Foo {
  constructor() {
    let check = () => new.target === Foo
    v = check()
  }
}
let f = new Foo()
""")
        assert val(i) is True

    def test_new_target_name_property(self) -> None:
        i = run("""
class Widget {
  constructor() {
    this.ctorName = new.target.name
  }
}
let w = new Widget()
let v = w.ctorName
""")
        assert val(i) == "Widget"


# ---------------------------------------------------------------------------
# String.prototype.localeCompare
# ---------------------------------------------------------------------------

class TestLocaleCompare:
    def test_locale_compare_less(self) -> None:
        i = run("let v = 'a'.localeCompare('b')")
        assert val(i) == -1

    def test_locale_compare_greater(self) -> None:
        i = run("let v = 'b'.localeCompare('a')")
        assert val(i) == 1

    def test_locale_compare_equal(self) -> None:
        i = run("let v = 'a'.localeCompare('a')")
        assert val(i) == 0

    def test_locale_compare_numbers(self) -> None:
        i = run("let v = '10'.localeCompare('9')")
        assert isinstance(val(i), int)

    def test_locale_compare_empty(self) -> None:
        i = run("let v = ''.localeCompare('')")
        assert val(i) == 0

    def test_locale_compare_empty_vs_nonempty(self) -> None:
        i = run("let v = ''.localeCompare('a')")
        assert val(i) == -1

    def test_locale_compare_used_in_sort(self) -> None:
        i = run("""
let words = ['banana', 'apple', 'cherry']
let v = words.toSorted((a, b) => a.localeCompare(b))
""")
        assert val(i) == ["apple", "banana", "cherry"]

    def test_locale_compare_returns_number_type(self) -> None:
        i = run("let v = typeof 'x'.localeCompare('y')")
        assert val(i) == "number"

    def test_locale_compare_with_locale_arg(self) -> None:
        i = run("let v = 'a'.localeCompare('b', 'en')")
        assert val(i) == -1

    def test_locale_compare_with_options_arg(self) -> None:
        i = run("let v = 'a'.localeCompare('b', 'en', {sensitivity: 'base'})")
        assert val(i) == -1


# ---------------------------------------------------------------------------
# Object.getOwnPropertySymbols
# ---------------------------------------------------------------------------

class TestGetOwnPropertySymbols:
    def test_no_symbols_returns_empty(self) -> None:
        i = run("""
let obj = {a: 1, b: 2}
let v = Object.getOwnPropertySymbols(obj).length
""")
        assert val(i) == 0

    def test_one_symbol_key(self) -> None:
        i = run("""
let sym = Symbol('s')
let obj = {[sym]: 42, a: 1}
let v = Object.getOwnPropertySymbols(obj).length
""")
        assert val(i) == 1

    def test_symbol_identity_preserved(self) -> None:
        i = run("""
let sym = Symbol('s')
let obj = {[sym]: 42}
let syms = Object.getOwnPropertySymbols(obj)
let v = syms[0] === sym
""")
        assert val(i) is True

    def test_multiple_symbols(self) -> None:
        i = run("""
let s1 = Symbol('a')
let s2 = Symbol('b')
let obj = {[s1]: 1, [s2]: 2, str: 3}
let v = Object.getOwnPropertySymbols(obj).length
""")
        assert val(i) == 2

    def test_well_known_symbol(self) -> None:
        i = run("""
let obj = {}
obj[Symbol.iterator] = fn() {}
let v = Object.getOwnPropertySymbols(obj).length
""")
        assert val(i) == 1

    def test_symbol_value_accessible(self) -> None:
        i = run("""
let sym = Symbol('key')
let obj = {[sym]: 99}
let syms = Object.getOwnPropertySymbols(obj)
let v = obj[syms[0]]
""")
        assert val(i) == 99


# ---------------------------------------------------------------------------
# JSON.stringify ignores Symbol-keyed properties
# ---------------------------------------------------------------------------

class TestJsonStringifySymbols:
    def test_symbol_key_ignored(self) -> None:
        import json as _json
        i = run("""
let sym = Symbol('s')
let obj = {[sym]: 1, a: 2}
let v = JSON.stringify(obj)
""")
        result = _json.loads(val(i))
        assert result == {"a": 2}
        assert len(result) == 1

    def test_only_symbol_keys_returns_empty_obj(self) -> None:
        i = run("""
let sym = Symbol('s')
let obj = {[sym]: 42}
let v = JSON.stringify(obj)
""")
        assert val(i) == "{}"

    def test_mixed_keys_string_preserved(self) -> None:
        import json as _json
        i = run("""
let sym = Symbol('hidden')
let obj = {name: 'Alice', [sym]: 'secret', age: 30}
let v = JSON.stringify(obj)
""")
        result = _json.loads(val(i))
        assert "name" in result
        assert "age" in result
        assert "hidden" not in result
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Async generator Promises
# ---------------------------------------------------------------------------

class TestAsyncGeneratorPromises:
    def test_next_returns_promise(self) -> None:
        i = run("""
async fn* ag() { yield 1 }
let g = ag()
let v = g.next() instanceof Promise
""")
        assert val(i) is True

    def test_next_promise_resolves_to_value(self) -> None:
        i = run("""
async fn* ag() { yield 42 }
let g = ag()
let p = g.next()
let v = p.value
""")
        assert val(i) == {"value": 42, "done": False}

    def test_return_returns_promise(self) -> None:
        i = run("""
async fn* ag() { yield 1; yield 2 }
let g = ag()
g.next()
let v = g.return('done') instanceof Promise
""")
        assert val(i) is True

    def test_throw_returns_promise(self) -> None:
        i = run("""
async fn* ag() {
  try {
    yield 1
  } catch(e) {
    yield 'caught'
  }
}
let g = ag()
g.next()
let v = g.throw(new Error('boom')) instanceof Promise
""")
        assert val(i) is True

    def test_for_await_iterates_values(self) -> None:
        i = run("""
async fn* counter() {
  let i = 0
  while (i < 3) { yield i; i++ }
}
let results = []
async fn main() {
  for await (let n of counter()) {
    results.push(n)
  }
}
main()
let v = results
""")
        assert val(i) == [0, 1, 2]

    def test_async_gen_done_promise(self) -> None:
        i = run("""
async fn* ag() { yield 1 }
let g = ag()
g.next()
let p = g.next()
let v = p.value
""")
        assert val(i) == {"value": None, "done": True}

    def test_sync_gen_next_not_promise(self) -> None:
        i = run("""
fn* sg() { yield 1 }
let g = sg()
let v = g.next() instanceof Promise
""")
        assert val(i) is False

    def test_async_gen_spread_works(self) -> None:
        i = run("""
async fn* nums() { yield 1; yield 2; yield 3 }
let results = []
async fn collect() {
  for await (let n of nums()) {
    results.push(n)
  }
}
collect()
let v = results
""")
        assert val(i) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Intl.Segmenter
# ---------------------------------------------------------------------------

class TestIntlSegmenter:
    def test_segmenter_exists(self) -> None:
        i = run("let v = typeof new Intl.Segmenter('en')")
        assert val(i) == "object"

    def test_create_word_segmenter(self) -> None:
        i = run("""
let seg = new Intl.Segmenter('en', {granularity: 'word'})
let v = typeof seg.segment
""")
        assert val(i) == "function"

    def test_word_segmentation_basic(self) -> None:
        i = run("""
let seg = new Intl.Segmenter('en', {granularity: 'word'})
let v = [...seg.segment('Hello World')].filter(s => s.isWordLike).map(s => s.segment)
""")
        assert val(i) == ["Hello", "World"]

    def test_word_segment_has_is_word_like(self) -> None:
        i = run("""
let seg = new Intl.Segmenter('en', {granularity: 'word'})
let segs = [...seg.segment('hi there')]
let v = segs.filter(s => s.isWordLike).length
""")
        assert val(i) == 2

    def test_grapheme_segmentation(self) -> None:
        i = run("""
let seg = new Intl.Segmenter('en', {granularity: 'grapheme'})
let v = [...seg.segment('abc')].map(s => s.segment)
""")
        assert val(i) == ["a", "b", "c"]

    def test_grapheme_length(self) -> None:
        i = run("""
let seg = new Intl.Segmenter('en', {granularity: 'grapheme'})
let v = [...seg.segment('hello')].length
""")
        assert val(i) == 5

    def test_segment_has_index(self) -> None:
        i = run("""
let seg = new Intl.Segmenter('en', {granularity: 'grapheme'})
let segs = [...seg.segment('abc')]
let v = segs.map(s => s.index)
""")
        assert val(i) == [0, 1, 2]

    def test_segment_has_input(self) -> None:
        i = run("""
let seg = new Intl.Segmenter('en', {granularity: 'grapheme'})
let segs = [...seg.segment('abc')]
let v = segs[0].input
""")
        assert val(i) == "abc"

    def test_resolved_options(self) -> None:
        i = run("""
let seg = new Intl.Segmenter('en-US', {granularity: 'word'})
let opts = seg.resolvedOptions()
let v = [opts.locale, opts.granularity]
""")
        assert val(i) == ["en-US", "word"]

    def test_default_granularity_is_grapheme(self) -> None:
        i = run("""
let seg = new Intl.Segmenter('en')
let opts = seg.resolvedOptions()
let v = opts.granularity
""")
        assert val(i) == "grapheme"

    def test_sentence_segmentation(self) -> None:
        i = run("""
let seg = new Intl.Segmenter('en', {granularity: 'sentence'})
let v = [...seg.segment('Hello. World.')].length
""")
        assert val(i) >= 2

    def test_empty_string_segmentation(self) -> None:
        i = run("""
let seg = new Intl.Segmenter('en', {granularity: 'grapheme'})
let v = [...seg.segment('')].length
""")
        assert val(i) == 0

    def test_intl_segmenter_three_words(self) -> None:
        i = run("""
let seg = new Intl.Segmenter('en', {granularity: 'word'})
let v = [...seg.segment('one two three')].filter(s => s.isWordLike).map(s => s.segment)
""")
        assert val(i) == ["one", "two", "three"]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestPhase53Integration:
    def test_abstract_class_pattern_with_new_target(self) -> None:
        i = run("""
class Shape {
  constructor() {
    if (new.target === Shape) {
      this.error = 'Cannot instantiate Shape directly'
    } else {
      this.type = new.target.name
    }
  }
}
class Circle extends Shape {}
let c = new Circle()
let v = c.type
""")
        assert val(i) == "Circle"

    def test_symbol_keys_not_in_json_but_accessible(self) -> None:
        import json as _json
        i = run("""
let id = Symbol('id')
let user = {name: 'Alice', [id]: 123}
let json = JSON.stringify(user)
let v = [JSON.parse(json).name, user[Object.getOwnPropertySymbols(user)[0]]]
""")
        result = val(i)
        assert result[0] == "Alice"
        assert result[1] == 123

    def test_sorted_words_with_locale_compare(self) -> None:
        i = run("""
let fruits = ['cherry', 'apple', 'banana', 'date']
let v = fruits.toSorted((a, b) => a.localeCompare(b))
""")
        assert val(i) == ["apple", "banana", "cherry", "date"]

    def test_async_gen_with_early_return(self) -> None:
        i = run("""
async fn* sequence() {
  yield 1
  yield 2
  yield 3
}
let results = []
async fn collect() {
  let g = sequence()
  results.push((await g.next()).value)
  results.push((await g.next()).value)
  let done = await g.return('stop')
  results.push(done.done)
}
collect()
let v = results
""")
        assert val(i) == [1, 2, True]

    def test_segmenter_word_count(self) -> None:
        i = run("""
fn wordCount(text) {
  let seg = new Intl.Segmenter('en', {granularity: 'word'})
  return [...seg.segment(text)].filter(s => s.isWordLike).length
}
let v = wordCount('The quick brown fox')
""")
        assert val(i) == 4

    def test_new_target_registry_pattern(self) -> None:
        i = run("""
let registry = []
class Plugin {
  constructor(name) {
    this.name = name
    this.pluginType = new.target.name
  }
}
class AudioPlugin extends Plugin {}
class VideoPlugin extends Plugin {}
let a = new AudioPlugin('eq')
let b = new VideoPlugin('filter')
let v = [a.pluginType, b.pluginType]
""")
        assert val(i) == ["AudioPlugin", "VideoPlugin"]
