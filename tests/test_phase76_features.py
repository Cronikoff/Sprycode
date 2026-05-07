"""Tests for Phase 76 features: Iterators and Iteration Protocol."""
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


class TestCustomIterator:
    def test_custom_iterator_next_value(self):
        src = """
let count = 0;
let iter = {
  next: function() {
    count++;
    if (count <= 3) return {value: count, done: false};
    return {value: undefined, done: true};
  }
};
let r1 = iter.next();
let v = r1.value;
"""
        assert val(run(src)) == 1

    def test_custom_iterator_next_done_false(self):
        src = """
let count = 0;
let iter = {
  next: function() {
    count++;
    if (count <= 3) return {value: count, done: false};
    return {value: undefined, done: true};
  }
};
let r1 = iter.next();
let v = r1.done;
"""
        assert val(run(src)) is False

    def test_custom_iterator_done_true(self):
        src = """
let count = 0;
let iter = {
  next: function() {
    count++;
    if (count <= 2) return {value: count, done: false};
    return {value: undefined, done: true};
  }
};
iter.next();
iter.next();
let r = iter.next();
let v = r.done;
"""
        assert val(run(src)) is True

    def test_custom_iterator_sum(self):
        src = """
let count = 0;
let iter = {
  next: function() {
    count++;
    if (count <= 3) return {value: count, done: false};
    return {value: undefined, done: true};
  }
};
let r1 = iter.next();
let r2 = iter.next();
let r3 = iter.next();
let v = r1.value + r2.value + r3.value;
"""
        assert val(run(src)) == 6

    def test_iterator_terminates_on_done_true(self):
        src = """
let iter = {
  next: function() {
    return {value: undefined, done: true};
  }
};
let v = Array.from(iter).length;
"""
        assert val(run(src)) == 0


class TestForOfIterator:
    def test_for_of_array(self):
        src = """
let sum = 0;
for (const x of [1, 2, 3]) { sum = sum + x; }
let v = sum;
"""
        assert val(run(src)) == 6

    def test_for_of_string(self):
        src = """
let chars = [];
for (const c of 'abc') { chars.push(c); }
let v = chars.join('');
"""
        assert val(run(src)) == "abc"

    def test_for_of_generator(self):
        src = """
function* gen() {
  yield 1;
  yield 2;
  yield 3;
}
let sum = 0;
for (const x of gen()) { sum += x; }
let v = sum;
"""
        assert val(run(src)) == 6

    def test_for_of_map(self):
        src = """
let m = new Map();
m.set('a', 1);
m.set('b', 2);
let keys = [];
for (const [k, v2] of m) { keys.push(k); }
let v = keys.join(',');
"""
        assert val(run(src)) == "a,b"

    def test_for_of_set(self):
        src = """
let s = new Set([1, 2, 3]);
let sum = 0;
for (const x of s) { sum = sum + x; }
let v = sum;
"""
        assert val(run(src)) == 6

    def test_for_of_object_entries(self):
        src = """
let sum = 0;
for (const [k, v2] of Object.entries({a: 1, b: 2})) {
  sum += v2;
}
let v = sum;
"""
        assert val(run(src)) == 3

    def test_for_of_object_keys(self):
        src = """
let keys = [];
for (const k of Object.keys({a: 1, b: 2})) {
  keys.push(k);
}
let v = keys.join(',');
"""
        assert val(run(src)) == "a,b"


class TestSymbolIterator:
    def test_array_symbol_iterator(self):
        src = """
let arr = [10, 20, 30];
let iter = arr[Symbol.iterator]();
let r1 = iter.next();
let v = r1.value;
"""
        assert val(run(src)) == 10

    def test_array_symbol_iterator_done(self):
        src = """
let arr = [1];
let iter = arr[Symbol.iterator]();
iter.next();
let r = iter.next();
let v = r.done;
"""
        assert val(run(src)) is True

    def test_symbol_iterator_on_custom_object(self):
        src = """
let obj = {
  data: [10, 20, 30],
  [Symbol.iterator]: function() {
    let idx = 0;
    let data = [10, 20, 30];
    return {
      next: function() {
        if (idx < data.length) {
          return {value: data[idx++], done: false};
        }
        return {value: undefined, done: true};
      }
    };
  }
};
let v = Array.from(obj).join(',');
"""
        assert val(run(src)) == "10,20,30"

    def test_class_symbol_iterator(self):
        src = """
class Range {
  constructor(start, end) {
    this.start = start;
    this.end = end;
  }
  [Symbol.iterator]() {
    let current = this.start;
    let end = this.end;
    return {
      next() {
        if (current <= end) {
          return {value: current++, done: false};
        }
        return {value: undefined, done: true};
      }
    };
  }
}
let r = new Range(1, 3);
let sum = 0;
for (const n of r) { sum += n; }
let v = sum;
"""
        assert val(run(src)) == 6

    def test_spread_with_symbol_iterator(self):
        src = """
let obj = {
  [Symbol.iterator]: function() {
    let n = 0;
    return {
      next: function() {
        n++;
        if (n <= 3) return {value: n, done: false};
        return {value: undefined, done: true};
      }
    };
  }
};
let v = [...obj].length;
"""
        assert val(run(src)) == 3

    def test_array_from_symbol_iterator(self):
        src = """
let obj = {
  [Symbol.iterator]: function() {
    let n = 0;
    return {
      next: function() {
        n++;
        if (n <= 3) return {value: n * 2, done: false};
        return {value: undefined, done: true};
      }
    };
  }
};
let v = Array.from(obj).join(',');
"""
        assert val(run(src)) == "2,4,6"


class TestIteratorFeatures:
    def test_spread_array(self):
        src = "let v = [...[1, 2, 3]].length;"
        assert val(run(src)) == 3

    def test_array_from_iterator_with_next(self):
        src = """
let count = 0;
let iter = {
  next: function() {
    count++;
    if (count <= 3) return {value: count, done: false};
    return {value: undefined, done: true};
  }
};
let v = Array.from(iter).length;
"""
        assert val(run(src)) == 3

    def test_generator_as_iterator(self):
        src = """
function* gen() {
  yield 10;
  yield 20;
}
let g = gen();
let r1 = g.next();
let r2 = g.next();
let v = r1.value + r2.value;
"""
        assert val(run(src)) == 30

    def test_iterator_chaining_manually(self):
        src = """
let count1 = 0;
let iter1 = {
  next: function() {
    count1++;
    if (count1 <= 2) return {value: count1, done: false};
    return {value: undefined, done: true};
  }
};
let count2 = 0;
let iter2 = {
  next: function() {
    count2++;
    if (count2 <= 2) return {value: count2 + 10, done: false};
    return {value: undefined, done: true};
  }
};
let results = [];
let r = iter1.next();
while (!r.done) { results.push(r.value); r = iter1.next(); }
r = iter2.next();
while (!r.done) { results.push(r.value); r = iter2.next(); }
let v = results.join(',');
"""
        assert val(run(src)) == "1,2,11,12"

    def test_array_destructuring_from_iterator(self):
        src = """
let obj = {
  [Symbol.iterator]: function() {
    let n = 0;
    return {
      next: function() {
        n++;
        if (n <= 3) return {value: n, done: false};
        return {value: undefined, done: true};
      }
    };
  }
};
let [a, b, c] = obj;
let v = a + b + c;
"""
        assert val(run(src)) == 6

    def test_map_iteration_values(self):
        src = """
let m = new Map();
m.set('x', 10);
m.set('y', 20);
let sum = 0;
for (const [k, v2] of m) { sum += v2; }
let v = sum;
"""
        assert val(run(src)) == 30

    def test_set_iteration_collect(self):
        src = """
let s = new Set([4, 5, 6]);
let result = [];
for (const x of s) { result.push(x); }
let v = result.length;
"""
        assert val(run(src)) == 3

    def test_string_iteration_chars(self):
        src = """
let result = [];
for (const c of 'hello') { result.push(c); }
let v = result.length;
"""
        assert val(run(src)) == 5

    def test_generator_spread(self):
        src = """
function* nums() {
  yield 1;
  yield 2;
  yield 3;
}
let v = [...nums()].join(',');
"""
        assert val(run(src)) == "1,2,3"
