"""Tests for Phase 104: performance timeline API."""
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


class TestPerformanceNow:
    def test_now_is_number(self):
        i = run("let v = typeof performance.now();")
        assert val(i) == "number"

    def test_now_monotonic(self):
        i = run("let a = performance.now(); let b = performance.now(); let v = b >= a;")
        assert val(i) is True


class TestPerformanceMark:
    def test_mark_returns_entry(self):
        i = run("""
let m = performance.mark("start");
let v = m.name;
""")
        assert val(i) == "start"

    def test_mark_entry_type(self):
        i = run("""
let m = performance.mark("phase");
let v = m.entryType;
""")
        assert val(i) == "mark"

    def test_get_entries_by_type_mark(self):
        i = run("""
performance.mark("a");
performance.mark("b");
let entries = performance.getEntriesByType("mark");
let v = entries.length;
""")
        assert val(i) == 2


class TestPerformanceMeasure:
    def test_measure_without_marks(self):
        i = run("""
let m = performance.measure("m1");
let v = m.entryType;
""")
        assert val(i) == "measure"

    def test_measure_between_marks(self):
        i = run("""
performance.mark("s");
performance.mark("e");
let m = performance.measure("delta", "s", "e");
let v = m.duration >= 0;
""")
        assert val(i) is True

    def test_measure_defaults_end_to_now(self):
        i = run("""
performance.mark("s");
let m = performance.measure("delta", "s");
let v = m.duration >= 0;
""")
        assert val(i) is True

    def test_measure_unknown_start_uses_zero(self):
        i = run("""
let m = performance.measure("delta", "missing");
let v = m.startTime === 0;
""")
        assert val(i) is True

    def test_get_entries_by_type_measure(self):
        i = run("""
performance.measure("m1");
performance.measure("m2");
let v = performance.getEntriesByType("measure").length;
""")
        assert val(i) == 2


class TestPerformanceEntries:
    def test_get_entries_by_type_without_arg_returns_all(self):
        i = run("""
performance.mark("a");
performance.measure("m");
let v = performance.getEntriesByType().length;
""")
        assert val(i) == 2

    def test_get_entries_by_name(self):
        i = run("""
performance.mark("same");
performance.measure("same");
let v = performance.getEntriesByName("same").length;
""")
        assert val(i) == 2

    def test_get_entries_by_name_with_type(self):
        i = run("""
performance.mark("same");
performance.measure("same");
let v = performance.getEntriesByName("same", "mark").length;
""")
        assert val(i) == 1


class TestPerformanceClear:
    def test_clear_marks_all(self):
        i = run("""
performance.mark("a");
performance.mark("b");
performance.clearMarks();
let v = performance.getEntriesByType("mark").length;
""")
        assert val(i) == 0

    def test_clear_marks_by_name(self):
        i = run("""
performance.mark("a");
performance.mark("b");
performance.clearMarks("a");
let v = performance.getEntriesByName("a", "mark").length;
""")
        assert val(i) == 0

    def test_clear_measures_all(self):
        i = run("""
performance.measure("m1");
performance.measure("m2");
performance.clearMeasures();
let v = performance.getEntriesByType("measure").length;
""")
        assert val(i) == 0

    def test_clear_measures_by_name(self):
        i = run("""
performance.measure("m1");
performance.measure("m2");
performance.clearMeasures("m1");
let v = performance.getEntriesByName("m1", "measure").length;
""")
        assert val(i) == 0


class TestPerformanceCompatibility:
    def test_existing_phase15_mark_usage_still_ok(self):
        i = run("""
performance.mark("start");
let v = true;
""")
        assert val(i) is True

    def test_existing_phase15_measure_usage_still_ok(self):
        i = run("""
performance.measure("m", "start", "end");
let v = true;
""")
        assert val(i) is True
