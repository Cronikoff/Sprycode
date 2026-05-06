"""Phase 61-62 feature tests — Array.reduce arity (index/array args),
findLast/findLastIndex arity, findIndex arity."""
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


def val(src: str, name: str = "v"):
    return run(src).globals.get(name)


# ---------------------------------------------------------------------------
# Array.reduce with index/array args
# ---------------------------------------------------------------------------

class TestReduceArity:
    def test_reduce_basic(self):
        src = """
let v = [1, 2, 3, 4].reduce((acc, x) => acc + x, 0)
"""
        assert val(src) == 10

    def test_reduce_with_index(self):
        src = """
let indices = []
[10, 20, 30].reduce((acc, x, i) => {
  indices.push(i)
  return acc + x
}, 0)
let v = indices.length
"""
        assert val(src) == 3

    def test_reduce_indices_correct(self):
        src = """
let sum_idx = 0
[10, 20, 30].reduce((acc, x, i) => {
  sum_idx = sum_idx + i
  return acc + x
}, 0)
let v = sum_idx
"""
        assert val(src) == 3  # 0 + 1 + 2

    def test_reduce_no_init(self):
        src = """
let v = [1, 2, 3].reduce((acc, x) => acc + x)
"""
        assert val(src) == 6


# ---------------------------------------------------------------------------
# findIndex arity
# ---------------------------------------------------------------------------

class TestFindIndexArity:
    def test_find_index_basic(self):
        src = """
let v = [1, 2, 3, 4].findIndex(x => x > 2)
"""
        assert val(src) == 2

    def test_find_index_with_index(self):
        src = """
let v = [1, 2, 3, 4].findIndex((x, i) => i == 2)
"""
        assert val(src) == 2

    def test_find_index_not_found(self):
        src = """
let v = [1, 2, 3].findIndex(x => x > 10)
"""
        assert val(src) == -1


# ---------------------------------------------------------------------------
# findLast / findLastIndex arity
# ---------------------------------------------------------------------------

class TestFindLastArity:
    def test_find_last_basic(self):
        src = """
let v = [1, 2, 3, 4, 5].findLast(x => x % 2 == 0)
"""
        assert val(src) == 4

    def test_find_last_with_index(self):
        src = """
let found = []
[10, 20, 30].findLast((x, i) => {
  found.push(i)
  return x > 5
})
let v = found.length
"""
        assert val(src) >= 1

    def test_find_last_index_basic(self):
        src = """
let v = [1, 2, 3, 4, 5].findLastIndex(x => x % 2 == 0)
"""
        assert val(src) == 3

    def test_find_last_index_with_index(self):
        src = """
let v = [1, 2, 3, 4].findLastIndex((x, i) => i < 2)
"""
        assert val(src) == 1
